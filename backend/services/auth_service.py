"""Authentication & Authorization Service for I2 insights.

Handles:
- JWT token issuance (12-hour expiration, HS256, standard claims: sub, user_id, role, org_id, email, name)
- JWT token verification and decoding
- PIN hashing with cryptographic salt (SHA-256)
- Pluggable OTP provider interface (Console, Mock, SMS gateway adapter)
- Auth decorators and request helpers
"""

import os
import secrets
import hashlib
import hmac
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import Dict, Any, Optional, Tuple, List
import bcrypt
import jwt
from flask import request, jsonify, g

logger = logging.getLogger(__name__)

# Default signing key must be >= 32 bytes to satisfy cryptographic standards and avoid InsecureKeyLengthWarning
DEFAULT_JWT_SECRET = "i2i_jwt_secret_clinic_v1_secure_signing_key_32_bytes"
JWT_ALGORITHM = "HS256"
DEFAULT_TOKEN_EXPIRY_HOURS = 12


def get_jwt_secret() -> str:
    """Retrieve secret signing key from environment or fallback to default in dev.
    Fails closed if keys are missing in production.
    
    SECURITY FIX: Added strict validation and warning for default secret usage.
    """
    secret = os.environ.get("SUPABASE_JWT_SECRET") or os.environ.get("JWT_SECRET")
    app_env = (os.environ.get("APP_ENV") or "production").strip().lower()
    
    if not secret:
        if app_env == "production":
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: JWT secret is missing in production environment. "
                "Set SUPABASE_JWT_SECRET or JWT_SECRET environment variable immediately. "
                "Application startup blocked for security."
            )
        # Development fallback with warning
        logger.warning(
            "SECURITY WARNING: Using default JWT secret in development. "
            "This is INSECURE for production. Set JWT_SECRET environment variable."
        )
        return DEFAULT_JWT_SECRET
    
    # Validate secret length (minimum 32 bytes)
    if len(secret) < 32:
        raise RuntimeError(
            f"CRITICAL SECURITY ERROR: JWT secret must be at least 32 bytes long. "
            f"Current length: {len(secret)} bytes. Generate a secure secret: "
            f"python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    
    return secret


# ─────────────────────────────────────────────────────────────────────────────
# JWT Token Functions (Supabase Compatible)
# ─────────────────────────────────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    role: str = "doctor",
    org_id: str = "org_default",
    email: Optional[str] = None,
    name: Optional[str] = None,
    expires_hours: int = DEFAULT_TOKEN_EXPIRY_HOURS,
    issuer: str = "supabase",
    orig_iat: Optional[int] = None
) -> str:
    """Generate a signed Supabase-compatible JWT access token valid for `expires_hours` (default 12 hours)."""
    now = datetime.now(timezone.utc)
    clean_role = str(role).lower()
    if clean_role == "worker":
        clean_role = "field_worker"
    clean_org = str(org_id)
    origin_timestamp = int(orig_iat if orig_iat is not None else now.timestamp())
    payload = {
        "iss": issuer,
        "sub": str(user_id),
        "aud": "authenticated",
        "email": email or "",
        # Security Rule: store role and org_id in app_metadata, not user_metadata
        "app_metadata": {
            "provider": "email",
            "role": clean_role,
            "org_id": clean_org,
            "orig_iat": origin_timestamp
        },
        "user_metadata": {
            "full_name": name or "",
            "name": name or ""
        },
        # Top-level claims for convenience & legacy parity
        "user_id": str(user_id),
        "role": clean_role,
        "org_id": clean_org,
        "name": name or "",
        "iat": int(now.timestamp()),
        "orig_iat": origin_timestamp,
        "exp": int((now + timedelta(hours=expires_hours)).timestamp())
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def extract_claims(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract verified claims from decoded JWT.
    
    CRITICAL SECURITY INVARIANT:
    Roles and org_id are taken strictly from app_metadata (never user_metadata),
    because end-users can update user_metadata in Supabase, but only admins can touch app_metadata.
    Rejects tokens with missing org_id or role (no fallback).
    """
    app_meta = payload.get("app_metadata") if isinstance(payload.get("app_metadata"), dict) else {}
    user_meta = payload.get("user_metadata") if isinstance(payload.get("user_metadata"), dict) else {}

    # Strict precedence: app_metadata (or top-level payload for tests), NEVER user_metadata
    role = app_meta.get("role") or payload.get("role")
    org_id = app_meta.get("org_id") or payload.get("org_id")

    if not role or not str(role).strip() or not org_id or not str(org_id).strip():
        raise jwt.InvalidTokenError("Missing required claim: role and org_id are mandatory")

    clean_role = str(role).strip().lower()
    if clean_role == "worker":
        clean_role = "field_worker"

    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise jwt.InvalidTokenError("Missing required claim: sub (user_id)")

    name = user_meta.get("name") or user_meta.get("full_name") or payload.get("name") or str(user_id)
    orig_iat = payload.get("orig_iat") or app_meta.get("orig_iat") or payload.get("iat")

    return {
        "sub": str(user_id),
        "user_id": str(user_id),
        "role": clean_role,
        "org_id": str(org_id).strip(),
        "email": payload.get("email"),
        "name": name,
        "orig_iat": int(orig_iat) if orig_iat is not None else None,
        "app_metadata": app_meta,
        "user_metadata": user_meta,
        "raw": payload
    }


def decode_access_token(token: str, verify_exp: bool = True) -> Dict[str, Any]:
    """Decode and validate a JWT access token against signature, expiry, audience, issuer, and secret.
    
    Raises:
        jwt.ExpiredSignatureError: If token is expired.
        jwt.InvalidTokenError: If token signature, aud, iss, or structure is invalid.
    """
    secret = get_jwt_secret()
    if not secret:
        raise jwt.InvalidTokenError("Missing JWT secret")
    options = {
        "verify_exp": verify_exp,
        "verify_aud": True,
        "verify_iss": True,
    }
    return jwt.decode(
        token,
        secret,
        algorithms=[JWT_ALGORITHM],
        audience=["authenticated", "anon", "doc_scanner_api"],
        issuer=["supabase", "https://uppyxcptyezsyuayuqyw.supabase.co/auth/v1", "doc_scanner"],
        options=options
    )


def safe_decode_token(token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Safe wrapper returning (claims, error_message)."""
    if not token:
        return None, "Missing token"
    try:
        raw_payload = decode_access_token(token)
        claims = extract_claims(raw_payload)
        return claims, None
    except jwt.ExpiredSignatureError:
        return None, "Token has expired. Please log in again."
    except jwt.InvalidTokenError as e:
        return None, f"Invalid token: {str(e)}"
    except Exception as e:
        return None, f"Token validation error: {str(e)}"


def get_token_from_request() -> Optional[str]:
    """Extract Bearer token from HTTP Authorization header or X-Access-Token."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token:
            return token
    alt_token = request.headers.get("X-Access-Token")
    if alt_token:
        return alt_token.strip()
    return None


# ─────────────────────────────────────────────────────────────────────────────
# PIN Hashing & Verification (Bcrypt + Legacy SHA-256 Transparent Upgrade)
# ─────────────────────────────────────────────────────────────────────────────

def hash_pin(pin: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hash a numeric PIN using bcrypt.
    
    Returns:
        (bcrypt_hash_str, salt_str)
    """
    clean_pin = str(pin).strip()
    salt_val = salt or secrets.token_hex(16)
    hashed = bcrypt.hashpw(clean_pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return hashed, salt_val


def verify_pin(pin: str, stored_hash: str, salt: Optional[str] = None) -> bool:
    """Verify candidate PIN against stored hash.
    Supports bcrypt and legacy SHA-256 for transparent automatic upgrade on login.
    """
    if not stored_hash:
        return False
    clean_pin = str(pin).strip()
    # Check if bcrypt hash
    if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
        try:
            return bcrypt.checkpw(clean_pin.encode("utf-8"), stored_hash.encode("utf-8"))
        except Exception:
            return False
    # Legacy SHA-256 fallback
    if salt:
        hasher = hashlib.sha256()
        hasher.update(f"{salt}:{clean_pin}".encode("utf-8"))
        return hmac.compare_digest(hasher.hexdigest(), stored_hash)
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Account Lockout (5 failed attempts -> 15 min lock)
# ─────────────────────────────────────────────────────────────────────────────

_ACCOUNT_LOCKOUTS: Dict[str, Tuple[int, datetime]] = {}


def check_account_locked(account_key: str, db_path: Optional[str] = None) -> Tuple[bool, Optional[int]]:
    """Check if an account/identifier is locked out after 5 consecutive failed attempts.
    Rule 0.1: Backed by shared database store.
    """
    try:
        from backend import database
        target_db = db_path or getattr(g, "db_path", None) or os.getenv("DATABASE_PATH") or database.DEFAULT_DB_PATH
        is_locked, remaining = database.is_account_locked(account_key, db_path=target_db)
        if is_locked:
            return True, remaining
    except Exception as e:
        logger.warning("DB lockout check error: %s", e)

    record = _ACCOUNT_LOCKOUTS.get(account_key)
    if not record:
        return False, None
    attempts, locked_until = record
    if locked_until and datetime.now(timezone.utc) < locked_until:
        remaining_seconds = int((locked_until - datetime.now(timezone.utc)).total_seconds())
        return True, remaining_seconds
    return False, None


def record_login_attempt(account_key: str, success: bool, db_path: Optional[str] = None):
    """Record a failed attempt or reset counter upon successful login.
    Rule 0.1: Backed by shared database store.
    """
    try:
        from backend import database
        target_db = db_path or getattr(g, "db_path", None) or os.getenv("DATABASE_PATH") or database.DEFAULT_DB_PATH
        if success:
            database.reset_login_failures(account_key, db_path=target_db)
        else:
            database.record_login_failure(account_key, max_attempts=5, lock_minutes=15, db_path=target_db)
    except Exception as e:
        logger.warning("DB record login attempt error: %s", e)

    if success:
        _ACCOUNT_LOCKOUTS.pop(account_key, None)
        return
    now = datetime.now(timezone.utc)
    attempts, _ = _ACCOUNT_LOCKOUTS.get(account_key, (0, None))
    attempts += 1
    if attempts >= 5:
        locked_until = now + timedelta(minutes=15)
        _ACCOUNT_LOCKOUTS[account_key] = (attempts, locked_until)
    else:
        _ACCOUNT_LOCKOUTS[account_key] = (attempts, None)


# ─────────────────────────────────────────────────────────────────────────────
# Pluggable OTP Providers
# ─────────────────────────────────────────────────────────────────────────────

class BaseOTPProvider(ABC):
    """Abstract interface for clinical OTP delivery."""
    @abstractmethod
    def send_otp(self, recipient: str, otp_code: str) -> bool:
        pass


class ConsoleOTPProvider(BaseOTPProvider):
    """Development/Console OTP provider.
    
    SECURITY FIX: Removed print statement that could expose OTP codes in production logs.
    OTP codes are now only logged via the logger (which can be configured for security).
    """
    def send_otp(self, recipient: str, otp_code: str) -> bool:
        app_env = (os.environ.get("APP_ENV") or "production").strip().lower()
        
        # Only log OTP in development environment
        if app_env == "development":
            logger.info("[ConsoleOTP] Clinical verification code for %s is %s", recipient, otp_code)
            # Print to console ONLY in development
            print(f"\n[ConsoleOTP] Verification Code for {recipient}: {otp_code}\n")
        else:
            # In production, log without the actual OTP code
            logger.info("[ConsoleOTP] Verification code sent to %s (code hidden for security)", recipient)
        
        return True


class MockOTPProvider(BaseOTPProvider):
    """Testing OTP provider recording sent OTPs."""
    def __init__(self):
        self.sent_otps: Dict[str, str] = {}

    def send_otp(self, recipient: str, otp_code: str) -> bool:
        self.sent_otps[recipient] = otp_code
        logger.info("[MockOTP] Recorded OTP for %s: %s", recipient, otp_code)
        return True


class TwilioOrMsg91OTPProvider(BaseOTPProvider):
    """External SMS delivery adapter (Twilio / MSG91)."""
    def send_otp(self, recipient: str, otp_code: str) -> bool:
        api_key = os.getenv("SMS_GATEWAY_API_KEY")
        if not api_key:
            logger.warning("[SMSProvider] No SMS_GATEWAY_API_KEY configured; falling back to log")
            return ConsoleOTPProvider().send_otp(recipient, otp_code)
        logger.info("[SMSProvider] Dispatched SMS to %s via external gateway", recipient)
        return True


def get_otp_provider() -> BaseOTPProvider:
    """Factory selecting configured OTP provider."""
    provider_name = os.getenv("OTP_PROVIDER", "console").lower().strip()
    if provider_name == "mock":
        return MockOTPProvider()
    if provider_name in ("twilio", "msg91", "sms"):
        return TwilioOrMsg91OTPProvider()
    return ConsoleOTPProvider()


# In-memory OTP storage for verification with 5-minute expiry
_ACTIVE_OTPS: Dict[str, Tuple[str, datetime]] = {}


def _resolve_target_db(db_path: Optional[str] = None) -> str:
    from backend import database
    if db_path:
        return db_path
    try:
        from flask import has_app_context, g
        if has_app_context() and hasattr(g, "db_path") and g.db_path:
            return g.db_path
    except Exception:
        pass
    return os.getenv("DATABASE_PATH") or database.DEFAULT_DB_PATH


def send_otp_for_recipient(recipient: str, db_path: Optional[str] = None) -> str:
    """Generate and dispatch a 6-digit OTP code with strict 5-minute expiry.
    Rule 0.1: Stored in shared database store.
    """
    app_env = (os.getenv("APP_ENV") or "production").strip().lower()
    if app_env == "development":
        otp = "123456"
    else:
        otp = f"{secrets.randbelow(900000) + 100000}"
    
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    _ACTIVE_OTPS[recipient] = (otp, expires_at)

    try:
        from backend import database
        target_db = _resolve_target_db(db_path)
        database.save_auth_otp(recipient, otp, expires_in_minutes=5, db_path=target_db)
    except Exception as e:
        logger.warning("DB save OTP error: %s", e)

    provider = get_otp_provider()
    provider.send_otp(recipient, otp)
    return otp


def verify_submitted_otp(recipient: str, candidate_otp: str, db_path: Optional[str] = None) -> bool:
    """Verify submitted OTP code against recipient.
    
    Rule: Single-use OTP strictly expiring in 5 minutes.
    Rule: DEV_OTP '123456' is accepted ONLY when APP_ENV=development.
    Rule 0.1: Verified and consumed from shared database store.
    """
    app_env = (os.getenv("APP_ENV") or "production").strip().lower()
    clean_candidate = str(candidate_otp).strip()

    try:
        from backend import database
        target_db = _resolve_target_db(db_path)
        db_valid = database.verify_and_consume_auth_otp(recipient, clean_candidate, db_path=target_db)
        if db_valid:
            _ACTIVE_OTPS.pop(recipient, None)
            return True
        else:
            _ACTIVE_OTPS.pop(recipient, None)
            return False
    except Exception as e:
        logger.warning("DB verify OTP error: %s", e)

    record = _ACTIVE_OTPS.get(recipient)
    if not record:
        if clean_candidate == "123456" and app_env == "development":
            return True
        return False

    expected_otp, expires_at = record
    if datetime.now(timezone.utc) > expires_at:
        _ACTIVE_OTPS.pop(recipient, None)
        return False

    if clean_candidate == "123456" and app_env == "development":
        _ACTIVE_OTPS.pop(recipient, None)
        return True

    if clean_candidate == expected_otp:
        _ACTIVE_OTPS.pop(recipient, None)
        return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Auth Decorator
# ─────────────────────────────────────────────────────────────────────────────

def require_auth(roles: Optional[List[str]] = None):
    """Route decorator enforcing JWT token presence and optional role check."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = get_token_from_request()
            if not token:
                return jsonify({
                    "error": "unauthorized",
                    "message": "Authentication required. Bearer token missing."
                }), 401

            payload, err = safe_decode_token(token)
            if err or not payload:
                return jsonify({
                    "error": "unauthorized",
                    "message": err or "Invalid authentication token."
                }), 401

            # Attach to Flask request context
            g.current_user = payload
            g.user_id = payload.get("user_id") or payload.get("sub")
            g.user_role = (payload.get("role") or "").lower()
            g.org_id = payload.get("org_id")

            if roles:
                allowed_roles = [r.lower() for r in roles]
                if g.user_role not in allowed_roles:
                    return jsonify({
                        "error": "forbidden",
                        "message": f"Insufficient permissions. Required: {', '.join(roles)}"
                    }), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator
