"""Helper functions to reduce code duplication.

Common utility functions used across multiple modules
to improve maintainability and consistency.

MEDIUM PRIORITY FIX: Extracted duplicate logic.
"""

import os
import re
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from flask import g

logger = logging.getLogger(__name__)


# ============================================================================
# CROSS-ORGANIZATION ACCESS CONTROL
# ============================================================================

def check_cross_org_access(
    record: Dict[str, Any],
    caller_org: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """Check if caller has access to record (same organization).
    
    Args:
        record: Record dictionary with org_id or community_id
        caller_org: Caller's organization ID (defaults to g.org_id)
        
    Returns:
        (is_allowed, error_message) tuple
        
    Example:
        allowed, error = check_cross_org_access(record)
        if not allowed:
            return error_response(error, status_code=403)
    """
    if caller_org is None:
        caller_org = getattr(g, 'org_id', None)
    
    if not caller_org:
        return False, "Organization ID not found in request context"
    
    record_org = record.get("community_id") or record.get("org_id")
    
    if not record_org:
        return False, "Record does not have an associated organization"
    
    if record_org != caller_org:
        return False, "Cross-organization access forbidden: record belongs to different organization"
    
    return True, None


def check_worker_access(
    record: Dict[str, Any],
    user_id: Optional[str] = None,
    user_role: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """Check if field worker has access to their own record.
    
    Args:
        record: Record dictionary with scanned_by field
        user_id: User ID (defaults to g.user_id)
        user_role: User role (defaults to g.user_role)
        
    Returns:
        (is_allowed, error_message) tuple
    """
    if user_id is None:
        user_id = getattr(g, 'user_id', None)
    if user_role is None:
        user_role = getattr(g, 'user_role', None)
    
    # Only field workers have this restriction
    if user_role != "field_worker":
        return True, None
    
    scanned_by = record.get("scanned_by")
    if scanned_by and scanned_by != user_id:
        return False, "Field workers can only access their own records"
    
    return True, None


def enforce_access_control(
    record: Dict[str, Any],
    check_worker_isolation: bool = True
) -> Tuple[bool, Optional[str], Optional[int]]:
    """Comprehensive access control check.
    
    Args:
        record: Record to check access for
        check_worker_isolation: Whether to enforce worker isolation
        
    Returns:
        (is_allowed, error_message, status_code) tuple
        
    Example:
        allowed, error, status = enforce_access_control(record)
        if not allowed:
            return error_response(error, status_code=status)
    """
    # Check cross-org access
    allowed, error = check_cross_org_access(record)
    if not allowed:
        return False, error, 403
    
    # Check worker isolation if needed
    if check_worker_isolation:
        allowed, error = check_worker_access(record)
        if not allowed:
            # Return 404 instead of 403 for field workers (security by obscurity)
            return False, "Record not found", 404
    
    return True, None, None


# ============================================================================
# DATABASE PATH RESOLUTION
# ============================================================================

def get_database_path(db_path: Optional[str] = None) -> str:
    """Resolve database path from multiple sources.
    
    Priority:
    1. Provided db_path parameter
    2. Flask g.db_path
    3. DATABASE_PATH environment variable
    4. Default database path
    
    Args:
        db_path: Optional explicit path
        
    Returns:
        Resolved database path
    """
    if db_path:
        return db_path
    
    # Try Flask context
    try:
        from flask import has_app_context
        if has_app_context() and hasattr(g, 'db_path') and g.db_path:
            return g.db_path
    except Exception:
        pass
    
    # Try environment variable
    env_path = os.getenv("DATABASE_PATH")
    if env_path:
        return env_path
    
    # Use default
    from backend import database
    return database.DEFAULT_DB_PATH


# ============================================================================
# USER CONTEXT HELPERS
# ============================================================================

def get_current_user_info() -> Dict[str, Any]:
    """Get current user information from Flask context.
    
    Returns:
        Dictionary with user_id, role, org_id, name, email
    """
    return {
        "user_id": getattr(g, 'user_id', None),
        "role": getattr(g, 'user_role', None),
        "org_id": getattr(g, 'org_id', None),
        "name": getattr(g, 'current_user', {}).get('name'),
        "email": getattr(g, 'current_user', {}).get('email'),
    }


def require_role(allowed_roles: list) -> Tuple[bool, Optional[str]]:
    """Check if current user has required role.
    
    Args:
        allowed_roles: List of allowed role names
        
    Returns:
        (is_allowed, error_message) tuple
        
    Example:
        allowed, error = require_role(['admin', 'doctor'])
        if not allowed:
            return forbidden_response(error)
    """
    current_role = getattr(g, 'user_role', '').lower()
    allowed_roles_lower = [r.lower() for r in allowed_roles]
    
    if current_role not in allowed_roles_lower:
        return False, f"Insufficient permissions. Required roles: {', '.join(allowed_roles)}"
    
    return True, None


# ============================================================================
# DATA PARSING HELPERS
# ============================================================================

def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to integer.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Integer value or default
    """
    try:
        return int(float(value))
    except (ValueError, TypeError, AttributeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Float value or default
    """
    try:
        return float(value)
    except (ValueError, TypeError, AttributeError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """Safely convert value to boolean.
    
    Args:
        value: Value to convert (1, "1", "true", True, etc.)
        default: Default value if conversion fails
        
    Returns:
        Boolean value or default
    """
    if value is None:
        return default
    
    if isinstance(value, bool):
        return value
    
    if isinstance(value, (int, float)):
        return value != 0
    
    if isinstance(value, str):
        return value.lower().strip() in ('1', 'true', 'yes', 'on')
    
    return default


def extract_numbers(text: str) -> list:
    """Extract all numbers from text.
    
    Args:
        text: Text containing numbers
        
    Returns:
        List of number strings
        
    Example:
        >>> extract_numbers("BP: 120/80 mmHg")
        ['120', '80']
    """
    if not text:
        return []
    return re.findall(r'\d+\.?\d*', str(text))


def parse_blood_pressure(bp_str: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse blood pressure string into systolic and diastolic.
    
    Args:
        bp_str: Blood pressure string (e.g., "120/80")
        
    Returns:
        (systolic, diastolic) tuple, or (None, None) if invalid
        
    Example:
        >>> parse_blood_pressure("120/80")
        (120, 80)
    """
    if not bp_str or '/' not in str(bp_str):
        return None, None
    
    try:
        parts = str(bp_str).split('/')
        systolic = safe_int(parts[0])
        diastolic = safe_int(parts[1])
        
        if systolic > 0 and diastolic > 0:
            return systolic, diastolic
    except Exception as e:
        logger.debug("Failed to parse blood pressure '%s': %s", bp_str, e)
    
    return None, None


# ============================================================================
# TIMESTAMP HELPERS
# ============================================================================

def get_utc_now() -> datetime:
    """Get current UTC datetime.
    
    Returns:
        Timezone-aware UTC datetime
    """
    return datetime.now(timezone.utc)


def get_utc_timestamp() -> str:
    """Get current UTC timestamp as ISO string.
    
    Returns:
        ISO format timestamp string
    """
    return get_utc_now().isoformat()


def parse_timestamp(timestamp_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO timestamp string to datetime.
    
    Args:
        timestamp_str: ISO format timestamp
        
    Returns:
        Timezone-aware datetime or None if invalid
    """
    if not timestamp_str:
        return None
    
    try:
        dt = datetime.fromisoformat(timestamp_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError) as e:
        logger.debug("Failed to parse timestamp '%s': %s", timestamp_str, e)
        return None


# ============================================================================
# FILE HANDLING HELPERS
# ============================================================================

def get_file_extension(filename: str) -> str:
    """Get file extension from filename.
    
    Args:
        filename: Name of file
        
    Returns:
        Lowercase extension including dot (e.g., ".jpg")
    """
    return os.path.splitext(filename)[1].lower()


def is_valid_image_extension(filename: str) -> bool:
    """Check if filename has valid image extension.
    
    Args:
        filename: Name of file
        
    Returns:
        True if valid image extension
    """
    from backend.config.constants import ALLOWED_IMAGE_EXTENSIONS
    ext = get_file_extension(filename)
    return ext in ALLOWED_IMAGE_EXTENSIONS


def generate_unique_filename(prefix: str = "", extension: str = ".jpg") -> str:
    """Generate unique filename with prefix and extension.
    
    Args:
        prefix: Filename prefix
        extension: File extension (with or without dot)
        
    Returns:
        Unique filename
        
    Example:
        >>> generate_unique_filename("camp_001_page1", ".jpg")
        'camp_001_page1_a3b5c7d9.jpg'
    """
    import secrets
    
    if not extension.startswith('.'):
        extension = '.' + extension
    
    random_suffix = secrets.token_hex(4)
    
    if prefix:
        return f"{prefix}_{random_suffix}{extension}"
    else:
        return f"{random_suffix}{extension}"


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def is_valid_uuid(value: str) -> bool:
    """Check if string is valid UUID.
    
    Args:
        value: String to check
        
    Returns:
        True if valid UUID format
    """
    import re
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(str(value)))


def is_valid_email(email: str) -> bool:
    """Quick email format validation.
    
    Args:
        email: Email address to check
        
    Returns:
        True if valid format
    """
    if not email:
        return False
    
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    return bool(email_pattern.match(str(email)))


def is_valid_phone(phone: str) -> bool:
    """Quick phone number validation (10-15 digits).
    
    Args:
        phone: Phone number to check
        
    Returns:
        True if valid format
    """
    if not phone:
        return False
    
    # Remove non-digits
    digits = re.sub(r'\D', '', str(phone))
    return 10 <= len(digits) <= 15


# ============================================================================
# STRING HELPERS
# ============================================================================

def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncated
        
    Returns:
        Truncated string
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def mask_sensitive_data(value: str, visible_chars: int = 4) -> str:
    """Mask sensitive data for logging.
    
    Args:
        value: Value to mask
        visible_chars: Number of characters to show at end
        
    Returns:
        Masked string
        
    Example:
        >>> mask_sensitive_data("1234567890", 4)
        '******7890'
    """
    if not value or len(value) <= visible_chars:
        return "***"
    
    return '*' * (len(value) - visible_chars) + value[-visible_chars:]


# ============================================================================
# DICTIONARY HELPERS
# ============================================================================

def deep_get(dictionary: dict, *keys, default=None):
    """Safely get nested dictionary value.
    
    Args:
        dictionary: Dictionary to search
        *keys: Nested keys to traverse
        default: Default value if key not found
        
    Returns:
        Value at nested key or default
        
    Example:
        >>> data = {"user": {"profile": {"name": "John"}}}
        >>> deep_get(data, "user", "profile", "name")
        'John'
    """
    for key in keys:
        if isinstance(dictionary, dict):
            dictionary = dictionary.get(key, default)
        else:
            return default
    return dictionary


def remove_none_values(data: dict) -> dict:
    """Remove keys with None values from dictionary.
    
    Args:
        data: Input dictionary
        
    Returns:
        Dictionary without None values
    """
    return {k: v for k, v in data.items() if v is not None}


def merge_dicts(*dicts: dict) -> dict:
    """Merge multiple dictionaries (later ones override earlier).
    
    Args:
        *dicts: Dictionaries to merge
        
    Returns:
        Merged dictionary
    """
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result
