"""Application constants and configuration values.

Centralizes all magic numbers, thresholds, and configuration constants
to improve maintainability and prevent inconsistencies.

MEDIUM PRIORITY FIX: Extracted magic numbers from across the codebase.
"""

# ============================================================================
# AUTHENTICATION & SECURITY
# ============================================================================

# JWT Token Configuration
JWT_EXPIRY_HOURS = 12
JWT_ALGORITHM = "HS256"
MIN_JWT_SECRET_LENGTH = 32  # bytes

# Account Lockout
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# OTP Configuration
OTP_EXPIRY_MINUTES = 5
OTP_LENGTH = 6
DEV_OTP_CODE = "123456"  # Only accepted in development mode

# Session Configuration
SESSION_TIMEOUT_MINUTES = 30


# ============================================================================
# FILE UPLOAD & STORAGE
# ============================================================================

# File Size Limits
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_FILE_SIZE_MB = 10
MAX_IMAGE_SIZE_BYTES = 15 * 1024 * 1024  # 15MB for high-res photos

# Image Processing
IMAGE_MAX_EDGE_PX = 1568  # Maximum dimension for processed images
IMAGE_MAX_BYTES = 1000000  # 1MB for compressed images
IMAGE_QUALITY_JPEG = 85  # JPEG compression quality (0-100)
IMAGE_RESIZE_WIDTH = 1920  # Max width for mobile uploads

# Allowed File Types
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif']
ALLOWED_MIME_TYPES = {
    'image/jpeg', 'image/jpg', 'image/png', 'image/webp',
    'image/heic', 'image/heif', 'image/heic-sequence', 'image/heif-sequence'
}


# ============================================================================
# DATABASE & PAGINATION
# ============================================================================

# Query Limits
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500
DEFAULT_RECORD_LIMIT = 100

# Timeouts
DATABASE_TIMEOUT_SECONDS = 30.0
QUERY_TIMEOUT_SECONDS = 60

# Retention
RETENTION_MONTHS = 12
BACKUP_RETENTION_DAYS = 90


# ============================================================================
# RATE LIMITING
# ============================================================================

# Per-user Rate Limits
RATE_LIMIT_USER_PER_MINUTE = 10
RATE_LIMIT_USER_PER_HOUR = 100

# Per-organization Rate Limits
RATE_LIMIT_ORG_PER_MINUTE = 60
RATE_LIMIT_ORG_PER_HOUR = 1000

# API-specific Limits
RATE_LIMIT_UPLOAD_PER_MINUTE = 5
RATE_LIMIT_AUTH_PER_MINUTE = 3


# ============================================================================
# MEDICAL DATA VALIDATION
# ============================================================================

# Age Ranges
MIN_AGE = 0
MAX_AGE = 150
PAEDIATRIC_AGE_THRESHOLD = 18  # Below this is considered pediatric

# Weight Ranges (kg)
MIN_WEIGHT_KG = 0.5
MAX_WEIGHT_KG = 500.0

# Height Ranges (cm)
MIN_HEIGHT_CM = 30.0
MAX_HEIGHT_CM = 250.0

# Blood Pressure Ranges (mmHg)
MIN_SYSTOLIC_BP = 50
MAX_SYSTOLIC_BP = 250
MIN_DIASTOLIC_BP = 30
MAX_DIASTOLIC_BP = 150

# BMI Classification Thresholds
BMI_UNDERWEIGHT = 18.5
BMI_NORMAL = 22.9
BMI_PRE_OBESE = 24.9
BMI_OVERWEIGHT = 29.9
# Above 29.9 is Obese

# Blood Pressure Classification (mmHg)
BP_NORMAL_SYSTOLIC = 120
BP_NORMAL_DIASTOLIC = 80
BP_ELEVATED_SYSTOLIC = 130
BP_STAGE1_SYSTOLIC = 140
BP_STAGE1_DIASTOLIC = 90
BP_STAGE2_SYSTOLIC = 180
BP_STAGE2_DIASTOLIC = 120


# ============================================================================
# AI & QUALITY THRESHOLDS
# ============================================================================

# AI Provider Settings
AI_MAX_OUTPUT_TOKENS = 4000
AI_TIMEOUT_SECONDS = 30
AI_MAX_RETRIES = 2

# Quality Assessment Thresholds
QUALITY_BLUR_MIN = 40.0  # Minimum acceptable blur score
QUALITY_DARK_MAX = 75.0  # Maximum darkness threshold
QUALITY_GLARE_MAX = 12.0  # Maximum glare percentage
MIN_BRIGHTNESS = 50
MAX_BRIGHTNESS = 200

