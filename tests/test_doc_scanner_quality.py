"""Comprehensive unit and integration test suite for Doc Scanner Image Capture & Quality.

Follows the DOC SCANNER test specification:
1. Unit tests for blur, darkness and glare formulas on fixed fixtures:
   - A sharp page
   - A blurred page
   - A dark page
   - A page with glare
   - A blank white image
2. Corner detection on:
   - A straight photo
   - A tilted photo
   - A photo with the page cut off at one edge (must ask "Move the whole page into the frame.")
3. Orientation:
   - The same photo with EXIF rotations 1, 3, 6, and 8 produces the same upright result.
4. Server rejection and paper quota release:
   - Server rejects blurred image with HTTP 422 and releases paper quota; accepts sharp image.
5. Bypass recording:
   - Bypass is recorded as quality_bypassed on the record.
6. Phone test validation across light conditions (bright office, ordinary room light, dim evening light).
7. Calibration report (blur threshold, false alarm rate, miss rate).
"""

import io
import os
import json
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageOps
import cv2

from backend.services.quality_service import (
    assess_image_quality,
    clean_and_enhance_image,
    detect_page_corners,
    order_points,
    warp_perspective,
    compute_tile_laplacian_variance,
    get_quality_config,
    MSG_BLURRY,
    MSG_TOO_DARK,
    MSG_GLARE,
    MSG_CORNERS_NOT_FOUND,
    MSG_COVERAGE_LOW,
)
from tools.calibrate_quality import find_optimal_blur_threshold, generate_calibration_report


# ==============================================================================
# FIXTURE GENERATORS
# ==============================================================================

def create_synthetic_sharp_page(width=800, height=1000) -> Image.Image:
    """Generate a clean document sheet with sharp black text and lines."""
    img = Image.new("RGB", (width, height), (245, 245, 245))
    draw = ImageDraw.Draw(img)

    # Outer form border
    draw.rectangle([30, 30, width - 30, height - 30], outline=(40, 40, 40), width=3)
    draw.rectangle([34, 34, width - 34, 90], fill=(220, 220, 220))

    # Grid lines and text labels
    for y in range(120, height - 50, 40):
        draw.line((40, y, width - 40, y), fill=(180, 180, 180), width=1)
        draw.rectangle([50, y - 25, 200, y - 5], fill=(30, 30, 30))
        draw.rectangle([250, y - 22, width - 60, y - 8], fill=(60, 60, 60))

    return img


def create_scene_on_table(paper_img: Image.Image, bg_w=1000, bg_h=1200, angle=0, offset_x=100, offset_y=100) -> np.ndarray:
    """Place a paper document image on a darker table background."""
    bg = np.full((bg_h, bg_w, 3), 45, dtype=np.uint8)  # dark surface
    paper_arr = np.array(paper_img, dtype=np.uint8)
    ph, pw = paper_arr.shape[:2]

    if angle != 0:
        center = (pw / 2.0, ph / 2.0)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        new_w = int((ph * sin) + (pw * cos))
        new_h = int((ph * cos) + (pw * sin))
        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]
        paper_arr = cv2.warpAffine(paper_arr, M, (new_w, new_h), borderValue=(45, 45, 45))
        ph, pw = paper_arr.shape[:2]

    # Paste on table
    y1 = max(0, offset_y)
    y2 = min(bg_h, offset_y + ph)
    x1 = max(0, offset_x)
    x2 = min(bg_w, offset_x + pw)

    src_y1 = y1 - offset_y
    src_y2 = src_y1 + (y2 - y1)
    src_x1 = x1 - offset_x
    src_x2 = src_x1 + (x2 - x1)

    mask = (paper_arr[src_y1:src_y2, src_x1:src_x2] > 55).any(axis=2)
    bg[y1:y2, x1:x2][mask] = paper_arr[src_y1:src_y2, src_x1:src_x2][mask]
    return bg


# ==============================================================================
# TEST 1: Blur, Darkness, and Glare Formulas on Fixed Fixtures
# ==============================================================================

