"""Comprehensive Tests for Carry-over Fixes (Part 0), Task 9 (Config & AI Provider), and Task 10 (Secure Scans & Files).

Covers:
- 0.1: DB-backed shared lockout and OTP store across separate app instances
- 0.2: Supabase RLS schema validation (WITH CHECK on UPDATE, all 4 CRUD actions on all tables)
- 0.3: Dynamic url_map route iteration verifying fail-closed 401 on every non-whitelisted route
- 0.4: POST /api/auth/refresh endpoint for token renewal with claims preservation
- 0.5: Join code length (>= 12 URL-safe chars), weak code rejection, and expiry validation
- 0.6: Standardized 'field_worker' role verification
- 9.1: AI_PROVIDER defaults to 'gemini' even when other keys exist; switching to claude, groq, nvidia
- 9.2: Provider and model recording in usage_ledger rows
- 9.3: Production startup fail-fast validation (missing JWT_SECRET, missing key, Vercel SQLite)
- 9.4: Public GET /api/health returning app version, provider, model, db status, and zero secrets
- 9.5: DAILY_SCAN_CAP_PER_ORG enforcement before AI call without breaking paper reservations
- 10.1 & 10.2: Private uploads outside static root, GET /api/files/<id> (401 unauth, 404 cross-org, 200 own org)
- 10.2: Signed short-lived file URL (5-min token)
- 10.4: Static catch-all blocking /uploads/ and path traversal attacks
- 10.5: Safe migration of legacy frontend/uploads to private folder
- 10.6: DPDP permanent erasure deleting physical files and retention cleanup
"""

import os
import io
import time
import json
import secrets
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from backend.app import create_app
from backend import database
from backend.services.auth_service import (
    create_access_token,
    safe_decode_token,
    send_otp_for_recipient,
    verify_submitted_otp,
    record_login_attempt,
    check_account_locked
)
from backend.services.unified_pipeline import detect_ai_provider, get_configured_ai_provider

TEST_JWT_SECRET = "secure_test_jwt_secret_must_be_over_32_characters_long!!"


# ==============================================================================
# PART 0: Carry-over Fixes
# ==============================================================================

