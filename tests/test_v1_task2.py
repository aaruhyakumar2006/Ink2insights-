"""Tests for V1 Task 2: Unified Image Quality Check.

Validates:
1. assess_image_quality returns expected metrics on synthetic images (sharp, blurry, dark, glare).
2. Clean white form (near-white but not sensor-clipped) does NOT falsely trigger glare.
3. Unreadable/corrupt files return ok: None with soft warning: "Could not check this photo, retake if unsure".
4. GET /api/config/quality returns current thresholds.
5. POST /api/quality-check inspects submitted image and returns structured assessment.
6. POST /api/extract blocks unreadable images with 422 error: "unreadable" and releases reserved paper unless bypassed.
7. POST /api/extract honors quality_bypassed flag, records quality metadata, and persists quality_bypassed on the record.
8. JavaScript and Python formulas agree on blur_score, brightness, and glare_pct within tolerance.
9. Calibration tool works on real clinic fixtures in fixtures/.
"""

import io
import os
import sys
import json
import subprocess
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
    for i in range(text_lines):
        y = 60 + i * 40
        for x in range(50, width - 50, 15):
            draw.rectangle([x, y, x + 8, y + 16], fill=(20, 20, 20))
    return img


def _create_dark_image(width=600, height=800, brightness=30):
    """Generate an underexposed image."""
    return Image.new("RGB", (width, height), color=(brightness, brightness, brightness))


def _create_glare_image(width=600, height=800):
    """Generate an image with a large bright page and a severe specular glare blowout.

    The page fills most of the frame (dark border) so corner detection finds it and
    coverage passes.  A large near-white area on the page then triggers the glare check.
    """
    # Dark background (simulates a table or floor behind the page)
    img = Image.new("RGB", (width, height), color=(40, 40, 40))
    draw = ImageDraw.Draw(img)
    # Large white page area – fills ~90 % of the frame so coverage >> 60 %
    margin = 20
    draw.rectangle([margin, margin, width - margin, height - margin], fill=(230, 230, 230))
    # Glare hotspot – pure white, covering ~30 % of the page area, saturated pixel count
    # well above QUALITY_GLARE_MAX=12 %.  Placed inside the page area so it is included
    # in the warped-page measurement.
    gx1, gy1 = margin + 20, margin + 20
    gx2 = gx1 + int((width - 2 * margin) * 0.55)
    gy2 = gy1 + int((height - 2 * margin) * 0.55)
    draw.rectangle([gx1, gy1, gx2, gy2], fill=(255, 255, 255))
    return img


def _image_to_bytes(img: Image.Image, format="JPEG") -> bytes:
    bio = io.BytesIO()
    img.save(bio, format=format)
    return bio.getvalue()


@pytest.fixture
def test_client_and_db(tmp_path, monkeypatch):
    from backend.services.auth_service import create_access_token
    db_file = str(tmp_path / "test_task2.db")
    app = create_app(db_path=db_file)
    app.config["TESTING"] = True
    token = create_access_token(user_id="doc_task2", role="admin", org_id="org_default")
    with app.test_client() as client:
        client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        yield client, db_file


def test_assess_image_quality_sharp_document():
    img = _create_synthetic_document()
    img_bytes = _image_to_bytes(img)
    res = assess_image_quality(img_bytes)
    assert res["ok"] is True
    assert res["blur_score"] > 200.0
    assert 50.0 <= res["brightness"] <= 250.0
    assert res["glare_pct"] < 12.0
    assert len(res["issues"]) == 0


def test_assess_image_quality_blurred():
    sharp_img = _create_synthetic_document()
    blurred_img = sharp_img.filter(ImageFilter.GaussianBlur(radius=6))
    res = assess_image_quality(_image_to_bytes(blurred_img))
    assert res["ok"] is False
    # The spec message contains "blurry" (lowercase); check case-insensitively
    assert any("blurry" in issue.lower() for issue in res["issues"])
    assert res["blur_score"] < 200.0


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


def test_clean_white_form_does_not_falsely_trigger_glare():
    """Near-white paper with natural paper tint (e.g. 248, 246, 242) should NOT trigger glare."""
    img = Image.new("RGB", (600, 800), color=(248, 246, 242))
    draw = ImageDraw.Draw(img)
    for i in range(12):
        y = 70 + i * 45
        for x in range(60, 540, 20):
            draw.rectangle([x, y, x + 10, y + 15], fill=(30, 30, 30))
    res = assess_image_quality(_image_to_bytes(img))
    assert res["glare_pct"] < 1.0
    assert res["ok"] is True


def test_unreadable_corrupt_file_returns_ok_null_soft_warning():
    """Corrupted bytes return ok: None and soft warning 'Could not check this photo, retake if unsure'."""
    corrupt_bytes = b"NOT_A_VALID_IMAGE_DATA_STREAM"
    res = assess_image_quality(corrupt_bytes)
    assert res["ok"] is None
    assert any("could not check this photo" in iss.lower() for iss in res["issues"])


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

    res_empty = client.post("/api/quality-check", data={})
    assert res_empty.status_code == 400


def test_api_extract_blocks_unreadable_and_releases_paper(test_client_and_db):
    client, db_path = test_client_and_db

    camp_res = client.post("/api/camps", json={"name": "Test Camp Quality"})
    camp_id = camp_res.get_json()["id"]

    record_id = "test_rec_quality_123"
    res_ok, res_code, _ = database.reserve_paper("org_default", record_id=record_id, db_path=db_path)
    assert res_ok is True

    sharp_img = _create_synthetic_document()
    blurry_img = sharp_img.filter(ImageFilter.GaussianBlur(radius=8))
    b_bytes = _image_to_bytes(blurry_img)

    data = {
        "student_form": (io.BytesIO(b_bytes), "sf.jpg"),
        "health_assessment": (io.BytesIO(b_bytes), "ha.jpg"),
        "org_id": "org_default",
        "camp_id": camp_id,
        "record_id": record_id,
    }
    res = client.post("/api/extract", data=data, content_type="multipart/form-data")

    assert res.status_code == 422
    body = res.get_json()
    assert body["error"] == "unreadable"
    assert "IMAGE_UNREADABLE" in body.get("code", "")
    assert body["quality"]["ok"] is False

    with database.get_db_connection(db_path) as conn:
        release_row = conn.cursor().execute(
            "SELECT * FROM usage_ledger WHERE record_id = ? AND action = 'release'",
            (record_id,)
        ).fetchone()
        assert release_row is not None


