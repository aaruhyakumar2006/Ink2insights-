"""Configuration module for I2 Insights backend."""

from .constants import *

__all__ = [
    # Authentication
    'JWT_EXPIRY_HOURS',
    'MAX_LOGIN_ATTEMPTS',
    'LOCKOUT_DURATION_MINUTES',
    'OTP_EXPIRY_MINUTES',
    
    # File Upload
    'MAX_FILE_SIZE_BYTES',
    'MAX_FILE_SIZE_MB',
    'ALLOWED_IMAGE_EXTENSIONS',
    'ALLOWED_MIME_TYPES',
    
    # Database
    'DEFAULT_PAGE_SIZE',
    'MAX_PAGE_SIZE',
    
    # Medical Validation
    'MIN_AGE',
    'MAX_AGE',
    'PAEDIATRIC_AGE_THRESHOLD',
    'MIN_WEIGHT_KG',
    'MAX_WEIGHT_KG',
    'MIN_HEIGHT_CM',
    'MAX_HEIGHT_CM',
    
    # Quality Thresholds
    'QUALITY_BLUR_MIN',
    'FLAG_CONFIDENCE',
    
    # Error Messages
    'ERROR_RECORD_NOT_FOUND',
    'ERROR_UNAUTHORIZED',
    'ERROR_FORBIDDEN',
]