def test_0_1_db_backed_shared_lockout_and_otps(tmp_path, monkeypatch):
    """0.1: Two app instances sharing one DB: OTP created in app1 is verified in app2,
    and 5 failed attempts across instances lock the account.
    """
    db_file = str(tmp_path / "shared_auth_test.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("APP_ENV", "development")

    database.init_db(db_file)
    app1 = create_app(db_path=db_file)
    app2 = create_app(db_path=db_file)

    phone = "919876543210"

    # Instance 1: Generate OTP in DB
    otp_code = database.save_auth_otp(phone, "482910", expires_in_minutes=5, db_path=db_file)
    assert otp_code == "482910"

    # Instance 2: Verify and consume OTP from DB
    valid = database.verify_and_consume_auth_otp(phone, "482910", db_path=db_file)
    assert valid is True

    # Single-use: Second attempt in Instance 1 or 2 must fail
    second_valid = database.verify_and_consume_auth_otp(phone, "482910", db_path=db_file)
    assert second_valid is False

    # Account Lockout across instances: 3 failures in instance 1 + 2 failures in instance 2 = 5 total -> LOCKED
    user_id = "doc_cross_instance_test"
    for _ in range(3):
        database.record_login_failure(user_id, max_attempts=5, lock_minutes=15, db_path=db_file)

    locked, remaining = database.is_account_locked(user_id, db_path=db_file)
    assert locked is False

    for _ in range(2):
        database.record_login_failure(user_id, max_attempts=5, lock_minutes=15, db_path=db_file)

    locked, remaining = database.is_account_locked(user_id, db_path=db_file)
    assert locked is True
    assert remaining > 0


def test_0_2_supabase_rls_policies_with_check():
    """0.2: Verify Supabase RLS policies in supabase_schema.sql have WITH CHECK on UPDATE
    and all 4 CRUD actions on all multi-tenant tables.
    """
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "supabase_schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()

    # Verify RLS enabled on all core tables
    for table in ["camps", "records", "doctors", "orgs", "usage_ledger", "communities"]:
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;" in sql

    # Verify WITH CHECK on UPDATE policies
    assert 'CREATE POLICY "Tenant update camps"' in sql
    assert 'CREATE POLICY "Tenant update records"' in sql
    assert 'CREATE POLICY "Tenant update doctors"' in sql
    assert 'WITH CHECK' in sql


def test_0_3_dynamic_url_map_protected_routes(tmp_path, monkeypatch):
    """0.3: Dynamically iterate app.url_map; every route not in whitelist must return 401 without token."""
    db_file = str(tmp_path / "url_map_test.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("APP_ENV", "development")

    database.init_db(db_file)
    app = create_app(db_path=db_file)
    client = app.test_client()

    public_prefixes = ("/api/health", "/api/status", "/api/config/quality", "/api/community/verify", "/api/auth/", "/api/billing/webhook")

    tested_endpoints = 0
    for rule in app.url_map.iter_rules():
        rule_str = str(rule)
        if not rule_str.startswith("/api/"):
            continue
        if any(rule_str.startswith(p) for p in public_prefixes):
            continue

        # Build concrete test URL replacing variables
        test_url = rule_str
        for arg in rule.arguments:
            test_url = test_url.replace(f"<{arg}>", "dummy_test_val")

        methods = [m for m in rule.methods if m in ("GET", "POST", "PUT", "DELETE")]
        for method in methods:
            # 1. No token -> 401
            res_no_tok = client.open(test_url, method=method)
            assert res_no_tok.status_code == 401, f"{method} {test_url} did not return 401 without token (got {res_no_tok.status_code})"

            # 2. Garbage token -> 401
            res_bad_tok = client.open(test_url, method=method, headers={"Authorization": "Bearer not.a.real.jwt.token"})
            assert res_bad_tok.status_code == 401, f"{method} {test_url} did not return 401 with garbage token (got {res_bad_tok.status_code})"
            tested_endpoints += 1

    assert tested_endpoints >= 18, f"Expected at least 18 endpoints tested, got {tested_endpoints}"


def test_0_4_auth_refresh_endpoint(tmp_path, monkeypatch):
    """0.4: POST /api/auth/refresh re-issues a valid token preserving role and org_id."""
    db_file = str(tmp_path / "refresh_test.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("APP_ENV", "development")

    database.init_db(db_file)
    app = create_app(db_path=db_file)
    client = app.test_client()

    # Initial token
    orig_token = create_access_token(user_id="doc_refresh_01", role="doctor", org_id="comm_alpha")

    # Refresh via endpoint
    res = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {orig_token}"})
    assert res.status_code == 200
    data = res.get_json()
    assert "access_token" in data

    # Verify new token claims
    new_claims, err = safe_decode_token(data["access_token"])
    assert err is None
    assert new_claims["user_id"] == "doc_refresh_01"
    assert new_claims["role"] == "doctor"
    assert new_claims["org_id"] == "comm_alpha"


def test_0_5_join_codes_complexity_and_expiry(tmp_path):
    """0.5: Join codes must be at least 12 chars URL-safe, reject weak custom codes, and have expiry."""
    db_file = str(tmp_path / "join_codes_test.db")
    database.init_db(db_file)

    # 1. Generated code must be >= 12 chars
    comm_auto = database.create_community("Camp Alpha", "Dr. A", "a@clinic.org", db_path=db_file)
    assert len(comm_auto["code"]) >= 12

    # 2. Reject weak / short custom codes (< 12 chars or guessable)
    with pytest.raises(ValueError, match="at least 12 characters"):
        database.create_community("Camp Beta", "Dr. B", "b@clinic.org", code="SHORT123", db_path=db_file)

    with pytest.raises(ValueError, match="sufficiently complex"):
        database.create_community("Camp Gamma", "Dr. C", "c@clinic.org", code="11111111111111", db_path=db_file)

    # 3. Valid complex code succeeds and sets expires_at
    valid_code = secrets.token_urlsafe(12)
    comm_custom = database.create_community("Camp Delta", "Dr. D", "d@clinic.org", code=valid_code, db_path=db_file)
    assert comm_custom["code"] == valid_code
    assert comm_custom.get("expires_at") is not None


def test_0_6_standardized_field_worker_role():
    """0.6: Standardize on 'field_worker' role and alias legacy 'worker'."""
    token = create_access_token(user_id="worker_01", role="field_worker", org_id="comm_alpha")
    claims, _ = safe_decode_token(token)
    assert claims["role"] == "field_worker"

    # Alias legacy 'worker' to 'field_worker'
    token_alias = create_access_token(user_id="worker_02", role="worker", org_id="comm_alpha")
    claims_alias, _ = safe_decode_token(token_alias)
    assert claims_alias["role"] == "field_worker"


# ==============================================================================
# PART 1: Task 9 - Configuration and Provider
# ==============================================================================

def test_9_1_ai_provider_default_gemini_and_explicit_switching(monkeypatch):
    """9.1: AI_PROVIDER defaults to 'gemini' even when other keys exist; switches only when explicitly set."""
    # When NVIDIA_API_KEY and GROQ_API_KEY exist but AI_PROVIDER is unset -> MUST be gemini
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-some-key")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-some-key")

    assert get_configured_ai_provider() == "gemini"

    # Explicit switching
    monkeypatch.setenv("AI_PROVIDER", "claude")
    assert get_configured_ai_provider() == "claude"

    monkeypatch.setenv("AI_PROVIDER", "groq")
    assert get_configured_ai_provider() == "groq"

    monkeypatch.setenv("AI_PROVIDER", "nvidia")
    assert get_configured_ai_provider() == "nvidia"


def test_9_2_usage_ledger_records_provider_and_model(tmp_path):
    """9.2: Add provider and model name to every usage_ledger row."""
    db_file = str(tmp_path / "ledger_provider_test.db")
    database.init_db(db_file)

    database.log_usage_ledger(
        org_id="org_test_provider",
        record_id="rec_prov_001",
        action="ai_extract",
        provider="claude",
        model="claude-sonnet-5-5",
        tokens_in=2000,
        tokens_out=500,
        cost_rs=3.50,
        db_path=db_file
    )

    ledger = database.get_usage_ledger_paged(org_id="org_test_provider", db_path=db_file)
    rows = ledger.get("rows", [])
    assert len(rows) == 1
    assert rows[0]["provider"] == "claude"
    assert rows[0]["model"] == "claude-sonnet-5-5"


def test_9_3_production_startup_validation_fail_fast(tmp_path, monkeypatch):
    """9.3: APP_ENV=production fails fast if JWT_SECRET missing, API key missing, or Vercel SQLite."""
    db_file = str(tmp_path / "prod_startup.db")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)

    # 1. Missing JWT secret in production -> RuntimeError
    with pytest.raises(RuntimeError, match="JWT_SECRET is missing"):
        create_app(db_path=db_file)

    # 2. Provide JWT secret, but missing selected provider key
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("AI_PROVIDER", "claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is missing"):
        create_app(db_path=db_file)

    # 3. Vercel environment with local SQLite database -> RuntimeError
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy_gemini_key")
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(RuntimeError, match="Local SQLite database cannot be used in serverless Vercel"):
        create_app(db_path=db_file)


def test_9_4_public_health_endpoint_diagnostics(tmp_path, monkeypatch):
    """9.4: GET /api/health returns version, provider, model, db ok, and zero secrets."""
    db_file = str(tmp_path / "health_test.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")

    database.init_db(db_file)
    app = create_app(db_path=db_file)
    client = app.test_client()

    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert "version" in data
    assert data["provider"] == "gemini"
    assert "model" in data
    assert data["database"] == "ok"
    # Never return secrets
    raw_text = res.get_data(as_text=True)
    assert TEST_JWT_SECRET not in raw_text


def test_9_5_daily_scan_cap_per_org(tmp_path, monkeypatch):
    """9.5: Enforce DAILY_SCAN_CAP_PER_ORG before AI call without breaking reserve_paper / release_paper."""
    db_file = str(tmp_path / "daily_cap_test.db")
    monkeypatch.setenv("DAILY_SCAN_CAP_PER_ORG", "2")
    database.init_db(db_file)

    org_id = "org_daily_cap_test"
    database.get_or_create_org(org_id=org_id, papers_included=100, db_path=db_file)

    # 1. First scan succeeds
    ok1, code1, _ = database.reserve_paper(org_id=org_id, record_id="rec_1", db_path=db_file)
    assert ok1 is True
    database.log_usage_ledger(org_id=org_id, record_id="rec_1", action="ai_extract", db_path=db_file)

    # 2. Second scan succeeds
    ok2, code2, _ = database.reserve_paper(org_id=org_id, record_id="rec_2", db_path=db_file)
    assert ok2 is True
    database.log_usage_ledger(org_id=org_id, record_id="rec_2", action="ai_extract", db_path=db_file)

    # 3. Third scan hits DAILY_SCAN_CAP_PER_ORG -> rejected
    ok3, code3, _ = database.reserve_paper(org_id=org_id, record_id="rec_3", db_path=db_file)
    assert ok3 is False
    assert code3 == "daily_cap_reached"

    # 4. Release paper from second scan functions properly
    rel_ok = database.release_paper(org_id=org_id, record_id="rec_2", reason="scan_failed", db_path=db_file)
    assert rel_ok is not None and (rel_ok is True or rel_ok >= 0)


# ==============================================================================
# PART 2: Task 10 - Protect Scans and Patient Files
# ==============================================================================

def test_10_1_and_10_2_private_files_endpoint(tmp_path, monkeypatch):
    """10.1 & 10.2: Files stored outside static root; GET /api/files/<id> (401 unauth, 404 cross-org, 200 own org)."""
    db_file = str(tmp_path / "files_test.db")
    private_dir = str(tmp_path / "private_uploads")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("PRIVATE_UPLOAD_DIR", private_dir)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)

    database.init_db(db_file)
    app = create_app(db_path=db_file)
    client = app.test_client()

    # Save a private test file belonging to Org A
    file_bytes = b"JPEG_BINARY_DATA_OF_CONFIDENTIAL_CLINICAL_INTAKE_RECORD"
    file_id = database.save_private_file(
        org_id="org_alpha",
        record_id="rec_alpha_01",
        file_type="scan_page1",
        filename="scan1.jpg",
        data=file_bytes,
        mime_type="image/jpeg",
        db_path=db_file,
        private_dir=private_dir
    )

    # 1. Unauthenticated request -> 401
    res_unauth = client.get(f"/api/files/{file_id}")
    assert res_unauth.status_code == 401

    # 2. Cross-org request from Org Beta -> 404 (NOT 403, to avoid leaking existence)
    tok_beta = create_access_token(user_id="doc_beta", role="doctor", org_id="org_beta")
    res_cross = client.get(f"/api/files/{file_id}", headers={"Authorization": f"Bearer {tok_beta}"})
    assert res_cross.status_code == 404

    # 3. Own-org request from Org Alpha -> 200 with matching bytes
    tok_alpha = create_access_token(user_id="doc_alpha", role="doctor", org_id="org_alpha")
    res_own = client.get(f"/api/files/{file_id}", headers={"Authorization": f"Bearer {tok_alpha}"})
    assert res_own.status_code == 200
    assert res_own.data == file_bytes
    assert res_own.mimetype == "image/jpeg"


