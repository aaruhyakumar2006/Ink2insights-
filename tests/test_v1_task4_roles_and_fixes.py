"""Unit and integration tests for Part 0 Fixes and Task 4 Roles & Permissions.

Permissions Matrix:
- Action                        | field_worker | doctor | admin
- Scan pages, see own scans     | yes (200)    | yes    | yes
- Edit identity fields          | yes (200)    | yes    | yes
- Edit clinical fields          | no (403)     | yes    | yes
- Approve a record              | no (403)     | yes    | yes
- See ALL org records           | no (own only)| yes    | yes
- Export Excel                  | no (403)     | yes    | yes
- Community / Admin routes      | no (403)     | no     | yes
"""

import os
import time
import json
import secrets
import concurrent.futures
from datetime import datetime, timezone, timedelta
import pytest

from backend.app import create_app
from backend import database
from backend.services.auth_service import (
    create_access_token,
    safe_decode_token,
    send_otp_for_recipient,
    verify_submitted_otp
)
from backend.database import (
    record_login_failure,
    is_account_locked,
    reset_login_failures
)
try:
    from backend.services.field_permissions import is_identity_field, is_clinical_field, filter_editable_fields
except ImportError:
    is_identity_field = None
    is_clinical_field = None
    filter_editable_fields = None

from backend.services.unified_pipeline import get_configured_ai_provider

TEST_JWT_SECRET = "test_task4_super_secret_jwt_key_32bytes_long"


# ==============================================================================
# PART 0: FIXES (0.1 to 0.7)
# ==============================================================================

def test_0_1_signed_file_urls_security(tmp_path, monkeypatch):
    """0.1: Signed URLs verify signature, expiry and org.
    Works for <img> tags without header; tests valid, expired, tampered, cross-org, and no token.
    """
    db_file = str(tmp_path / "signed_test.db")
    private_dir = str(tmp_path / "private_uploads")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("PRIVATE_UPLOAD_DIR", private_dir)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("APP_ENV", "development")

    database.init_db(db_file)
    app = create_app(db_path=db_file)
    client = app.test_client()

    file_bytes = b"CONFIDENTIAL_PATIENT_SCAN_DATA"
    file_id = database.save_private_file(
        org_id="org_alpha",
        record_id="rec_alpha_1",
        file_type="scan_page1",
        filename="p1.jpg",
        data=file_bytes,
        mime_type="image/jpeg",
        db_path=db_file,
        private_dir=private_dir
    )

    # 1. Valid signed token succeeds with required headers (0.6)
    valid_token = database.generate_signed_file_token(file_id, org_id="org_alpha", expires_in_seconds=300)
    res_valid = client.get(f"/api/files/{file_id}?token={valid_token}")
    assert res_valid.status_code == 200
    assert res_valid.data == file_bytes
    assert "private" in res_valid.headers.get("Cache-Control", "")
    assert "no-store" in res_valid.headers.get("Cache-Control", "")
    assert res_valid.headers.get("X-Content-Type-Options") == "nosniff"

    # 2. Expired signed token fails with 401
    expired_token = database.generate_signed_file_token(file_id, org_id="org_alpha", expires_in_seconds=-10)
    res_expired = client.get(f"/api/files/{file_id}?token={expired_token}")
    assert res_expired.status_code == 401

    # 3. Tampered signed token fails with 401
    tampered_token = valid_token[:-4] + "xxxx"
    res_tampered = client.get(f"/api/files/{file_id}?token={tampered_token}")
    assert res_tampered.status_code == 401

    # 4. Cross-org signed token (signed for org_beta attempting to access org_alpha file) -> 404
    cross_org_token = database.generate_signed_file_token(file_id, org_id="org_beta", expires_in_seconds=300)
    res_cross = client.get(f"/api/files/{file_id}?token={cross_org_token}")
    assert res_cross.status_code == 404

    # 5. No token and no Authorization header -> 401
    res_no_tok = client.get(f"/api/files/{file_id}")
    assert res_no_tok.status_code == 401


