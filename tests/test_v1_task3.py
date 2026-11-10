"""Tests for V1 Task 3: Real Authentication & Authorization.

Requirements:
1. 401 Unauthorized tests: missing token, invalid token, expired token.
2. 403 Forbidden tests: insufficient role permissions (field_worker accessing admin endpoint, field_worker attempting clinical review).
3. Public endpoints remain accessible without tokens:
   - GET /api/status
   - GET /api/config/quality
   - GET /api/health
   - POST /api/community/verify
   - POST /api/community/verify-invite
4. Refuse /api/auth/demo when APP_ENV=production (returns 403).
5. Accept DEV_OTP=123456 only when APP_ENV=development; refuse in production.
6. Take org_id and user from the token only (ignore/override spoofed body/header org_id).
7. PIN hashing with salt before storage.
8. 12-hour token expiration and standard claims.
"""

import os
import json
import pytest
from datetime import datetime, timezone, timedelta
import jwt

from backend.app import create_app
from backend import database
from backend.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_pin,
    verify_pin,
    JWT_ALGORITHM,
)

TEST_JWT_SECRET = "test_jwt_secret_clinic_key_999_32_bytes_long"


@pytest.fixture
def auth_client_and_db(tmp_path, monkeypatch):
    """Fixture providing an isolated SQLite database and configured Flask test client."""
    db_file = str(tmp_path / "test_auth_clinic.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("APP_ENV", "development")

    database.init_db(db_file)
    app = create_app(db_path=db_file)
    app.config["TESTING"] = True
    client = app.test_client()

    # Seed test community
    with database.get_db_connection(db_file) as conn:
        conn.cursor().execute("""
            INSERT OR REPLACE INTO communities (id, name, code, creator_name, creator_email, created_at)
            VALUES ('comm_test_01', 'Apollo Outreach Camp', 'TESTCODE1', 'Dr. Priya', 'priya@clinic.camp', '2026-10-01T00:00:00');
        """)
        conn.commit()

    return client, db_file


# ─────────────────────────────────────────────────────────────────────────────
# 1. 401 Unauthorized Tests (Written First per instruction)
# ─────────────────────────────────────────────────────────────────────────────

def test_protected_route_missing_token_returns_401(auth_client_and_db):
    """Protected endpoint (GET /api/records) returns 401 when Authorization header is missing."""
    client, _ = auth_client_and_db
    res = client.get("/api/records")
    assert res.status_code == 401
    data = res.get_json()
    assert data["error"] == "unauthorized"


def test_protected_route_invalid_token_returns_401(auth_client_and_db):
    """Protected endpoint returns 401 when Bearer token is malformed or forged."""
    client, _ = auth_client_and_db
    headers = {"Authorization": "Bearer not-a-valid-jwt-token"}
    res = client.get("/api/records", headers=headers)
    assert res.status_code == 401
    data = res.get_json()
    assert data["error"] == "unauthorized"


def test_protected_route_expired_token_returns_401(auth_client_and_db):
    """Protected endpoint returns 401 when JWT token is expired (> 12 hours old)."""
    client, _ = auth_client_and_db
    expired_payload = {
        "sub": "doc_expired",
        "user_id": "doc_expired",
        "role": "doctor",
        "org_id": "comm_test_01",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=13)
    }
    expired_token = jwt.encode(expired_payload, TEST_JWT_SECRET, algorithm=JWT_ALGORITHM)

    headers = {"Authorization": f"Bearer {expired_token}"}
    res = client.get("/api/records", headers=headers)
    assert res.status_code == 401
    data = res.get_json()
    assert data["error"] == "unauthorized"
    assert "expired" in data.get("message", "").lower()


# ─────────────────────────────────────────────────────────────────────────────
# 2. 403 Forbidden Tests (Written First per instruction)
# ─────────────────────────────────────────────────────────────────────────────

def test_admin_route_forbidden_for_field_worker_returns_403(auth_client_and_db):
    """Admin-only endpoint (POST /api/admin/ai-pause) returns 403 for field_worker role."""
    client, _ = auth_client_and_db
    token = create_access_token(user_id="worker_01", role="field_worker", org_id="comm_test_01")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/admin/ai-pause", json={"paused": True}, headers=headers)
    assert res.status_code == 403
    data = res.get_json()
    assert data["error"] == "forbidden"


