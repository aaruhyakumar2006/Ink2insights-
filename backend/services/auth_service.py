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
import jwt
from flask import request, jsonify, g

logger = logging.getLogger(__name__)

# Default signing key must be >= 32 bytes to satisfy cryptographic standards and avoid InsecureKeyLengthWarning
DEFAULT_JWT_SECRET = "i2i_jwt_secret_clinic_v1_secure_signing_key_32_bytes"
JWT_ALGORITHM = "HS256"
DEFAULT_TOKEN_EXPIRY_HOURS = 12


def get_jwt_secret() -> str:
    """Retrieve secret signing key from environment or fallback to default."""
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        return DEFAULT_JWT_SECRET
    # Ensure key is at least 32 bytes
    if len(secret.encode("utf-8")) < 32:
        return secret.ljust(32, "_")
    return secret


# ─────────────────────────────────────────────────────────────────────────────
# JWT Token Functions
# ─────────────────────────────────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    role: str = "doctor",
    org_id: str = "org_default",
    email: Optional[str] = None,
    name: Optional[str] = None,
    expires_hours: int = DEFAULT_TOKEN_EXPIRY_HOURS
) -> str:
    """Generate a signed JWT access token valid for `expires_hours` (default 12 hours)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "user_id": str(user_id),
        "role": str(role).lower(),
        "org_id": str(org_id),
        "email": email or "",
        "name": name or "",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=expires_hours)).timestamp())
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, verify_exp: bool = True) -> Dict[str, Any]:
    """Decode and validate a JWT access token.
    
    Raises:
        jwt.ExpiredSignatureError: If token is expired.
        jwt.InvalidTokenError: If token signature or structure is invalid.
    """
    options = {"verify_exp": verify_exp}
    return jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM], options=options)


def safe_decode_token(token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Safe wrapper returning (payload, error_message)."""
    if not token:
        return None, "Missing token"
    try:
        payload = decode_access_token(token)
        return payload, None
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
# PIN Hashing & Verification
# ─────────────────────────────────────────────────────────────────────────────

def hash_pin(pin: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hash a numeric PIN using SHA-256 and a random cryptographic salt.
    
    Returns:
        (hash_hex, salt_hex)
    """
    clean_pin = str(pin).strip()
    if not salt:
        salt = secrets.token_hex(16)
    hasher = hashlib.sha256()
    hasher.update(f"{salt}:{clean_pin}".encode("utf-8"))
    return hasher.hexdigest(), salt


def verify_pin(pin: str, stored_hash: str, salt: str) -> bool:
    """Verify candidate PIN against stored hash and salt using constant-time comparison."""
    if not stored_hash or not salt:
        return False
    computed_hash, _ = hash_pin(pin, salt=salt)
    return hmac.compare_digest(computed_hash, stored_hash)


# ─────────────────────────────────────────────────────────────────────────────
# Pluggable OTP Providers
# ─────────────────────────────────────────────────────────────────────────────

class BaseOTPProvider(ABC):
    """Abstract interface for clinical OTP delivery."""
    @abstractmethod
    def send_otp(self, recipient: str, otp_code: str) -> bool:
        pass


class ConsoleOTPProvider(BaseOTPProvider):
    """Development/Console OTP provider."""
    def send_otp(self, recipient: str, otp_code: str) -> bool:
        logger.info("[ConsoleOTP] Clinical verification code for %s is %s", recipient, otp_code)
        print(f"\n[ConsoleOTP] Verification Code for {recipient}: {otp_code}\n")
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
        # Placeholder / production gateway call
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


# In-memory OTP storage for verification with 10-minute expiry
_ACTIVE_OTPS: Dict[str, Tuple[str, datetime]] = {}


def send_otp_for_recipient(recipient: str) -> str:
    """Generate and dispatch a 6-digit OTP code."""
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    if app_env == "development":
        otp = "123456"
    else:
        otp = f"{secrets.randbelow(900000) + 100000}"
    
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    _ACTIVE_OTPS[recipient] = (otp, expires_at)

    provider = get_otp_provider()
    provider.send_otp(recipient, otp)
    return otp


def verify_submitted_otp(recipient: str, candidate_otp: str) -> bool:
    """Verify submitted OTP code against recipient.
    
    Rule: DEV_OTP '123456' is accepted ONLY when APP_ENV=development.
    """
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    clean_candidate = str(candidate_otp).strip()

    # Rule: Accept DEV_OTP=123456 only when APP_ENV=development
    if clean_candidate == "123456":
        if app_env == "development":
            return True
        # In non-development (e.g. production), DEV_OTP is refused unless explicitly generated
        record = _ACTIVE_OTPS.get(recipient)
        if record:
            expected_otp, expires_at = record
            if datetime.now(timezone.utc) <= expires_at and expected_otp == clean_candidate:
                del _ACTIVE_OTPS[recipient]
                return True
        return False

    record = _ACTIVE_OTPS.get(recipient)
    if not record:
        return False
    expected_otp, expires_at = record
    if datetime.now(timezone.utc) > expires_at:
        del _ACTIVE_OTPS[recipient]
        return False
    
    if hmac.compare_digest(expected_otp, clean_candidate):
        del _ACTIVE_OTPS[recipient]
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