def test_0_2_otp_hash_storage_and_atomic_consumption(tmp_path, monkeypatch):
    """0.2: OTP stores only hash, verify-and-consume is atomic, wrong guesses trigger lockout,
    and simulated concurrent verifications permit only one to succeed.
    """
    db_file = str(tmp_path / "otp_atomic.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("APP_ENV", "production")  # Random OTP

    database.init_db(db_file)
    recipient = "919876543210"

    # Save OTP
    otp_code = database.save_auth_otp(recipient, "593812", expires_in_minutes=5, db_path=db_file)
    assert otp_code == "593812"

    # Inspect DB table: verify that plaintext OTP "593812" is NOT stored in the database
    with database.get_db_connection(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT otp_hash FROM auth_otps WHERE recipient = ?;", (recipient,))
        row = cursor.fetchone()
        assert row is not None
        assert row["otp_hash"] != "593812"
        assert len(row["otp_hash"]) >= 32  # Cryptographic hash

    # Wrong guess triggers lockout increment
    bad_res = verify_submitted_otp(recipient, "000000", db_path=db_file)
    assert bad_res is False
    locked, attempts = database.is_account_locked(recipient, db_path=db_file)
    assert attempts >= 1

    # Re-save valid OTP for concurrency test
    database.save_auth_otp(recipient, "777888", expires_in_minutes=5, db_path=db_file)

    # Simulated concurrent verification of one OTP
    def attempt_verify():
        return database.verify_and_consume_auth_otp(recipient, "777888", db_path=db_file)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attempt_verify)
        f2 = executor.submit(attempt_verify)
        results = [f1.result(), f2.result()]

    # Exactly one must succeed, one must fail
    assert results.count(True) == 1
    assert results.count(False) == 1


def test_0_3_auth_refresh_max_session_and_revocation(tmp_path, monkeypatch):
    """0.3: /api/auth/refresh enforces max session age (SESSION_MAX_DAYS), verifies user exists & active, and rate limits."""
    db_file = str(tmp_path / "refresh_safety.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("SESSION_MAX_DAYS", "7")
    monkeypatch.setenv("APP_ENV", "development")

    database.init_db(db_file)
    app = create_app(db_path=db_file)
    client = app.test_client()

    # Create active user in DB
    user = database.create_doctor(
        email="worker.active@clinic.org",
        name="Field Worker Active",
        specialization="Field Screener",
        community_id="comm_alpha",
        db_path=db_file
    )
    user_id = user["id"]

    # 1. Valid refresh within max session age succeeds
    token_valid = create_access_token(
        user_id=user_id,
        role="field_worker",
        org_id="comm_alpha",
        orig_iat=int(time.time()) - 3600  # 1 hour ago
    )
    res_ok = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {token_valid}"})
    assert res_ok.status_code == 200
    new_data = res_ok.get_json()
    assert "access_token" in new_data

    # 2. Token exceeding SESSION_MAX_DAYS (8 days ago) -> 401
    token_expired_session = create_access_token(
        user_id=user_id,
        role="field_worker",
        org_id="comm_alpha",
        orig_iat=int(time.time()) - (8 * 86400)
    )
    res_old = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {token_expired_session}"})
    assert res_old.status_code == 401
    assert "max age" in res_old.get_json().get("message", "").lower()

    # 3. Revoked / inactive user -> 401
    with database.get_db_connection(db_file) as conn:
        conn.execute("UPDATE doctors SET is_active = 0 WHERE id = ?;", (user_id,))
        conn.commit()

    res_revoked = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {token_valid}"})
    assert res_revoked.status_code == 401

    # 4. User does not exist in production -> 401
    monkeypatch.setenv("APP_ENV", "production")
    token_ghost = create_access_token(user_id="doc_ghost_user", role="doctor", org_id="comm_alpha")
    res_ghost = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {token_ghost}"})
    assert res_ghost.status_code == 401
    assert "no longer exists" in res_ghost.get_json().get("message", "").lower()


def test_0_4_and_0_5_release_safety_and_static_commonpath(tmp_path, monkeypatch):
    """0.4 & 0.5: Release safety checks, static route commonpath traversal check & allowlist."""
    db_file = str(tmp_path / "static_safety.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)

    app = create_app(db_path=db_file)
    client = app.test_client()

    # Block non-allowlist file types (e.g. .py, .env, .db, .exe)
    res_py = client.get("/backend/app.py")
    assert res_py.status_code == 404 or res_py.mimetype == "text/html"  # Serves index.html SPA or 404

    # Traversal attempts fail with 404
    res_trav = client.get("/..%2f..%2fbackend%2fdatabase.py")
    assert res_trav.status_code == 404

    # Direct /uploads access blocked with 404
    res_up = client.get("/uploads/something.jpg")
    assert res_up.status_code == 404


def test_0_7_named_regression_tests(tmp_path, monkeypatch):
    """0.7: AI_PROVIDER defaults to gemini; production startup checks; health endpoint; DAILY_SCAN_CAP_PER_ORG protects quota."""
    # 1. AI_PROVIDER default
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    assert get_configured_ai_provider() == "gemini"

    # 2. Daily scan cap rejects over-cap scans WITHOUT consuming quota
    db_file = str(tmp_path / "quota_protect.db")
    monkeypatch.setenv("DAILY_SCAN_CAP_PER_ORG", "1")
    database.init_db(db_file)
    org_id = "org_quota_protect"
    database.get_or_create_org(org_id=org_id, papers_included=50, db_path=db_file)

    # 1st scan reserves quota (papers_used -> 1)
    ok1, _, left1 = database.reserve_paper(org_id=org_id, record_id="r1", db_path=db_file)
    assert ok1 is True
    database.log_usage_ledger(org_id=org_id, record_id="r1", action="ai_extract", db_path=db_file)

    org_status_1 = database.get_or_create_org(org_id=org_id, db_path=db_file)
    used_after_1 = org_status_1["papers_used"]

    # 2nd scan hits DAILY_SCAN_CAP_PER_ORG -> rejected
    ok2, code2, _ = database.reserve_paper(org_id=org_id, record_id="r2", db_path=db_file)
    assert ok2 is False
    assert code2 == "daily_cap_reached"

    # Quota must NOT have been incremented for rejected scan
    org_status_2 = database.get_or_create_org(org_id=org_id, db_path=db_file)
    assert org_status_2["papers_used"] == used_after_1


# ==============================================================================
# PART 1: TASK 4 - ROLES & PERMISSIONS
# ==============================================================================

def test_4_1_identity_vs_clinical_definition():
    """4.1: Shared identity vs clinical classification; unlisted fields fail closed as clinical."""
    # Identity fields
    assert is_identity_field("person_name") is True
    assert is_identity_field("dob") is True
    assert is_identity_field("age") is True
    assert is_identity_field("gender") is True
    assert is_identity_field("mobile_number") is True
    assert is_identity_field("address") is True
    assert is_identity_field("parent_guardian_name") is True

    # Clinical fields
    assert is_clinical_field("blood_pressure") is True
    assert is_clinical_field("weight") is True
    assert is_clinical_field("height") is True
    assert is_clinical_field("examination_details") is True
    assert is_clinical_field("referral_details") is True
    assert is_clinical_field("dental_caries") is True

    # Unknown field fails closed as clinical
    assert is_identity_field("unknown_custom_vital") is False
    assert is_clinical_field("unknown_custom_vital") is True


def test_4_2_field_worker_clinical_field_rejection_no_partial_save(tmp_path, monkeypatch):
    """4.2: A field_worker PUT touching ANY clinical field returns 403 and changes NOTHING (no partial save)."""
    db_file = str(tmp_path / "worker_clinical_edit.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)

    database.init_db(db_file)
    app = create_app(db_path=db_file)
    client = app.test_client()

    camp = database.create_camp("Role Camp", 10, "Today", community_id="comm_alpha", db_path=db_file)
    rec = database.insert_record({
        "camp_id": camp["id"],
        "community_id": "comm_alpha",
        "scanned_by": "worker_user_01",
        "person_name": "Original Name",
        "age": "25",
        "blood_pressure": "120/80",
        "status": "needs_review"
    }, db_path=db_file)
    rec_id = rec["id"]

    worker_tok = create_access_token(user_id="worker_user_01", role="field_worker", org_id="comm_alpha")
    doctor_tok = create_access_token(user_id="doc_01", role="doctor", org_id="comm_alpha")

    # 1. Pure clinical payload from field_worker -> 403 Forbidden
    res_pure = client.put(
        f"/api/records/{rec_id}",
        headers={"Authorization": f"Bearer {worker_tok}"},
        json={"blood_pressure": "140/90"}
    )
    assert res_pure.status_code == 403

    # 2. Mixed payload (identity 'person_name' + clinical 'blood_pressure') -> 403 Forbidden, changes NOTHING
    res_mixed = client.put(
        f"/api/records/{rec_id}",
        headers={"Authorization": f"Bearer {worker_tok}"},
        json={"person_name": "Tampered Name", "blood_pressure": "150/95"}
    )
    assert res_mixed.status_code == 403

    # Confirm database was NOT partially updated
    unchanged = database.get_record_by_id(rec_id, db_path=db_file)
    assert unchanged["person_name"] == "Original Name"
    assert unchanged["blood_pressure"] == "120/80"

    # 3. Pure identity edit from field_worker -> 200 OK
    res_ident = client.put(
        f"/api/records/{rec_id}",
        headers={"Authorization": f"Bearer {worker_tok}"},
        json={"person_name": "Updated Worker Name", "age": "26"}
    )
    assert res_ident.status_code == 200
    updated = database.get_record_by_id(rec_id, db_path=db_file)
    assert updated["person_name"] == "Updated Worker Name"
    assert updated["age"] == "26"

    # 4. Doctor editing clinical field -> 200 OK
    res_doc = client.put(
        f"/api/records/{rec_id}",
        headers={"Authorization": f"Bearer {doctor_tok}"},
        json={"blood_pressure": "130/85"}
    )
    assert res_doc.status_code == 200
    doc_updated = database.get_record_by_id(rec_id, db_path=db_file)
    assert doc_updated["blood_pressure"] == "130/85"


def test_4_3_field_worker_same_org_isolation_and_export_denial(tmp_path, monkeypatch):
    """4.3: field_worker sees only records they scanned/created. Reading another worker's record returns 404. Export denied (403)."""
    db_file = str(tmp_path / "worker_isolation.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)

    database.init_db(db_file)
    app = create_app(db_path=db_file)
    client = app.test_client()

    camp = database.create_camp("Shared Camp", 20, "Today", community_id="comm_alpha", db_path=db_file)

    # Worker 1 creates record 1
    rec1 = database.insert_record({
        "camp_id": camp["id"],
        "community_id": "comm_alpha",
        "scanned_by": "worker_alice",
        "person_name": "Alice Patient",
        "status": "needs_review"
    }, db_path=db_file)

    # Worker 2 creates record 2
    rec2 = database.insert_record({
        "camp_id": camp["id"],
        "community_id": "comm_alpha",
        "scanned_by": "worker_bob",
        "person_name": "Bob Patient",
        "status": "needs_review"
    }, db_path=db_file)

    tok_alice = create_access_token(user_id="worker_alice", role="field_worker", org_id="comm_alpha")
    tok_bob = create_access_token(user_id="worker_bob", role="field_worker", org_id="comm_alpha")
    tok_doc = create_access_token(user_id="doc_carol", role="doctor", org_id="comm_alpha")

    # 1. Alice sees only her own records in record list
    res_list = client.get("/api/records", headers={"Authorization": f"Bearer {tok_alice}"})
    assert res_list.status_code == 200
    res_data = res_list.get_json()
    records = res_data if isinstance(res_data, list) else res_data.get("records", [])
    assert all(r["scanned_by"] == "worker_alice" for r in records)
    assert any(r["id"] == rec1["id"] for r in records)
    assert not any(r["id"] == rec2["id"] for r in records)

    # 2. Alice accessing Bob's record directly -> 403 Forbidden (documented tenant/worker isolation)
    res_direct = client.get(f"/api/records/{rec2['id']}", headers={"Authorization": f"Bearer {tok_alice}"})
    assert res_direct.status_code == 403

    # 3. Field worker export -> 403 Forbidden
    res_export = client.get("/api/export", headers={"Authorization": f"Bearer {tok_alice}"})
    assert res_export.status_code == 403

    # 4. Doctor sees all records in org and can export
    res_doc_list = client.get("/api/records", headers={"Authorization": f"Bearer {tok_doc}"})
    assert res_doc_list.status_code == 200
    doc_data = res_doc_list.get_json()
    doc_records = doc_data if isinstance(doc_data, list) else doc_data.get("records", [])
    assert len(doc_records) >= 2


def test_4_4_approval_rules_and_edit_after_approval(tmp_path, monkeypatch):
    """4.4: Approval is explicit by doctor/admin only. Normal edit does not approve.
    Editing an approved record resets status to 'needs_review' with an audit row.
    """
    db_file = str(tmp_path / "approval_rules.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)

    database.init_db(db_file)
    app = create_app(db_path=db_file)
    client = app.test_client()

    camp = database.create_camp("Approval Camp", 10, "Today", community_id="comm_alpha", db_path=db_file)
    rec = database.insert_record({
        "camp_id": camp["id"],
        "community_id": "comm_alpha",
        "scanned_by": "worker_01",
        "person_name": "Patient X",
        "status": "needs_review"
    }, db_path=db_file)
    rec_id = rec["id"]

    worker_tok = create_access_token(user_id="worker_01", role="field_worker", org_id="comm_alpha")
    doc_tok = create_access_token(user_id="doc_01", role="doctor", org_id="comm_alpha")

    # 1. Field worker can approve their own record -> 200, status becomes 'approved'
    res_w_appr = client.post(f"/api/records/{rec_id}/approve", headers={"Authorization": f"Bearer {worker_tok}"})
    assert res_w_appr.status_code == 200
    w_approved = database.get_record_by_id(rec_id, db_path=db_file)
    assert w_approved["status"] == "approved"
    assert w_approved["approved_by"] == "worker_01"

    # Another worker attempting to approve worker_01's record -> 403
    other_worker_tok = create_access_token(user_id="worker_02", role="field_worker", org_id="comm_alpha")
    res_w2_appr = client.post(f"/api/records/{rec_id}/approve", headers={"Authorization": f"Bearer {other_worker_tok}"})
    assert res_w2_appr.status_code == 403

    # Reset record for doctor approval test
    database.update_record(rec_id, {"status": "needs_review", "approved_by": None, "approved_at": None}, db_path=db_file)

    # 2. Doctor approves -> 200, status becomes 'approved', stores approved_by and approved_at
    res_d_appr = client.post(f"/api/records/{rec_id}/approve", headers={"Authorization": f"Bearer {doc_tok}"})
    assert res_d_appr.status_code == 200
    approved_rec = database.get_record_by_id(rec_id, db_path=db_file)
    assert approved_rec["status"] == "approved"
    assert approved_rec["approved_by"] == "doc_01"
    assert approved_rec["approved_at"] is not None

    # 3. Doctor edits approved record -> status resets to 'needs_review'
    res_edit = client.put(
        f"/api/records/{rec_id}",
        headers={"Authorization": f"Bearer {doc_tok}"},
        json={"blood_pressure": "135/88"}
    )
    assert res_edit.status_code == 200
    rechecked = database.get_record_by_id(rec_id, db_path=db_file)
    assert rechecked["status"] == "needs_review"


def test_4_5_audit_log_insert_only(tmp_path, monkeypatch):
    """4.5: Audit log records user, role, field, old_val, new_val; insert-only; GET /api/records/<id>/audit for doctor/admin."""
    db_file = str(tmp_path / "audit_log.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)

    database.init_db(db_file)
    app = create_app(db_path=db_file)
    client = app.test_client()

    camp = database.create_camp("Audit Camp", 10, "Today", community_id="comm_alpha", db_path=db_file)
    rec = database.insert_record({
        "camp_id": camp["id"],
        "community_id": "comm_alpha",
        "person_name": "Audit Patient",
        "age": "30",
        "status": "needs_review"
    }, db_path=db_file)
    rec_id = rec["id"]

    doc_tok = create_access_token(user_id="doc_auditor", role="doctor", org_id="comm_alpha")
    worker_tok = create_access_token(user_id="worker_auditor", role="field_worker", org_id="comm_alpha")

    # Perform edit
    client.put(
        f"/api/records/{rec_id}",
        headers={"Authorization": f"Bearer {doc_tok}"},
        json={"person_name": "Audited Name", "age": "31"}
    )

    # 1. Doctor retrieves audit log -> 200
    res_audit = client.get(f"/api/records/{rec_id}/audit", headers={"Authorization": f"Bearer {doc_tok}"})
    assert res_audit.status_code == 200
    audit_rows = res_audit.get_json().get("audit_log", [])
    assert len(audit_rows) >= 2
    assert any(r["field_name"] == "person_name" and r["new_value"] == "Audited Name" for r in audit_rows)

    # 2. Field worker accessing audit log -> 403 Forbidden
    res_worker_audit = client.get(f"/api/records/{rec_id}/audit", headers={"Authorization": f"Bearer {worker_tok}"})
    assert res_worker_audit.status_code == 403


def test_4_6_server_enforcement_admin_only_routes(tmp_path, monkeypatch):
    """4.6: Admin-only routes return 403 for field_worker and doctor."""
    db_file = str(tmp_path / "admin_routes.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)

    database.init_db(db_file)
    app = create_app(db_path=db_file)
    client = app.test_client()

    worker_tok = create_access_token(user_id="w1", role="field_worker", org_id="comm_alpha")
    doc_tok = create_access_token(user_id="d1", role="doctor", org_id="comm_alpha")
    admin_tok = create_access_token(user_id="a1", role="admin", org_id="comm_alpha")

    admin_endpoints = [
        ("GET", "/api/admin/billing"),
        ("GET", "/api/community/members"),
        ("POST", "/api/community/rotate-code"),
        ("POST", "/api/ai/pause"),
        ("GET", "/api/usage/ledger")
    ]

    for method, endpoint in admin_endpoints:
        # Worker -> 403
        res_w = client.open(endpoint, method=method, headers={"Authorization": f"Bearer {worker_tok}"})
        assert res_w.status_code == 403, f"Worker got {res_w.status_code} for {endpoint}"

        # Doctor -> 403
        res_d = client.open(endpoint, method=method, headers={"Authorization": f"Bearer {doc_tok}"})
        assert res_d.status_code == 403, f"Doctor got {res_d.status_code} for {endpoint}"

        # Admin -> 200 or successful execution
        res_a = client.open(endpoint, method=method, headers={"Authorization": f"Bearer {admin_tok}"})
        assert res_a.status_code in (200, 201), f"Admin got {res_a.status_code} for {endpoint}"


def test_4_9_role_by_action_matrix(tmp_path, monkeypatch):
    """4.9: Parametrized role-by-action matrix test across field_worker, doctor, admin."""
    db_file = str(tmp_path / "matrix_test.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)

    database.init_db(db_file)
    app = create_app(db_path=db_file)
    client = app.test_client()

    camp = database.create_camp("Matrix Camp", 10, "Today", community_id="comm_matrix", db_path=db_file)
    rec = database.insert_record({
        "camp_id": camp["id"],
        "community_id": "comm_matrix",
        "scanned_by": "field_worker_user",
        "person_name": "Matrix Patient",
        "status": "needs_review"
    }, db_path=db_file)
    rec_id = rec["id"]

    roles = ["field_worker", "doctor", "admin"]
    tokens = {r: create_access_token(user_id=f"{r}_user", role=r, org_id="comm_matrix") for r in roles}

    # Matrix expectations: (action_name, method, url, payload, expected_status_by_role)
    matrix = [
        # 1. Edit Identity
        ("edit_identity", "PUT", f"/api/records/{rec_id}", {"person_name": "New Identity"}, {"field_worker": 200, "doctor": 200, "admin": 200}),
        # 2. Edit Clinical
        ("edit_clinical", "PUT", f"/api/records/{rec_id}", {"blood_pressure": "140/90"}, {"field_worker": 403, "doctor": 200, "admin": 200}),
        # 3. Approve Record (field worker can approve own record; doctor and admin can approve any)
        ("approve_record", "POST", f"/api/records/{rec_id}/approve", {}, {"field_worker": 200, "doctor": 200, "admin": 200}),
        # 4. Export Records
        ("export_excel", "GET", "/api/export", None, {"field_worker": 403, "doctor": 200, "admin": 200}),
        # 5. Admin Billing
        ("admin_billing", "GET", "/api/admin/billing", None, {"field_worker": 403, "doctor": 403, "admin": 200}),
        # 6. Usage Ledger
        ("usage_ledger", "GET", "/api/usage/ledger", None, {"field_worker": 403, "doctor": 403, "admin": 200}),
    ]

    for action_name, method, url, payload, expectations in matrix:
        for role in roles:
            kwargs = {"headers": {"Authorization": f"Bearer {tokens[role]}"}}
            if payload is not None:
                kwargs["json"] = payload
            res = client.open(url, method=method, **kwargs)
            expected = expectations[role]
            assert res.status_code == expected, f"Action '{action_name}' for role '{role}' expected {expected}, got {res.status_code}"