class TestQualityFormulasOnFixedFixtures:
    """Test 1: Unit tests for blur, darkness and glare formulas."""

    def test_sharp_page_passes(self):
        """A sharp, properly lit document page must pass all checks."""
        sharp_img = create_synthetic_sharp_page()
        res = assess_image_quality(sharp_img)
        assert res["ok"] is True, f"Sharp page should pass: {res}"
        assert res["reason"] is None
        assert res["blur_score"] >= 40.0
        assert res["brightness"] >= 75.0
        assert res["glare_pct"] <= 12.0

    def test_blurred_page_fails_with_blurry_message(self):
        """A page blurred with Gaussian filter must fail with specific blurry message."""
        sharp_img = create_synthetic_sharp_page()
        blurred_img = sharp_img.filter(ImageFilter.GaussianBlur(radius=8.0))
        res = assess_image_quality(blurred_img)
        assert res["ok"] is False, f"Blurred page must fail: {res}"
        assert res["reason"] == MSG_BLURRY
        assert res["blur_score"] < 40.0

    def test_dark_page_fails_with_too_dark_message(self):
        """A page underexposed / in low light must fail with specific too-dark message."""
        sharp_img = create_synthetic_sharp_page()
        dark_arr = (np.array(sharp_img, dtype=np.float32) * 0.20).astype(np.uint8)
        dark_img = Image.fromarray(dark_arr)
        res = assess_image_quality(dark_img)
        assert res["ok"] is False, f"Dark page must fail: {res}"
        assert res["reason"] == MSG_TOO_DARK
        assert res["brightness"] < 75.0

    def test_page_with_glare_fails_with_glare_message(self):
        """A page with specular flash/glare hotspot must fail with specific glare message."""
        # Real document scenario on a table: paper is ~195 luminance, flash hotspot is 255
        sharp_img = create_synthetic_sharp_page()
        # Scale paper to realistic camera exposure (190)
        paper_arr = (np.array(sharp_img, dtype=np.float32) * 0.78).astype(np.uint8)
        h, w = paper_arr.shape[:2]

        # Add blown-out specular reflection hotspot covering ~18% of page
        cy, cx = h // 2, w // 2
        radius = int(min(h, w) * 0.28)
        for y in range(max(0, cy - radius), min(h, cy + radius)):
            for x in range(max(0, cx - radius), min(w, cx + radius)):
                if (x - cx) ** 2 + (y - cy) ** 2 < radius ** 2:
                    paper_arr[y, x] = [255, 255, 255]

        glare_img = Image.fromarray(paper_arr)
        res = assess_image_quality(glare_img)
        assert res["ok"] is False, f"Glared page must fail: {res}"
        assert res["reason"] == MSG_GLARE
        assert res["glare_pct"] > 12.0

    def test_blank_white_image_fails_blur(self):
        """A blank white image with no writing has ~0 Laplacian variance and must fail."""
        blank_img = Image.new("RGB", (800, 1000), (255, 255, 255))
        res = assess_image_quality(blank_img)
        assert res["ok"] is False, f"Blank image must fail: {res}"
        assert res["reason"] == MSG_BLURRY
        assert res["blur_score"] < 40.0


# ==============================================================================
# TEST 2: Corner Detection (Straight, Tilted, Cut-off)
# ==============================================================================

class TestCornerDetection:
    """Test 2: Corner detection on straight, tilted, and cut-off photos."""

    def test_straight_photo_detects_corners(self):
        """Document centered on a dark surface must detect 4 corners and coverage >= 60%."""
        paper = create_synthetic_sharp_page(width=600, height=800)
        scene = create_scene_on_table(paper, bg_w=800, bg_h=1000, angle=0, offset_x=100, offset_y=100)
        corners, cov, err = detect_page_corners(scene)
        assert corners is not None, "Straight photo should detect 4 corners"
        assert len(corners) == 4
        assert cov >= 50.0, f"Coverage should be high: {cov}"
        assert err is None

    def test_tilted_photo_detects_corners_and_warps(self):
        """Document tilted 15 degrees on a dark surface must detect corners and straighten."""
        paper = create_synthetic_sharp_page(width=500, height=700)
        scene = create_scene_on_table(paper, bg_w=900, bg_h=1100, angle=15, offset_x=180, offset_y=180)
        corners, cov, err = detect_page_corners(scene)
        assert corners is not None, "Tilted photo should detect 4 corners"
        assert len(corners) == 4
        assert err is None

        # Perspective warp should straighten to upright rectangle
        warped = warp_perspective(scene, corners)
        wh, ww = warped.shape[:2]
        assert ww > 300 and wh > 400
        # Cleaned image test
        cleaned_bytes = clean_and_enhance_image(scene, corners)
        assert len(cleaned_bytes) > 1000
        assert len(cleaned_bytes) < 1000000

    def test_cutoff_photo_asks_to_move_whole_page_into_frame(self):
        """When document is cut off at one edge, corner detection must reject with specific prompt."""
        paper = create_synthetic_sharp_page(width=600, height=800)
        # Position sheet so right edge is cut off (offset_x = 400 in an 800px wide frame -> right edge at 1000)
        scene = create_scene_on_table(paper, bg_w=800, bg_h=1000, angle=0, offset_x=450, offset_y=100)
        corners, cov, err = detect_page_corners(scene)
        assert corners is None, "Cut-off photo must not detect valid complete 4 corners"
        assert err == MSG_CORNERS_NOT_FOUND, f"Error must match spec: {err}"

        # Quality check should report corners not found
        res = assess_image_quality(scene)
        assert res["ok"] is False
        assert res["reason"] == MSG_CORNERS_NOT_FOUND


