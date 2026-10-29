"""Tests for V1 Task 2: Unified Image Quality Check.

Validates:
1. assess_image_quality returns expected metrics on synthetic images (sharp, blurry, dark, glare).
2. GET /api/config/quality returns current thresholds.
3. POST /api/quality-check inspects submitted image and returns structured assessment.
4. POST /api/extract blocks unreadable images with 422 error: "unreadable" and releases reserved paper unless bypassed.
5. POST /api/extract honors quality_bypassed flag and records quality metadata.
6. Calibration tool (tools/calibrate_quality.py) functions properly on sample sets.
"""

import io
import os
import sys
import pytest
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

from backend.app import create_app
from backend import database
from backend.services.quality_service import assess_image_quality, get_quality_config
from tools.calibrate_quality import find_optimal_threshold


def _create_synthetic_document(text_lines=15, width=600, height=800, brightness=200):
    """Generate a high-contrast synthetic printed document."""
    img = Image.new("RGB", (width, height), color=(brightness, brightness, brightness))
    draw = ImageDraw.Draw(img)
    # Draw dark black grid/lines mimicking document text
    for i in range(text_lines):
        y = 60 + i * 40
        # Draw dotted / striped line representing text glyphs
        for x in range(50, width - 50, 15):
            draw.rectangle([x, y, x + 8, y + 16], fill=(20, 20, 20))
    return img


def _create_dark_image(width=600, height=800, brightness=30):
    """Generate an underexposed image."""
    return Image.new("RGB", (width, height), color=(brightness, brightness, brightness))


def _create_glare_image(width=600, height=800):
    """Generate an image with a severe white glare spot (> 15% of pixels at 255)."""
    img = Image.new("RGB", (width, height), color=(140, 140, 140))
    draw = ImageDraw.Draw(img)
    # Large saturated white rectangle
    glare_w = int(width * 0.5)
    glare_h = int(height * 0.5)
    draw.rectangle([100, 100, 100 + glare_w, 100 + glare_h], fill=(255, 255, 255))
    return img


def _image_to_bytes(img: Image.Image, format="JPEG") -> bytes:
    bio = io.BytesIO()
    img.save(bio, format=format)
    return bio.getvalue()


@pytest.fixture
def test_client_and_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_task2.db")
    app = create_app(db_path=db_file)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client, db_file


def test_assess_image_quality_sharp_document():
    img = _create_synthetic_document()
    img_bytes = _image_to_bytes(img)
    res = assess_image_quality(img_bytes)
    assert res["ok"] is True
    assert res["blur_score"] > 80.0
    assert 50.0 <= res["brightness"] <= 250.0
    assert res["glare_pct"] < 12.0
    assert len(res["issues"]) == 0


def test_assess_image_quality_blurred():
    sharp_img = _create_synthetic_document()
    blurred_img = sharp_img.filter(ImageFilter.GaussianBlur(radius=6))
    res = assess_image_quality(_image_to_bytes(blurred_img))
    assert res["ok"] is False
    assert any("Blurry" in issue for issue in res["issues"])
    assert res["blur_score"] < 80.0


def test_assess_image_quality_dark():
    dark_img = _create_dark_image(brightness=30)
    res = assess_image_quality(_image_to_bytes(dark_img))
    assert res["ok"] is False
    assert any("dark" in issue.lower() for issue in res["issues"])
    assert res["brightness"] < 50.0


def test_assess_image_quality_glare():
    glare_img = _create_glare_image()
    res = assess_image_quality(_image_to_bytes(glare_img))
    assert res["ok"] is False
    assert any("glare" in issue.lower() for issue in res["issues"])
    assert res["glare_pct"] > 12.0


def test_api_config_quality_endpoint(test_client_and_db, monkeypatch):
    client, _ = test_client_and_db
    monkeypatch.setenv("QUALITY_BLUR_MIN", "95.5")
    monkeypatch.setenv("QUALITY_DARK_MAX", "42.0")
    monkeypatch.setenv("QUALITY_GLARE_MAX", "15.0")

    res = client.get("/api/config/quality")
    assert res.status_code == 200
    data = res.get_json()
    assert data["blur_min"] == 95.5
    assert data["dark_max"] == 42.0
    assert data["glare_max"] == 15.0