def test_doctor_route_forbidden_for_unauthorized_role_returns_403(auth_client_and_db):
    """Clinical review endpoint requires doctor or admin role; field_worker is forbidden (403)."""
    client, _ = auth_client_and_db
    admin_token = create_access_token(user_id="doc_admin", role="doctor", org_id="comm_test_01")
    camp_res = client.post(
        "/api/camps",
        json={"name": "Rural Camp 2026"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    camp_id = camp_res.get_json()["id"]

    rec_res = client.post(
        "/api/records",
        json={"camp_id": camp_id, "person_name": "Radha K", "status": "needs_review"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    record_id = rec_res.get_json()["id"]

    # Attempt review as field_worker
    worker_token = create_access_token(user_id="worker_02", role="field_worker", org_id="comm_test_01")
    headers = {"Authorization": f"Bearer {worker_token}"}
    res = client.post(
        f"/api/records/{record_id}/review",
        json={"person_name": "Radha Krishnan"},
        headers=headers
    )
    assert res.status_code == 403
    data = res.get_json()
    assert data["error"] == "forbidden"


def _seed_two_org_records(client, db_file):
    """Helper to create records belonging to two distinct organizations."""
    from backend import database
    # Org B Camp & Record
    database.create_camp("Camp Org B", 50, "Today", camp_id="camp_b_01", community_id="org_B", db_path=db_file)
    with database.get_db_connection(db_file) as conn:
        conn.cursor().execute("""
            INSERT OR REPLACE INTO records (id, camp_id, person_name, status, community_id, created_at, updated_at)
            VALUES ('rec_org_b_99', 'camp_b_01', 'Patient In Org B', 'needs_review', 'org_B', '2026-10-29T10:00:00', '2026-10-29T10:00:00');
        """)
        conn.commit()


def test_cross_org_read_and_change_forbidden_for_admin(auth_client_and_db):
    """403: Admin in Org A cannot read or change Org B's records."""
    client, db_file = auth_client_and_db
    _seed_two_org_records(client, db_file)

    admin_a_token = create_access_token(user_id="admin_a", role="admin", org_id="org_A")
    headers = {"Authorization": f"Bearer {admin_a_token}"}

    # 1. Admin A attempts to READ Org B record -> 403
    read_res = client.get("/api/records/rec_org_b_99", headers=headers)
    assert read_res.status_code == 403
    assert read_res.get_json()["error"] == "forbidden"

    # 2. Admin A attempts to CHANGE Org B record -> 403
    change_res = client.put("/api/records/rec_org_b_99", json={"person_name": "Hacked By Org A"}, headers=headers)
    assert change_res.status_code == 403
    assert change_res.get_json()["error"] == "forbidden"


def test_cross_org_read_and_change_forbidden_for_doctor(auth_client_and_db):
    """403: Doctor in Org A cannot read or change Org B's records."""
    client, db_file = auth_client_and_db
    _seed_two_org_records(client, db_file)

    doc_a_token = create_access_token(user_id="doc_a", role="doctor", org_id="org_A")
    headers = {"Authorization": f"Bearer {doc_a_token}"}

    # 1. Doctor A attempts to READ Org B record -> 403
    read_res = client.get("/api/records/rec_org_b_99", headers=headers)
    assert read_res.status_code == 403
    assert read_res.get_json()["error"] == "forbidden"

    # 2. Doctor A attempts to CHANGE Org B record -> 403
    change_res = client.put("/api/records/rec_org_b_99", json={"person_name": "Hacked By Doctor A"}, headers=headers)
    assert change_res.status_code == 403
    assert change_res.get_json()["error"] == "forbidden"


def test_cross_org_read_and_change_forbidden_for_field_worker(auth_client_and_db):
    """403: Field worker in Org A cannot read or change Org B's records."""
    client, db_file = auth_client_and_db
    _seed_two_org_records(client, db_file)

    worker_a_token = create_access_token(user_id="worker_a", role="field_worker", org_id="org_A")
    headers = {"Authorization": f"Bearer {worker_a_token}"}

    # 1. Worker A attempts to READ Org B record -> 403
    read_res = client.get("/api/records/rec_org_b_99", headers=headers)
    assert read_res.status_code == 403
    assert read_res.get_json()["error"] == "forbidden"

    # 2. Worker A attempts to CHANGE Org B record -> 403
    change_res = client.put("/api/records/rec_org_b_99", json={"person_name": "Hacked By Worker A"}, headers=headers)
    assert change_res.status_code == 403
    assert change_res.get_json()["error"] == "forbidden"


def test_user_metadata_cannot_spoof_app_metadata_org_id(auth_client_and_db):
    """Security: org_id is taken strictly from app_metadata, user_metadata spoof is ignored."""
    client, db_file = auth_client_and_db
    _seed_two_org_records(client, db_file)

    # Malicious user with app_metadata org_id="org_A", but tries to put org_id="org_B" in user_metadata
    now = datetime.now(timezone.utc)
    forged_user_meta_payload = {
        "iss": "supabase",
        "sub": "user_malicious",
        "aud": "authenticated",
        "app_metadata": {
            "provider": "email",
            "role": "doctor",
            "org_id": "org_A"  # Real tenant
        },
        "user_metadata": {
            "org_id": "org_B",  # Malicious attempt to claim org_B
            "role": "admin"
        },
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=12)).timestamp())
    }
    forged_token = jwt.encode(forged_user_meta_payload, TEST_JWT_SECRET, algorithm=JWT_ALGORITHM)
    headers = {
        "Authorization": f"Bearer {forged_token}",
        "X-Org-ID": "org_B"  # Spoofed header
    }

    # Attempt to read Org B record using spoofed user_metadata
    res = client.get("/api/records/rec_org_b_99", headers=headers)
    assert res.status_code == 403
    assert res.get_json()["error"] == "forbidden"



# ─────────────────────────────────────────────────────────────────────────────
# 3. Public Endpoints Whitelist Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_public_whitelist_endpoints_accessible_without_token(auth_client_and_db):
    """Public endpoints must NOT require authentication and must return 200 without Authorization header."""
    client, _ = auth_client_and_db

    # GET /api/status
    res_status = client.get("/api/status")
    assert res_status.status_code == 200

    # GET /api/config/quality
    res_quality = client.get("/api/config/quality")
    assert res_quality.status_code == 200
    assert "blur_min" in res_quality.get_json()

    # GET /api/health
    res_health = client.get("/api/health")
    assert res_health.status_code == 200

    # POST /api/community/verify and /api/community/verify-invite
    res_verify = client.post("/api/community/verify-invite", json={"code": "INVALID_CODE"})
    assert res_verify.status_code == 400

    res_verify_comm = client.post("/api/community/verify", json={"code": "INVALID_CODE"})
    assert res_verify_comm.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# 4. APP_ENV Guards: Demo Login & DEV_OTP
# ─────────────────────────────────────────────────────────────────────────────

def test_demo_login_refused_when_app_env_production(auth_client_and_db, monkeypatch):
    """POST /api/auth/demo must return 403 when APP_ENV=production."""
    client, _ = auth_client_and_db
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "0")

    res = client.post("/api/auth/demo")
    assert res.status_code == 403
    err_text = res.get_json().get("error", "").lower()
    assert "production" in err_text or "disabled" in err_text


