"""Standardized API response utilities.

Provides consistent response formats across all API endpoints
to improve client error handling and API consistency.

MEDIUM PRIORITY FIX: Unified error response format.
"""

from typing import Any, Dict, Optional, List
from datetime import datetime, timezone
from flask import jsonify, Response


def success_response(
    data: Any = None,
    message: Optional[str] = None,
    status_code: int = 200,
    **kwargs
) -> tuple[Response, int]:
    """Create standardized success response.
    
    Args:
        data: Response data (dict, list, or any JSON-serializable type)
        message: Optional success message
        status_code: HTTP status code (default: 200)
        **kwargs: Additional fields to include in response
        
    Returns:
        (JSON response, status_code) tuple
        
    Example:
        return success_response(
            data={"record_id": "123"},
            message="Record created successfully"
        )
    """
    response = {
        "success": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    if message:
        response["message"] = message
    
    if data is not None:
        response["data"] = data
    
    # Add any additional fields
    response.update(kwargs)
    
    return jsonify(response), status_code


def error_response(
    message: str,
    status_code: int = 400,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    field_errors: Optional[Dict[str, str]] = None,
    **kwargs
) -> tuple[Response, int]:
    """Create standardized error response.
    
    Args:
        message: Human-readable error message
        status_code: HTTP status code (default: 400)
        error_code: Machine-readable error code (e.g., "VALIDATION_ERROR")
        details: Additional error details
        field_errors: Field-specific validation errors
        **kwargs: Additional fields to include in response
        
    Returns:
        (JSON response, status_code) tuple
        
    Example:
        return error_response(
            message="Invalid input data",
            status_code=400,
            error_code="VALIDATION_ERROR",
            field_errors={"email": "Invalid email format"}
        )
    """
    response = {
        "success": False,
        "error": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    if error_code:
        response["error_code"] = error_code
    
    if details:
        response["details"] = details
    
    if field_errors:
        response["field_errors"] = field_errors
    
    # Add any additional fields
    response.update(kwargs)
    
    return jsonify(response), status_code


def validation_error_response(
    field_errors: Dict[str, str],
    message: str = "Validation failed",
    **kwargs
) -> tuple[Response, int]:
    """Create validation error response.
    
    Args:
        field_errors: Dictionary of field names to error messages
        message: Overall validation error message
        **kwargs: Additional fields
        
    Returns:
        (JSON response, 400) tuple
        
    Example:
        return validation_error_response(
            field_errors={
                "age": "Age cannot be negative",
                "phone": "Phone number must have 10 digits"
            }
        )
    """
    return error_response(
        message=message,
        status_code=400,
        error_code="VALIDATION_ERROR",
        field_errors=field_errors,
        **kwargs
    )


def not_found_response(
    resource: str = "Resource",
    resource_id: Optional[str] = None,
    **kwargs
) -> tuple[Response, int]:
    """Create not found error response.
    
    Args:
        resource: Type of resource (e.g., "Record", "User")
        resource_id: ID of the resource that wasn't found
        **kwargs: Additional fields
        
    Returns:
        (JSON response, 404) tuple
        
    Example:
        return not_found_response("Record", record_id="123")
    """
    message = f"{resource} not found"
    if resource_id:
        message += f": {resource_id}"
    
    return error_response(
        message=message,
        status_code=404,
        error_code="NOT_FOUND",
        resource_type=resource,
        resource_id=resource_id,
        **kwargs
    )


def unauthorized_response(
    message: str = "Authentication required",
    **kwargs
) -> tuple[Response, int]:
    """Create unauthorized error response.
    
    Args:
        message: Error message
        **kwargs: Additional fields
        
    Returns:
        (JSON response, 401) tuple
    """
    return error_response(
        message=message,
        status_code=401,
        error_code="UNAUTHORIZED",
        **kwargs
    )


def forbidden_response(
    message: str = "Insufficient permissions",
    required_role: Optional[str] = None,
    **kwargs
) -> tuple[Response, int]:
    """Create forbidden error response.
    
    Args:
        message: Error message
        required_role: Role required for this operation
        **kwargs: Additional fields
        
    Returns:
        (JSON response, 403) tuple
    """
    details = {}
    if required_role:
        details["required_role"] = required_role
    
    return error_response(
        message=message,
        status_code=403,
        error_code="FORBIDDEN",
        details=details if details else None,
        **kwargs
    )


def conflict_response(
    message: str = "Resource conflict",
    conflict_type: Optional[str] = None,
    **kwargs
) -> tuple[Response, int]:
    """Create conflict error response.
    
    Args:
        message: Error message
        conflict_type: Type of conflict (e.g., "DUPLICATE", "LOCKED")
        **kwargs: Additional fields
        
    Returns:
        (JSON response, 409) tuple
        
    Example:
        return conflict_response(
            message="Record is locked by another user",
            conflict_type="LOCKED",
            locked_by="Dr. Smith"
        )
    """
    return error_response(
        message=message,
        status_code=409,
        error_code=conflict_type or "CONFLICT",
        **kwargs
    )


def rate_limit_response(
    retry_after: Optional[int] = None,
    limit: Optional[int] = None,
    **kwargs
) -> tuple[Response, int]:
    """Create rate limit error response.
    
    Args:
        retry_after: Seconds until rate limit resets
        limit: Rate limit threshold
        **kwargs: Additional fields
        
    Returns:
        (JSON response, 429) tuple
    """
    message = "Rate limit exceeded. Please try again later"
    if retry_after:
        message += f" (retry after {retry_after} seconds)"
    
    details = {}
    if retry_after:
        details["retry_after"] = retry_after
    if limit:
        details["limit"] = limit
    
    return error_response(
        message=message,
        status_code=429,
        error_code="RATE_LIMIT_EXCEEDED",
        details=details if details else None,
        **kwargs
    )


def server_error_response(
    message: str = "Internal server error",
    error_id: Optional[str] = None,
    **kwargs
) -> tuple[Response, int]:
    """Create internal server error response.
    
    Args:
        message: Error message (generic in production)
        error_id: Unique error ID for tracking
        **kwargs: Additional fields
        
    Returns:
        (JSON response, 500) tuple
        
    Example:
        import uuid
        error_id = str(uuid.uuid4())
        logger.error("Database error: %s", error, extra={"error_id": error_id})
        return server_error_response(error_id=error_id)
    """
    details = {}
    if error_id:
        details["error_id"] = error_id
        message += f" (Error ID: {error_id})"
    
    return error_response(
        message=message,
        status_code=500,
        error_code="INTERNAL_ERROR",
        details=details if details else None,
        **kwargs
    )


def paginated_response(
    data: List[Any],
    page: int,
    limit: int,
    total: int,
    message: Optional[str] = None,
    **kwargs
) -> tuple[Response, int]:
    """Create paginated success response.
    
    Args:
        data: List of items for current page
        page: Current page number (1-indexed)
        limit: Items per page
        total: Total number of items
        message: Optional message
        **kwargs: Additional fields
        
    Returns:
        (JSON response, 200) tuple
        
    Example:
        return paginated_response(
            data=records,
            page=1,
            limit=50,
            total=250
        )
    """
    total_pages = (total + limit - 1) // limit if limit > 0 else 1
    
    pagination = {
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }
    
    return success_response(
        data=data,
        message=message,
        pagination=pagination,
        **kwargs
    )


# Common HTTP status code helpers
def created_response(data: Any, message: str = "Created successfully", **kwargs):
    """HTTP 201 Created response."""
    return success_response(data=data, message=message, status_code=201, **kwargs)


def accepted_response(message: str = "Request accepted", **kwargs):
    """HTTP 202 Accepted response."""
    return success_response(message=message, status_code=202, **kwargs)


def no_content_response():
    """HTTP 204 No Content response."""
    return '', 204


def bad_request_response(message: str, **kwargs):
    """HTTP 400 Bad Request response."""
    return error_response(message=message, status_code=400, error_code="BAD_REQUEST", **kwargs)


def unprocessable_response(message: str, **kwargs):
    """HTTP 422 Unprocessable Entity response."""
    return error_response(message=message, status_code=422, error_code="UNPROCESSABLE", **kwargs)