# Confidence Thresholds
FLAG_CONFIDENCE = 0.8  # Threshold for flagging uncertain fields
FLAG_CONFIDENCE_MEASURE = 0.9  # Higher threshold for measurements
MIN_CONFIDENCE_SCORE = 0.6  # Minimum acceptable confidence


# ============================================================================
# RECORD LOCKING & CONCURRENCY
# ============================================================================

# Record Lock Duration
RECORD_LOCK_TIMEOUT_MINUTES = 10
RESERVATION_EXPIRY_DAYS = 7

# Concurrent Access
MAX_CONCURRENT_REVIEWS = 3
MAX_CONCURRENT_UPLOADS = 5


# ============================================================================
# BILLING & QUOTAS
# ============================================================================

# Paper Quota Defaults
DEFAULT_PAPERS_INCLUDED = 100
DEFAULT_PAPERS_ADDON = 0
DEFAULT_PAPERS_ROLLOVER = 0
OVERAGE_BUFFER_PERCENT = 5  # 5% buffer over quota

# Pricing (USD)
PRICE_IN_USD_PER_MILLION = 1.50
PRICE_OUT_USD_PER_MILLION = 7.50
FALLBACK_PRICE_IN_USD_PER_MILLION = 2.00
FALLBACK_PRICE_OUT_USD_PER_MILLION = 12.00

# Currency
USD_TO_INR = 97  # Exchange rate
GST_RATE = 0.18  # 18% GST


# ============================================================================
# CAMP & ORGANIZATION DEFAULTS
# ============================================================================

# Default Organization
DEFAULT_ORG_ID = "org_default"
DEFAULT_COMMUNITY_ID = "default_community"
DEFAULT_CAMP_ID = "default_camp"

# Invite Code
INVITE_CODE_LENGTH = 8
INVITE_CODE_EXPIRY_DAYS = 90


# ============================================================================
# NOTIFICATION & ALERTS
# ============================================================================

# Alert Thresholds
HIGH_BMI_ALERT_THRESHOLD = 30.0  # Obese Class II
HYPERTENSION_CRISIS_SYSTOLIC = 180
HYPERTENSION_CRISIS_DIASTOLIC = 120

# Notification Settings
MAX_NOTIFICATION_RETRIES = 3
NOTIFICATION_TIMEOUT_SECONDS = 10


# ============================================================================
# LOGGING & MONITORING
# ============================================================================

# Log Levels
LOG_LEVEL_DEV = "DEBUG"
LOG_LEVEL_PROD = "INFO"

# Log Rotation
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB per log file
LOG_BACKUP_COUNT = 5  # Keep 5 backup files

# Metrics
METRICS_COLLECTION_INTERVAL_SECONDS = 60
SLOW_QUERY_THRESHOLD_MS = 1000  # Log queries taking > 1s


# ============================================================================
# FEATURE FLAGS
# ============================================================================

# Feature Toggles
ENABLE_SUPABASE_SYNC = True
ENABLE_AI_EXTRACTION = True
ENABLE_QUALITY_CHECKS = True
ENABLE_RATE_LIMITING = True
ENABLE_AUDIT_LOGGING = True

# Demo Mode
DEMO_MODE_ENABLED = False  # Set via environment variable


# ============================================================================
# API VERSIONING
# ============================================================================

API_VERSION = "v1"
API_PREFIX = "/api"
SUPPORTED_API_VERSIONS = ["v1"]


# ============================================================================
# ERROR MESSAGES
# ============================================================================

# Standard Error Messages
ERROR_RECORD_NOT_FOUND = "Record not found"
ERROR_UNAUTHORIZED = "Authentication required"
ERROR_FORBIDDEN = "Insufficient permissions"
ERROR_INVALID_INPUT = "Invalid input data"
ERROR_FILE_TOO_LARGE = "File size exceeds maximum limit"
ERROR_RATE_LIMIT = "Rate limit exceeded. Please try again later"
ERROR_SERVER_ERROR = "Internal server error"

# Success Messages
SUCCESS_RECORD_CREATED = "Record created successfully"
SUCCESS_RECORD_UPDATED = "Record updated successfully"
SUCCESS_RECORD_DELETED = "Record deleted successfully"
SUCCESS_FILE_UPLOADED = "File uploaded successfully"


# ============================================================================
# DEVELOPMENT & TESTING
# ============================================================================

# Test Data
TEST_PHONE_NUMBER = "9876543210"
TEST_EMAIL = "test@example.com"
TEST_CAMP_ID = "test_camp_001"

# Development Ports
DEFAULT_BACKEND_PORT = 5001
DEFAULT_FRONTEND_PORT = 3000
DEFAULT_MOBILE_PORT = 19006