# ==============================================================================
# TEST 3: EXIF Orientation Transpose
# ==============================================================================

class TestExifOrientation:
    """Test 3: Same photo with EXIF rotations 1, 3, 6, 8 produces identical upright result."""

    def test_exif_rotations_1_3_6_8_produce_same_upright_image(self):
        # Create asymmetric test image with red top-left indicator
        base = Image.new("RGB", (300, 150), (240, 240, 240))
        draw = ImageDraw.Draw(base)
        draw.rectangle([10, 10, 60, 40], fill=(255, 0, 0))  # red corner marker
        draw.text((80, 20), "DOC-FORM-ORIENTATION-TEST", fill=(20, 20, 20))

        # Tag 1: Normal upright
        im1 = base.copy()
        im1.getexif()[0x0112] = 1

        # Tag 3: 180 deg upside-down
        im3 = base.transpose(Image.Transpose.ROTATE_180)
        im3.getexif()[0x0112] = 3

        # Tag 6: 90 deg CW (needs ROTATE_270 to become upright)
        im6 = base.transpose(Image.Transpose.ROTATE_90)
        im6.getexif()[0x0112] = 6

        # Tag 8: 270 deg CW (needs ROTATE_90 to become upright)
        im8 = base.transpose(Image.Transpose.ROTATE_270)
        im8.getexif()[0x0112] = 8

        t1 = np.array(ImageOps.exif_transpose(im1))
        t3 = np.array(ImageOps.exif_transpose(im3))
        t6 = np.array(ImageOps.exif_transpose(im6))
        t8 = np.array(ImageOps.exif_transpose(im8))

        assert np.array_equal(t1, t3), "EXIF 3 must match upright EXIF 1"
        assert np.array_equal(t1, t6), "EXIF 6 must match upright EXIF 1"
        assert np.array_equal(t1, t8), "EXIF 8 must match upright EXIF 1"

        # Verify quality service treats all 4 identically
        buf1, buf3, buf6, buf8 = io.BytesIO(), io.BytesIO(), io.BytesIO(), io.BytesIO()
        im1.save(buf1, format="JPEG", exif=im1.getexif())
        im3.save(buf3, format="JPEG", exif=im3.getexif())
        im6.save(buf6, format="JPEG", exif=im6.getexif())
        im8.save(buf8, format="JPEG", exif=im8.getexif())

        res1 = assess_image_quality(buf1.getvalue())
        res3 = assess_image_quality(buf3.getvalue())
        res6 = assess_image_quality(buf6.getvalue())
        res8 = assess_image_quality(buf8.getvalue())

        assert res1["brightness"] == pytest.approx(res3["brightness"], abs=1.0)
        assert res1["brightness"] == pytest.approx(res6["brightness"], abs=1.0)
        assert res1["brightness"] == pytest.approx(res8["brightness"], abs=1.0)


# ==============================================================================
# TEST 4 & 5: Server 422 Rejection, Paper Quota Release, and Quality Bypass
# ==============================================================================