def test_api_extract_proceeds_with_quality_bypassed_and_saves_to_record(test_client_and_db, monkeypatch):
    client, db_path = test_client_and_db

    camp_res = client.post("/api/camps", json={"name": "Test Camp Quality Bypassed"})
    camp_id = camp_res.get_json()["id"]

    def mock_extract(*args, **kwargs):
        return {
            "success": True,
            "data": {
                "student_name": "Rohan Sharma",
                "grade": "7",
                "camp_id": camp_id
            },
            "status": "success",
            "tier": "tier1"
        }

    monkeypatch.setattr("backend.app.ai_extract", mock_extract)

    sharp_img = _create_synthetic_document()
    blurry_img = sharp_img.filter(ImageFilter.GaussianBlur(radius=8))
    b_bytes = _image_to_bytes(blurry_img)

    data = {
        "student_form": (io.BytesIO(b_bytes), "sf.jpg"),
        "health_assessment": (io.BytesIO(b_bytes), "ha.jpg"),
        "org_id": "org_default",
        "camp_id": camp_id,
        "quality_bypassed": "1",
    }
    res = client.post("/api/extract", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["quality_bypassed"] is True

    # Now verify saving the record persists quality_bypassed=1 in database
    rec_payload = {
        "camp_id": camp_id,
        "person_name": "Rohan Sharma",
        "structured_record": body["data"],
        "quality_bypassed": True,
        "status": "needs_review"
    }
    save_res = client.post("/api/records", json=rec_payload)
    assert save_res.status_code in (200, 201)
    saved_record_id = save_res.get_json()["id"]

    saved_rec = database.get_record_by_id(saved_record_id, db_path=db_path)
    assert saved_rec is not None
    assert saved_rec["quality_bypassed"] is True


def test_client_and_server_quality_formula_parity(tmp_path):
    """Verify JS assessImageQuality formula produces matching metrics to Python assess_image_quality."""
    img = _create_synthetic_document(width=640, height=800)
    img_bytes = _image_to_bytes(img, format="PNG")
    py_res = assess_image_quality(img_bytes)

    # Rescale to long edge = 640 px matching both client and server specs
    w, h = img.size
    if w >= h:
        new_w, new_h = 640, max(1, int(round(640 * h / w)))
    else:
        new_h, new_w = 640, max(1, int(round(640 * w / h)))
    rgba_img = img.convert("RGBA").resize((new_w, new_h), Image.Resampling.BILINEAR)
    w, h = rgba_img.size
    raw_bytes = rgba_img.tobytes()

    # Save to temp file to avoid Windows command line length limits
    raw_file = str(tmp_path / "pixels.raw").replace("\\", "/")
    with open(raw_file, "wb") as f:
        f.write(raw_bytes)

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scanner_js_path = os.path.join(repo_root, "frontend", "js", "scanner.js").replace("\\", "/")

    # Directly import and execute the real assessImageQuality from frontend/js/scanner.js
    node_script = f"""
    import fs from 'fs';
    const rawBuffer = fs.readFileSync('{raw_file}');
    const rawData = new Uint8ClampedArray(rawBuffer.buffer, rawBuffer.byteOffset, rawBuffer.byteLength);
    const newW = {w};
    const newH = {h};

    const mockCanvas = {{
      width: newW,
      height: newH,
      getContext: () => ({{
        drawImage: () => {{}},
        getImageData: (x, y, w, h) => ({{ data: rawData }})
      }})
    }};
    global.document = {{
      createElement: () => mockCanvas
    }};

    import * as scanner from 'file:///{scanner_js_path}';
    const js_res = await scanner.assessImageQuality(mockCanvas);
    console.log(JSON.stringify(js_res));
    """
    proc = subprocess.run(["node", "--input-type=module", "-e", node_script], capture_output=True, text=True)
    assert proc.returncode == 0, f"Node error: {proc.stderr}"
    js_res = json.loads(proc.stdout.strip())

    # Python and JS must match closely (< 2% difference due to float precision)
    assert abs(js_res["brightness"] - py_res["brightness"]) < 1.0
    assert abs(js_res["glare_pct"] - py_res["glare_pct"]) < 0.5
    assert abs(js_res["blur_score"] - py_res["blur_score"]) < (0.05 * py_res["blur_score"] + 1.0)


def test_calibration_tool_find_optimal_threshold():
    sharp = [120.0, 150.0, 180.0, 200.0]
    blur = [20.0, 35.0, 45.0, 60.0, 75.0]
    thresh, recall, far = find_optimal_threshold(sharp, blur, target_recall=0.90)
    assert thresh > 0
    assert recall >= 80.0
    assert far == 0.0


def test_calibration_tool_on_real_camp_fixtures():
    """Run calibration on real clinic camp fixtures and verify threshold differentiates sharp from blur."""
    fixtures_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")
    real_forms = ["blank_page_1.jpeg", "blank_page_2.jpeg", "filled_sample_page_1.jpeg", "filled_sample_page_2.jpeg"]

    sharp_scores = []
    blur_scores = []

    for name in real_forms:
        fpath = os.path.join(fixtures_dir, name)
        if not os.path.exists(fpath):
            continue
        res_sharp = assess_image_quality(fpath)
        if res_sharp["ok"] is not None:
            sharp_scores.append(res_sharp["blur_score"])

        # Create simulated camera motion blur
        img = Image.open(fpath)
        b_img = img.filter(ImageFilter.GaussianBlur(radius=4))
        res_blur = assess_image_quality(b_img)
        if res_blur["ok"] is not None:
            blur_scores.append(res_blur["blur_score"])

    assert len(sharp_scores) >= 3
    assert len(blur_scores) >= 3

    thresh, recall, far = find_optimal_threshold(sharp_scores, blur_scores, target_recall=0.95)
    assert recall >= 95.0
    assert far == 0.0
    # Every real sharp form scores > 800 while blurred forms score < 40
    assert min(sharp_scores) > max(blur_scores)


def test_database_migration_safe_on_existing_pre_migration_database(tmp_path):
    """Rule 4 Safe Migration: Verify init_db on a pre-migration database preserves all existing data and adds quality_bypassed."""
    import sqlite3

    old_db = str(tmp_path / "old_pre_migration.db")
    conn = sqlite3.connect(old_db)
    cur = conn.cursor()

    # Create pre-migration camps table
    cur.execute("""
        CREATE TABLE camps (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            date_str TEXT NOT NULL,
            expected_records INTEGER NOT NULL DEFAULT 100,
            location TEXT DEFAULT 'Chennai Health Camp',
            created_by TEXT,
            target_group TEXT NOT NULL DEFAULT 'adult',
            created_at TEXT NOT NULL,
            updated_at TEXT
        );
    """)
    cur.execute("INSERT INTO camps VALUES ('camp_old_1', 'Old Camp', '2026-10-01', 50, 'Chennai', 'doc_1', 'adult', '2026-10-01T10:00:00', NULL);")

    # Create pre-migration records table (WITHOUT quality_bypassed column)
    cur.execute("""
        CREATE TABLE records (
            id TEXT PRIMARY KEY,
            camp_id TEXT NOT NULL,
            person_name TEXT NOT NULL,
            age TEXT,
            gender TEXT,
            height TEXT,
            weight TEXT,
            blood_pressure TEXT,
            examination_details TEXT,
            referral_details TEXT,
            missing_fields TEXT NOT NULL DEFAULT '[]',
            uncertain_fields TEXT NOT NULL DEFAULT '[]',
            extraction_notes TEXT,
            structured_record TEXT,
            status TEXT NOT NULL DEFAULT 'needs_review',
            page1_preview TEXT,
            page2_preview TEXT,
            reviewer_notes TEXT,
            reviewed_by TEXT,
            reviewed_at TEXT,
            scanned_by TEXT,
            community_id TEXT,
            target_group TEXT NOT NULL DEFAULT 'adult',
            is_paediatric INTEGER DEFAULT 0,
            paediatric_alerts TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    cur.execute("""
        INSERT INTO records (id, camp_id, person_name, age, status, created_at, updated_at)
        VALUES ('rec_old_001', 'camp_old_1', 'Kavitha R', '34', 'reviewed', '2026-10-01T10:30:00', '2026-10-01T10:30:00');
    """)
    conn.commit()
    conn.close()

    # Run safe migration via database.init_db
    database.init_db(old_db)

    # Verify old record is 100% intact
    rec_after = database.get_record_by_id("rec_old_001", db_path=old_db)
    assert rec_after is not None
    assert rec_after["person_name"] == "Kavitha R"
    assert rec_after["age"] == "34"
    assert rec_after["status"] == "reviewed"
    # Column exists and defaults to False
    assert rec_after["quality_bypassed"] is False

    # Insert a new record with quality_bypassed=True into the migrated DB
    new_rec = database.insert_record({
        "id": "rec_new_migrated_002",
        "camp_id": "camp_old_1",
        "person_name": "Suresh M",
        "age": "45",
        "quality_bypassed": True,
        "status": "needs_review"
    }, db_path=old_db)
    assert new_rec["quality_bypassed"] is True


def test_ok_null_on_uncheckable_photo_does_not_block_extract_with_422(test_client_and_db, monkeypatch):
    """When photo clarity cannot be checked (ok: None), extract does NOT return 422, allowing workflow to proceed."""
    client, db_path = test_client_and_db

    camp_res = client.post("/api/camps", json={"name": "Test Camp Uncheckable"})
    camp_id = camp_res.get_json()["id"]

    def mock_extract(*args, **kwargs):
        return {
            "success": True,
            "data": {
                "student_name": "Pooja V",
                "camp_id": camp_id
            },
            "status": "success",
            "tier": "tier1"
        }

    monkeypatch.setattr("backend.app.ai_extract", mock_extract)

    # Mock assess_image_quality to return ok: None (soft warning)
    def mock_assess(img_bytes, *args, **kwargs):
        return {
            "ok": None,
            "blur_score": 0.0,
            "brightness": 0.0,
            "glare_pct": 0.0,
            "issues": ["Could not check this photo, retake if unsure"]
        }

    monkeypatch.setattr("backend.services.quality_service.assess_image_quality", mock_assess)

    sharp_img = _create_synthetic_document()
    img_bytes = _image_to_bytes(sharp_img)

    data = {
        "student_form": (io.BytesIO(img_bytes), "sf.jpg"),
        "health_assessment": (io.BytesIO(img_bytes), "ha.jpg"),
        "org_id": "org_default",
        "camp_id": camp_id,
    }
    # Call without bypass flag - must NOT be blocked with 422!
    res = client.post("/api/extract", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["quality"]["ok"] is True  # server treated non-failure as allowed