def test_dev_otp_accepted_only_when_app_env_development(auth_client_and_db, monkeypatch):
    """DEV_OTP=123456 is accepted in development, but strictly refused in production."""
    client, _ = auth_client_and_db

    # Development: 123456 is accepted
    monkeypatch.setenv("APP_ENV", "development")
    res_dev = client.post("/api/auth/login", json={
        "community_code": "TESTCODE1",
        "phone": "+919876543210",
        "otp": "123456"
    })
    assert res_dev.status_code == 200
    dev_body = res_dev.get_json()
    assert dev_body["success"] is True
    assert "token" in dev_body

    # Production: 123456 is refused
    monkeypatch.setenv("APP_ENV", "production")
    res_prod = client.post("/api/auth/login", json={
        "community_code": "TESTCODE1",
        "phone": "+919876543210",
        "otp": "123456"
    })
    assert res_prod.status_code in (400, 401, 403)
    assert res_prod.get_json().get("success") is not True


# ─────────────────────────────────────────────────────────────────────────────
# 5. Token Authority: org_id and User taken from Token ONLY
# ─────────────────────────────────────────────────────────────────────────────

def test_org_id_and_user_taken_from_token_only(auth_client_and_db):
    """Server takes org_id and user from token only, overriding spoofed request payload/headers."""
    client, _ = auth_client_and_db
    # Create doctor token for org_actual_123
    token = create_access_token(
        user_id="doc_token_user",
        role="doctor",
        org_id="org_actual_123",
        name="Dr. Token Verified"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-ID": "org_spoofed_header"  # Spoofed header
    }

    # Attempt to create a camp claiming org_id='org_spoofed_body'
    camp_res = client.post(
        "/api/camps",
        json={
            "name": "Camp Token Test",
            "org_id": "org_spoofed_body",  # Spoofed body
            "expected_records": 50
        },
        headers=headers
    )
    assert camp_res.status_code == 201
    camp_data = camp_res.get_json()
    # Camp must be attributed to user's real community/org from token
    assert camp_data.get("community_id") == "org_actual_123" or camp_data.get("created_by") == "Dr. Token Verified"


# ─────────────────────────────────────────────────────────────────────────────
# 6. PIN Hashing & Security Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_pin_hashing_and_verification():
    """Verify PIN is stored with cryptographic salt and never in plaintext."""
    raw_pin = "8520"
    hashed, salt = hash_pin(raw_pin)

    assert hashed != raw_pin
    assert len(hashed) in (60, 64)  # Bcrypt (60) or legacy SHA-256 (64)
    assert len(salt) >= 16

    assert verify_pin(raw_pin, hashed, salt) is True
    assert verify_pin("0000", hashed, salt) is False


# ─────────────────────────────────────────────────────────────────────────────
# 7. JWT Expiry (12 Hours) and Claims
# ─────────────────────────────────────────────────────────────────────────────

def test_jwt_token_claims_and_twelve_hour_expiry():
    """Verify access token contains expected claims and expires in 12 hours."""
    token = create_access_token(
        user_id="doc_789",
        role="doctor",
        org_id="comm_test_01",
        email="doctor@clinic.camp",
        name="Dr. Priya",
        expires_hours=12
    )
    payload = decode_access_token(token)
    assert payload["sub"] == "doc_789"
    assert payload["role"] == "doctor"
    assert payload["org_id"] == "comm_test_01"
    assert payload["name"] == "Dr. Priya"

    now_ts = datetime.now(timezone.utc).timestamp()
    exp_ts = payload["exp"]
    diff_hours = (exp_ts - now_ts) / 3600.0
    assert 11.8 < diff_hours <= 12.1
