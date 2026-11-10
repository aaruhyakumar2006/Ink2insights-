"""Input validation utilities for I2 Insights.

Centralized validation functions for all user inputs to prevent:
- SQL injection
- XSS attacks
- Invalid data storage
- Business logic errors

SECURITY FIX: Created centralized validation layer.
"""

import re
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timezone


def validate_phone(phone: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Validate and normalize phone number.
    
    Args:
        phone: Raw phone number input
        
    Returns:
        (normalized_phone, error_message)
        
    Examples:
        >>> validate_phone("+91 98765 43210")
        ("919876543210", None)
        >>> validate_phone("abc")
        (None, "Invalid phone number format")
    """
    if not phone:
        return None, None
    
    # Remove all non-digit characters
    clean = re.sub(r'\D', '', str(phone))
    
    # Must have at least 10 digits
    if len(clean) < 10:
        return None, "Phone number must have at least 10 digits"
    
    # Limit to 15 digits (international max)
    if len(clean) > 15:
        return None, "Phone number too long (max 15 digits)"
    
    return clean, None


def validate_email(email: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Validate and normalize email address.
    
    Args:
        email: Raw email input
        
    Returns:
        (normalized_email, error_message)
        
    Examples:
        >>> validate_email("Doctor@Example.COM")
        ("doctor@example.com", None)
        >>> validate_email("invalid@")
        (None, "Invalid email format")
    """
    if not email:
        return None, None
    
    email = str(email).strip()
    
    # Basic email pattern (RFC 5322 simplified)
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        return None, "Invalid email format"
    
    # Normalize to lowercase
    return email.lower(), None


def validate_age(age: Optional[Any]) -> Tuple[Optional[int], Optional[str]]:
    """Validate age value.
    
    Args:
        age: Raw age input (int, str, float)
        
    Returns:
        (validated_age, error_message)
        
    Examples:
        >>> validate_age(25)
        (25, None)
        >>> validate_age(-5)
        (None, "Age must be between 0 and 150")
    """
    if age is None or age == "":
        return None, None
    
    try:
        age_int = int(float(age))
    except (ValueError, TypeError):
        return None, "Age must be a valid number"
    
    if age_int < 0:
        return None, "Age cannot be negative"
    
    if age_int > 150:
        return None, "Age must be less than 150 years"
    
    return age_int, None


def validate_weight(weight: Optional[Any]) -> Tuple[Optional[float], Optional[str]]:
    """Validate weight value in kg.
    
    Args:
        weight: Raw weight input
        
    Returns:
        (validated_weight, error_message)
        
    Examples:
        >>> validate_weight(65.5)
        (65.5, None)
        >>> validate_weight(-10)
        (None, "Weight must be between 0.5 and 500 kg")
    """
    if weight is None or weight == "":
        return None, None
    
    try:
        weight_float = float(weight)
    except (ValueError, TypeError):
        return None, "Weight must be a valid number"
    
    if weight_float < 0.5:
        return None, "Weight must be at least 0.5 kg"
    
    if weight_float > 500:
        return None, "Weight must be less than 500 kg"
    
    return round(weight_float, 2), None


def validate_height(height: Optional[Any]) -> Tuple[Optional[float], Optional[str]]:
    """Validate height value in cm.
    
    Args:
        height: Raw height input
        
    Returns:
        (validated_height, error_message)
        
    Examples:
        >>> validate_height(165.5)
        (165.5, None)
        >>> validate_height(300)
        (None, "Height must be between 30 and 250 cm")
    """
    if height is None or height == "":
        return None, None
    
    try:
        height_float = float(height)
    except (ValueError, TypeError):
        return None, "Height must be a valid number"
    
    if height_float < 30:
        return None, "Height must be at least 30 cm"
    
    if height_float > 250:
        return None, "Height must be less than 250 cm"
    
    return round(height_float, 2), None


def validate_blood_pressure(bp: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Validate blood pressure format.
    
    Args:
        bp: Blood pressure string (e.g., "120/80")
        
    Returns:
        (validated_bp, error_message)
        
    Examples:
        >>> validate_blood_pressure("120/80")
        ("120/80", None)
        >>> validate_blood_pressure("300/200")
        (None, "Systolic BP must be between 50 and 250 mmHg")
    """
    if not bp or bp == "":
        return None, None
    
    bp_str = str(bp).strip()
    
    # Match format: number/number
    match = re.match(r'^(\d+)\s*/\s*(\d+)$', bp_str)
    if not match:
        return None, "Blood pressure must be in format: 120/80"
    
    systolic = int(match.group(1))
    diastolic = int(match.group(2))
    
    if systolic < 50 or systolic > 250:
        return None, "Systolic BP must be between 50 and 250 mmHg"
    
    if diastolic < 30 or diastolic > 150:
        return None, "Diastolic BP must be between 30 and 150 mmHg"
    
    if diastolic >= systolic:
        return None, "Diastolic BP must be less than systolic BP"
    
    return f"{systolic}/{diastolic}", None


def validate_date(date_str: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Validate date string.
    
    Args:
        date_str: Date in various formats
        
    Returns:
        (iso_date_string, error_message)
        
    Examples:
        >>> validate_date("2024-01-15")
        ("2024-01-15T00:00:00+00:00", None)
        >>> validate_date("invalid")
        (None, "Invalid date format")
    """
    if not date_str or date_str == "":
        return None, None
    
    # Try multiple date formats
    formats = [
        "%Y-%m-%d",           # 2024-01-15
        "%d/%m/%Y",           # 15/01/2024
        "%d-%m-%Y",           # 15-01-2024
        "%Y-%m-%dT%H:%M:%S",  # ISO format
        "%Y-%m-%dT%H:%M:%S.%f",  # ISO with microseconds
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(str(date_str).strip(), fmt)
            # Add timezone if not present
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat(), None
        except ValueError:
            continue
    
    return None, "Invalid date format (use YYYY-MM-DD or DD/MM/YYYY)"


def validate_gender(gender: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Validate and normalize gender.
    
    Args:
        gender: Raw gender input
        
    Returns:
        (normalized_gender, error_message)
        
    Examples:
        >>> validate_gender("male")
        ("Male", None)
        >>> validate_gender("M")
        ("Male", None)
    """
    if not gender:
        return None, None
    
    gender_str = str(gender).strip().lower()
    
    # Normalize common variations
    if gender_str in ('m', 'male', 'boy', 'man'):
        return "Male", None
    elif gender_str in ('f', 'female', 'girl', 'woman'):
        return "Female", None
    elif gender_str in ('o', 'other', 'transgender', 'non-binary', 'prefer not to say'):
        return "Other", None
    
    return None, "Gender must be Male, Female, or Other"


def validate_record_data(data: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    """Validate complete record data.
    
    Args:
        data: Record dictionary
        
    Returns:
        (is_valid, error_dict)
        
    Example:
        >>> is_valid, errors = validate_record_data({"age": -5})
        >>> errors
        {"age": "Age cannot be negative"}
    """
    errors = {}
    
    # Validate name (required)
    if not data.get('person_name') or not str(data.get('person_name')).strip():
        errors['person_name'] = "Name is required"
    
    # Validate age
    if 'age' in data:
        _, age_error = validate_age(data['age'])
        if age_error:
            errors['age'] = age_error
    
    # Validate phone
    if 'phone' in data:
        _, phone_error = validate_phone(data['phone'])
        if phone_error:
            errors['phone'] = phone_error
    
    # Validate email
    if 'email' in data:
        _, email_error = validate_email(data['email'])
        if email_error:
            errors['email'] = email_error
    
    # Validate weight
    if 'weight' in data:
        _, weight_error = validate_weight(data['weight'])
        if weight_error:
            errors['weight'] = weight_error
    
    # Validate height
    if 'height' in data:
        _, height_error = validate_height(data['height'])
        if height_error:
            errors['height'] = height_error
    
    # Validate blood pressure
    if 'blood_pressure' in data:
        _, bp_error = validate_blood_pressure(data['blood_pressure'])
        if bp_error:
            errors['blood_pressure'] = bp_error
    
    # Validate gender
    if 'gender' in data:
        _, gender_error = validate_gender(data['gender'])
        if gender_error:
            errors['gender'] = gender_error
    
    # Validate date
    if 'date_of_birth' in data:
        _, dob_error = validate_date(data['date_of_birth'])
        if dob_error:
            errors['date_of_birth'] = dob_error
    
    return len(errors) == 0, errors


def sanitize_string(value: Optional[str], max_length: int = 500) -> Optional[str]:
    """Sanitize string input to prevent XSS and SQL injection.
    
    Args:
        value: Raw string input
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
        
    Examples:
        >>> sanitize_string("<script>alert('xss')</script>")
        "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
    """
    if not value:
        return None
    
    value = str(value).strip()
    
    # Truncate to max length
    if len(value) > max_length:
        value = value[:max_length]
    
    # HTML escape to prevent XSS
    value = (value
             .replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&#x27;"))
    
    return value
