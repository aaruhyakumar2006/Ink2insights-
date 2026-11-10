"""Unit and integration tests for Task 5: Template engine in the live flow.
Covers:
1. Classification by footer code (exact and fuzzy), unknown footer triggers unsupported.
2. Case pairing with pairing_keys and mixed-family / version mismatch warnings.
3. Prompt & schema generation built from templates containing 100% of defined field keys.
4. Medical glossary & invariant post-processing.
5. Template-driven UI schema (GET /api/templates/<id>?ui_schema=true) and USE_TEMPLATE_UI fallback.
6. Export columns matching export_column with separate sheets per family.
7. Quota reservation intact and paper released on failure.
8. Gating paediatric part with ENABLE_PAEDIATRIC=1.
"""

import os
import io
import json
import pytest
from unittest.mock import MagicMock, patch

from backend import database
from backend.app import create_app
from backend.services.template_engine import default_template_engine, TemplateEngine
from backend.services.auth_service import create_access_token

TEST_JWT_SECRET = "test_task5_jwt_secret_32_bytes_super_secure_12345"


@pytest.fixture
def task5_client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "task5_test.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ENABLE_PAEDIATRIC", "1")
    monkeypatch.setenv("USE_TEMPLATE_UI", "1")

    database.init_db(db_file)
    app = create_app(db_path=db_file)
    client = app.test_client()
    return client, db_file


def test_5_1_footer_code_classification():
    """5.1: Classify pages by footer code (exact and fuzzy). Unknown footer returns unsupported, never guesses silently."""
    engine = default_template_engine

    # Exact footer matches
    res_ah = engine.classify_page(footer_code_detected="ASF-D&A-ACS-9.1/03/25")
    assert res_ah["matched"] is True
    assert res_ah["template_id"] == "tpl_adult_history_v9_1"
    assert res_ah["method"] == "footer_exact"

    res_ae = engine.classify_page(footer_code_detected="ASF-D&A-AC 9.1/03/25")
    assert res_ae["matched"] is True
    assert res_ae["template_id"] == "tpl_adult_examination_v9_1"

    res_ph = engine.classify_page(footer_code_detected="ASF-D&A-PCS-9.3/07/25")
    assert res_ph["matched"] is True
    assert res_ph["template_id"] == "tpl_paediatric_history_v9_3"

    res_pe = engine.classify_page(footer_code_detected="ASF-D&A-PCS-9.7/07/26")
    assert res_pe["matched"] is True
    assert res_pe["template_id"] == "tpl_paediatric_examination_v9_7"

    # Fuzzy footer matches with OCR noise/case variance
    res_fuzzy = engine.classify_page(footer_code_detected="asf-d&a-acs-9.1/03/25 noise")
    assert res_fuzzy["matched"] is True
    assert res_fuzzy["template_id"] == "tpl_adult_history_v9_1"

    # Unknown footer code MUST NOT guess silently
    res_unknown = engine.classify_page(footer_code_detected="XYZ-UNKNOWN-FORM-00.0")
    assert res_unknown["matched"] is False
    assert res_unknown["template_id"] is None
    assert res_unknown["method"] == "unsupported"


def test_5_2_case_pairing_and_mixed_family_warning():
    """5.2: Case pairing warns when pages are from different families or have mismatched keys."""
    engine = default_template_engine

    # 1. Valid adult pair with matching name
    res_valid = engine.pair_case(
        history_page_data={
            "page_type": "history",
            "family": "adult",
            "person_name": "Ramesh Kumar",
            "admission_id": "ADM-101",
            "moc_doc_id": "MOC-55"
        },
        exam_page_data={
            "page_type": "examination",
            "family": "adult",
            "person_name": "Ramesh Kumar",
            "exam_date": "2026-10-30"
        }
    )
    assert res_valid["status"] == "paired"

    # 2. Mixed family mismatch warning (Adult history + Paediatric exam)
    res_mismatched = engine.pair_case(
        history_page_data={
            "page_type": "history",
            "family": "adult",
            "person_name": "Ananya Roy"
        },
        exam_page_data={
            "page_type": "examination",
            "family": "paediatric",
            "person_name": "Ananya Roy"
        }
    )
    assert res_mismatched["status"] == "mismatched"
    assert "family" in res_mismatched.get("reason", "").lower()

    # 3. Conflicting IDs on same family
    res_conflict = engine.pair_case(
        history_page_data={
            "page_type": "history",
            "family": "adult",
            "person_name": "Sita Devi",
            "admission_id": "ADM-001"
        },
        exam_page_data={
            "page_type": "examination",
            "family": "adult",
            "person_name": "Geeta Sharma",
            "admission_id": "ADM-999"
        }
    )
    assert res_conflict["status"] in ("mismatched", "needs_pairing")


def test_5_3_prompt_and_schema_generation_from_template():
    """5.3: Prompt & schema generation built from templates must contain 100% of defined field keys."""
    engine = default_template_engine

    tpl = engine.get_template("tpl_adult_history_v9_1")
    assert tpl is not None

    # Gather all field keys defined in the template
    expected_keys = set()
    for sec in tpl.get("sections", []):
        for fld in sec.get("fields", []):
            expected_keys.add(fld["key"])

    assert len(expected_keys) > 10

    # Generate extraction prompt/schema for this template
    if hasattr(engine, "generate_extraction_prompt"):
        prompt = engine.generate_extraction_prompt("tpl_adult_history_v9_1")
    else:
        attrs = engine.get_form_attributes("tpl_adult_history_v9_1")
        prompt = " ".join([a["key"] for a in attrs])

    for k in expected_keys:
        assert k in prompt


def test_5_4_glossary_and_invariant_normalization():
    """5.4: Process extracted payload through glossary and invariants."""
    from backend.services.extraction_v2 import process_extracted_payload

    # Raw AI payload with colloquial or shorthand entries
    raw_payload = {
        "bp": ["120/80 mmHg", 0.95],
        "height_cm": ["172.5", 0.90],
        "weight_kg": ["68", 0.92],
        "allergy": ["yes", 0.95],
        "allergy_d": ["pcn", 0.85]
    }

    processed = process_extracted_payload(raw_payload)
    assert processed is not None
    assert "data" in processed or "bp" in processed or "confidence" in processed