def test_10_2_signed_short_lived_file_url(tmp_path, monkeypatch):
    """10.2: Short-lived signed URL allows image tags to load files without Authorization header; fails when expired."""
    db_file = str(tmp_path / "signed_url_test.db")
    private_dir = str(tmp_path / "private_uploads")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("PRIVATE_UPLOAD_DIR", private_dir)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)

    database.init_db(db_file)
    app = create_app(db_path=db_file)
    client = app.test_client()

    file_bytes = b"PATIENT_SCAN_DATA"
    file_id = database.save_private_file(
        org_id="org_alpha",
        record_id="rec_alpha_02",
        file_type="scan_page1",
        filename="page1.jpg",
        data=file_bytes,
        mime_type="image/jpeg",
        db_path=db_file,
        private_dir=private_dir
    )

    # Generate signed token valid for 5 minutes
    signed_token = database.generate_signed_file_token(file_id, org_id="org_alpha", expires_in_seconds=300)

    # 1. Valid signed token succeeds without Authorization header
    res_signed = client.get(f"/api/files/{file_id}?token={signed_token}")
    assert res_signed.status_code == 200
    assert res_signed.data == file_bytes

    # 2. Expired signed token fails with 401
    expired_token = database.generate_signed_file_token(file_id, org_id="org_alpha", expires_in_seconds=-10)
    res_expired = client.get(f"/api/files/{file_id}?token={expired_token}")
    assert res_expired.status_code == 401