def test_api_quality_check_endpoint(test_client_and_db):
    client, _ = test_client_and_db
    sharp_img = _create_synthetic_document()
    buf = io.BytesIO(_image_to_bytes(sharp_img))

    # Multipart file upload
    res = client.post(
        "/api/quality-check",
        data={"file": (buf, "doc.jpg")},
        content_type="multipart/form-data"
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert "blur_score" in data
    assert "brightness" in data
    assert "glare_pct" in data

    # Missing file returns 400
    res_empty = client.post("/api/quality-check", data={})
    assert res_empty.status_code == 400


def test_api_extract_blocks_unreadable_and_releases_paper(test_client_and_db, monkeypatch):
    client, db_path = test_client_and_db

    # Create camp and patient
    camp_res = client.post("/api/camps", json={"name": "Test Camp Quality"})
    camp_id = camp_res.get_json().get("camp_id") or "test_camp_q"

    # Reserve paper
    record_id = "test_rec_quality_123"
    res_ok, res_code, _ = database.reserve_paper("org_default", record_id=record_id, db_path=db_path)
    assert res_ok is True

    # Generate severely blurred image
    sharp_img = _create_synthetic_document()
    blurry_img = sharp_img.filter(ImageFilter.GaussianBlur(radius=8))
    b_bytes = _image_to_bytes(blurry_img)

    # Call /api/extract without bypass
    data = {
        "student_form": (io.BytesIO(b_bytes), "sf.jpg"),
        "health_assessment": (io.BytesIO(b_bytes), "ha.jpg"),
        "org_id": "org_default",
        "camp_id": camp_id,
        "record_id": record_id,
    }
    res = client.post("/api/extract", data=data, content_type="multipart/form-data")

    # Must return 422 unreadable
    assert res.status_code == 422
    body = res.get_json()
    assert body["error"] == "unreadable"
    assert "IMAGE_UNREADABLE" in body.get("code", "")
    assert body["quality"]["ok"] is False

    # Check that reserved paper was released!
    with database.get_db_connection(db_path) as conn:
        release_row = conn.cursor().execute(
            "SELECT * FROM usage_ledger WHERE record_id = ? AND action = 'release'",
            (record_id,)
        ).fetchone()
        assert release_row is not None


def test_api_extract_proceeds_with_quality_bypassed(test_client_and_db, monkeypatch):
    client, db_path = test_client_and_db

    # Mock ai_extract so we don't call real Gemini in tests
    def mock_extract(*args, **kwargs):
        return {
            "success": True,
            "data": {
                "student_name": "Test Student",
                "grade": "5",
                "camp_id": "test_camp"
            },
            "status": "success",
            "tier": "tier1"
        }

    monkeypatch.setattr("backend.app.ai_extract", mock_extract)

    sharp_img = _create_synthetic_document()
    blurry_img = sharp_img.filter(ImageFilter.GaussianBlur(radius=8))
    b_bytes = _image_to_bytes(blurry_img)

    # Call /api/extract WITH quality_bypassed=1
    data = {
        "student_form": (io.BytesIO(b_bytes), "sf.jpg"),
        "health_assessment": (io.BytesIO(b_bytes), "ha.jpg"),
        "org_id": "org_default",
        "quality_bypassed": "1",
    }
    res = client.post("/api/extract", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["quality_bypassed"] is True
    assert body["quality"]["ok"] is False


def test_calibration_tool_find_optimal_threshold():
    # Sharp scores: 120, 150, 180, 200
    # Blur scores: 20, 35, 45, 60, 75
    sharp = [120.0, 150.0, 180.0, 200.0]
    blur = [20.0, 35.0, 45.0, 60.0, 75.0]

    thresh, recall, far = find_optimal_threshold(sharp, blur, target_recall=0.90)
    assert thresh > 0
    assert recall >= 80.0
    assert far == 0.0  # None of the sharp scores fall below ~70