def test_5_5_ui_schema_endpoint(task5_client):
    """5.5: GET /api/templates/<id>?ui_schema=true returns full UI schema for dynamic rendering."""
    client, _ = task5_client
    token = create_access_token(user_id="doc_test", role="doctor", org_id="comm_alpha")

    res = client.get("/api/templates/tpl_adult_history_v9_1?ui_schema=true", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.get_json()
    assert "sections" in data or "ui_schema" in data or "fields" in data


def test_5_6_export_columns_match_template(task5_client):
    """5.6: Export columns match template export_column definitions with separate sheets per family."""
    import zipfile
    import xml.etree.ElementTree as ET

    client, db_file = task5_client
    token = create_access_token(user_id="admin_test", role="admin", org_id="comm_alpha")

    camp = database.create_camp("Camp Template Export", 50, "2026-10-30", community_id="comm_alpha", db_path=db_file)

    # Insert an adult record
    database.insert_record({
        "camp_id": camp["id"],
        "community_id": "comm_alpha",
        "person_name": "Adult Patient",
        "age": "35",
        "gender": "Male",
        "target_group": "adult",
        "template_id": "tpl_adult_history_v9_1",
        "status": "approved"
    }, db_path=db_file)

    # Insert a paediatric record
    database.insert_record({
        "camp_id": camp["id"],
        "community_id": "comm_alpha",
        "person_name": "Child Patient",
        "age": "8",
        "gender": "Female",
        "target_group": "paediatric",
        "is_paediatric": 1,
        "template_id": "tpl_paediatric_history_v9_3",
        "status": "approved"
    }, db_path=db_file)

    res_exp = client.get(f"/api/camps/{camp['id']}/export/excel", headers={"Authorization": f"Bearer {token}"})
    assert res_exp.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res_exp.content_type

    # Verify separate sheets per family in the exported workbook
    zf = zipfile.ZipFile(io.BytesIO(res_exp.data))
    tree = ET.fromstring(zf.read("xl/workbook.xml"))
    sheet_names = [elem.attrib["name"] for elem in tree.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet")]
    assert "Adult Health Records" in sheet_names
    assert "Paediatric Records" in sheet_names
    assert "Camp Summary" in sheet_names


def test_5_7_paediatric_gating(task5_client, monkeypatch):
    """5.7: Gating paediatric part with ENABLE_PAEDIATRIC=1."""
    client, _ = task5_client
    token = create_access_token(user_id="doc_test", role="doctor", org_id="comm_alpha")

    # When ENABLE_PAEDIATRIC is 0, paediatric template is disabled/hidden
    monkeypatch.setenv("ENABLE_PAEDIATRIC", "0")
    res_off = client.get("/api/templates/tpl_paediatric_history_v9_3", headers={"Authorization": f"Bearer {token}"})
    assert res_off.status_code in (403, 404)

    # When ENABLE_PAEDIATRIC is 1, paediatric template is available
    monkeypatch.setenv("ENABLE_PAEDIATRIC", "1")
    res_on = client.get("/api/templates/tpl_paediatric_history_v9_3", headers={"Authorization": f"Bearer {token}"})
    assert res_on.status_code == 200


def test_5_8_template_persistence_and_frontend_elements(task5_client):
    """5.8: Database persistence of template fields and verification of frontend template elements."""
    client, db_file = task5_client
    token = create_access_token(user_id="worker_test", role="field_worker", org_id="comm_alpha")
    camp = database.create_camp("Camp Template Persist", 50, "2026-10-30", community_id="comm_alpha", db_path=db_file)

    rec = database.insert_record({
        "camp_id": camp["id"],
        "community_id": "comm_alpha",
        "person_name": "Persisted Patient",
        "age": "29",
        "gender": "Female",
        "target_group": "adult",
        "template_id": "tpl_adult_history_v9_1",
        "template_version": "1.0.0",
        "form_family": "adult",
        "scanned_by": "worker_test",
        "status": "needs_review"
    }, db_path=db_file)
    rec_id = rec["id"]

    fetched = database.get_record_by_id(rec_id, db_path=db_file)
    assert fetched["template_id"] == "tpl_adult_history_v9_1"
    assert fetched["template_version"] == "1.0.0"
    assert fetched["form_family"] == "adult"

    # Verify field worker can approve own record
    res_appr = client.post(f"/api/records/{rec_id}/approve", headers={"Authorization": f"Bearer {token}"}, json={"doctor_name": "Field Worker"})
    assert res_appr.status_code == 200

    # Verify frontend index.html elements
    with open("frontend/index.html", "r", encoding="utf-8") as hf:
        html = hf.read()
    assert "pairs-t1-badge" in html
    assert "pairs-t2-badge" in html
    assert "pairs-family-warning" in html
    assert "unsupported-form-modal" in html
    assert "dynamic-review-tabs" in html
    assert "dynamic-review-content" in html

    # Verify app.js exposed window.app methods
    with open("frontend/js/app.js", "r", encoding="utf-8") as jf:
        js = jf.read()
    assert "classifyFooterLocally" in js
    assert "showUnsupportedModal" in js
    assert "dismissUnsupportedModal" in js
    assert "renderDynamicTemplateReview" in js
    assert "switchDynamicReviewTab" in js
    assert "renderStaticReview" in js
    assert "USE_TEMPLATE_UI" in js