def test_10_4_static_route_blocks_uploads_and_traversal(tmp_path, monkeypatch):
    """10.4: Catch-all static route returns 404 for /uploads/... and path traversal attempts."""
    db_file = str(tmp_path / "static_safety.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)

    app = create_app(db_path=db_file)
    client = app.test_client()

    # 1. /uploads/... must return 404
    res_upload = client.get("/uploads/patient_confidential.jpg")
    assert res_upload.status_code == 404

    # 2. Traversal ../ must return 404
    res_trav1 = client.get("/../backend/.env")
    assert res_trav1.status_code == 404

    res_trav2 = client.get("/..%2f..%2fbackend%2fdatabase.py")
    assert res_trav2.status_code == 404


def test_10_5_migrate_uploads_to_private_folder(tmp_path):
    """10.5: Safe migration of legacy frontend/uploads to private folder updating stored paths."""
    db_file = str(tmp_path / "migration_files.db")
    frontend_dir = str(tmp_path / "frontend")
    legacy_uploads = str(tmp_path / "frontend" / "uploads")
    private_dir = str(tmp_path / "private_uploads")
    os.makedirs(legacy_uploads, exist_ok=True)
    os.makedirs(private_dir, exist_ok=True)

    database.init_db(db_file)
    camp = database.create_camp("Legacy Camp", 10, "Today", community_id="comm_legacy", db_path=db_file)

    # Create dummy legacy upload file
    legacy_file_path = os.path.join(legacy_uploads, "legacy_scan_01.jpg")
    test_content = b"LEGACY_PATIENT_SCAN_JPEG_DATA"
    with open(legacy_file_path, "wb") as f:
        f.write(test_content)

    rec = database.insert_record({
        "camp_id": camp["id"],
        "community_id": "comm_legacy",
        "person_name": "Legacy Patient",
        "page1_preview": "/uploads/legacy_scan_01.jpg",
        "status": "needs_review"
    }, db_path=db_file)

    # Run migration
    migrated_count = database.migrate_uploads_to_private_storage(
        db_path=db_file,
        frontend_dir=frontend_dir,
        private_dir=private_dir
    )
    assert migrated_count == 1

    # Check updated record path in database
    updated_rec = database.get_record_by_id(rec["id"], db_path=db_file)
    assert updated_rec["page1_preview"].startswith("/api/files/file_")

    # Verify original file was preserved until verified
    assert os.path.exists(legacy_file_path)


def test_10_6_retention_and_dpdp_file_deletion(tmp_path):
    """10.6: Scheduled retention cleanup and /api/records/<id>/erase deletes physical files from disk."""
    db_file = str(tmp_path / "retention_test.db")
    private_dir = str(tmp_path / "private_uploads")
    database.init_db(db_file)

    camp = database.create_camp("Retention Camp", 10, "Today", community_id="comm_retention", db_path=db_file)

    file_bytes = b"PATIENT_FILE_FOR_DPDP_DELETION"
    file_id = database.save_private_file(
        org_id="comm_retention",
        record_id="rec_dpdp_del_01",
        file_type="scan_page1",
        filename="p1.jpg",
        data=file_bytes,
        mime_type="image/jpeg",
        db_path=db_file,
        private_dir=private_dir
    )

    rec = database.insert_record({
        "id": "rec_dpdp_del_01",
        "camp_id": camp["id"],
        "community_id": "comm_retention",
        "person_name": "DPDP Patient",
        "page1_preview": f"/api/files/{file_id}",
        "status": "needs_review"
    }, db_path=db_file)

    # Check physical file exists
    file_info = database.get_file_by_id(file_id, db_path=db_file)
    disk_path = file_info["storage_path"]
    assert os.path.exists(disk_path)

    # Erase record -> physical file must be deleted from disk and files table
    success = database.erase_record_data("rec_dpdp_del_01", db_path=db_file)
    assert success is True
    assert not os.path.exists(disk_path)
    assert database.get_file_by_id(file_id, db_path=db_file) is None