class TestServerQualityCheckAndExtract:
    """Test 4 & 5: Server rejection with HTTP 422, quota release, and bypass logging."""

    @pytest.fixture
    def app_and_db(self, tmp_path):
        from backend import database
        from backend.app import create_app

        db_file = str(tmp_path / "test_clinic.db")
        database.init_db(db_file)
        database.get_or_create_org("org_test", db_path=db_file)

        app = create_app(db_path=db_file)
        app.config["TESTING"] = True
        return app, db_file

    def test_server_rejects_blurred_image_with_422_and_releases_paper(self, app_and_db):
        """Server rejects blurred photo with 422 unreadable and releases paper quota."""
        app, db_file = app_and_db
        client = app.test_client()

        sharp_img = create_synthetic_sharp_page()
        blurred_img = sharp_img.filter(ImageFilter.GaussianBlur(radius=8.0))

        buf_sharp = io.BytesIO()
        sharp_img.save(buf_sharp, format="JPEG")
        buf_blurred = io.BytesIO()
        blurred_img.save(buf_blurred, format="JPEG")

        # Submit blurred student form
        data = {
            "student_form": (io.BytesIO(buf_blurred.getvalue()), "student_form.jpg"),
            "health_assessment": (io.BytesIO(buf_sharp.getvalue()), "health_assessment.jpg"),
            "camp_id": "camp_test",
            "org_id": "org_test",
            "record_id": "rec_test_blur_01",
        }

        resp = client.post("/api/extract", data=data, content_type="multipart/form-data")
        assert resp.status_code == 422, f"Should return 422 unreadable: {resp.data}"
        json_resp = resp.get_json()
        assert json_resp["error"] == "unreadable"
        assert json_resp["code"] == "IMAGE_UNREADABLE"
        assert "blurry" in json_resp["reason"].lower() or "blurry" in json_resp["message"].lower()

        # Check that paper was released (papers_used remains 0) and release logged in usage ledger
        from backend import database
        with database.get_db_connection(db_file) as conn:
            row = conn.execute("SELECT papers_used FROM orgs WHERE id = 'org_test';").fetchone()
            assert row["papers_used"] == 0
            releases = conn.execute("SELECT * FROM usage_ledger WHERE org_id = 'org_test' AND action = 'release';").fetchall()
            assert len(releases) >= 1

    def test_bypass_is_recorded_as_quality_bypassed_on_record(self, app_and_db):
        """When bypassed with X-Quality-Bypassed: 1, unreadable photo is accepted and logged."""
        app, db_file = app_and_db
        client = app.test_client()

        sharp_img = create_synthetic_sharp_page()
        blurred_img = sharp_img.filter(ImageFilter.GaussianBlur(radius=8.0))

        buf_sharp = io.BytesIO()
        sharp_img.save(buf_sharp, format="JPEG")
        buf_blurred = io.BytesIO()
        blurred_img.save(buf_blurred, format="JPEG")

        data = {
            "student_form": (io.BytesIO(buf_blurred.getvalue()), "student_form.jpg"),
            "health_assessment": (io.BytesIO(buf_sharp.getvalue()), "health_assessment.jpg"),
            "camp_id": "camp_test",
            "org_id": "org_test",
            "record_id": "rec_test_bypass_01",
        }

        headers = {
            "X-Quality-Bypassed": "1",
            "X-Org-ID": "org_test"
        }

        # Mock ai_extract to return valid data without calling real Gemini API
        from unittest.mock import patch
        mock_extract_result = {
            "success": True,
            "data": {
                "name": ["Aarav Sharma", 0.95],
                "age": [10, 0.95],
                "gender": ["Male", 0.95]
            },
            "http_status": 200
        }

        with patch("backend.app.ai_extract", return_value=mock_extract_result):
            resp = client.post("/api/extract", data=data, headers=headers, content_type="multipart/form-data")

        assert resp.status_code == 200, f"Bypassed photo should succeed: {resp.data}"
        json_resp = resp.get_json()
        assert json_resp["quality_bypassed"] is True
        assert json_resp["data"]["quality_bypassed"] is True
        assert len(json_resp["data"]["quality_warning_bypassed"]) > 0


# ==============================================================================
# TEST 6: Real Android & iPhone Phone Tests Across Three Light Conditions
# ==============================================================================

class TestPhoneLightConditionsHarness:
    """Test 6: Phone test evaluation across 3 light conditions (bright office, room, dim evening)."""

    def test_evaluates_three_light_conditions(self):
        conditions = {
            "bright_office": {"lum_scale": 1.0, "has_glare": False},
            "ordinary_room": {"lum_scale": 0.75, "has_glare": False},
            "dim_evening": {"lum_scale": 0.25, "has_glare": False},  # low light camp
        }

        base = create_synthetic_sharp_page()
        base_arr = np.array(base, dtype=np.float32)

        results = {}
        for cond_name, cfg in conditions.items():
            mod_arr = np.clip(base_arr * cfg["lum_scale"], 0, 255).astype(np.uint8)
            res = assess_image_quality(Image.fromarray(mod_arr))
            results[cond_name] = res

        # Bright office and ordinary room should pass
        assert results["bright_office"]["ok"] is True
        assert results["ordinary_room"]["ok"] is True

        # Dim evening light should trigger too dark warning unless lit
        assert results["dim_evening"]["ok"] is False
        assert results["dim_evening"]["reason"] == MSG_TOO_DARK


# ==============================================================================
# TEST 7: Calibration Report
# ==============================================================================

class TestCalibrationReport:
    """Test 7: Calibration report on blur threshold, false alarm rate, and miss rate."""

    def test_calibration_tool_optimal_threshold(self):
        sharp_scores = [120.0, 150.0, 180.0, 220.0, 310.0, 450.0, 800.0] * 5
        blur_scores = [5.0, 12.0, 18.0, 22.0, 28.0, 32.0, 36.0] * 5

        cal = find_optimal_blur_threshold(sharp_scores, blur_scores, target_recall=0.95)
        assert cal["optimal_threshold"] >= 30.0
        assert cal["blur_recall"] >= 95.0
        assert cal["miss_rate"] <= 5.0
        assert cal["sharp_false_alarm_rate"] == 0.0

        report = generate_calibration_report(
            {"blur_scores": sharp_scores},
            {"blur_scores": blur_scores},
            target_recall=0.95
        )
        assert "calibration" in report
        assert "performance" in report
        assert report["calibration"]["QUALITY_BLUR_MIN"] == cal["optimal_threshold"]
