"""Error handler — classifies errors and determines retry vs DLQ vs abort.

Every error in the pipeline passes through this module. It categorizes the
error, decides the action, and provides structured error payloads for the DLQ.
"""

from enum import Enum


class ErrorCategory(str, Enum):
    """Error categories with distinct handling policies."""
    TRANSIENT = "transient"          # Retry with backoff
    FATAL_REJECT = "fatal_reject"    # DLQ, never retry
    FATAL_ABORT = "fatal_abort"      # Crash, operator intervention


class ErrorAction(str, Enum):
    """Actions the pipeline can take in response to an error."""
    RETRY = "retry"
    DLQ = "dlq"
    ABORT = "abort"


# Known error patterns and their categories
ERROR_PATTERNS: dict[str, dict] = {
    # API errors
    "timeout": {"category": ErrorCategory.TRANSIENT, "message": "API request timed out"},
    "rate_limit": {"category": ErrorCategory.TRANSIENT, "message": "Rate limited by API"},
    "429": {"category": ErrorCategory.TRANSIENT, "message": "Rate limited (HTTP 429)"},
    "502": {"category": ErrorCategory.TRANSIENT, "message": "Bad gateway (HTTP 502)"},
    "503": {"category": ErrorCategory.TRANSIENT, "message": "Service unavailable (HTTP 503)"},

    # Validation errors
    "invalid_prompt": {"category": ErrorCategory.FATAL_REJECT, "message": "Prompt failed validation"},
    "invalid_age_group": {"category": ErrorCategory.FATAL_REJECT, "message": "Invalid age group"},
    "invalid_payload": {"category": ErrorCategory.FATAL_REJECT, "message": "Message payload is invalid"},

    # Infrastructure errors
    "connection_refused": {"category": ErrorCategory.TRANSIENT, "message": "Connection refused"},
    "disk_full": {"category": ErrorCategory.FATAL_ABORT, "message": "Disk is full"},
    "permission_denied": {"category": ErrorCategory.FATAL_ABORT, "message": "Permission denied"},
    "queue_not_found": {"category": ErrorCategory.FATAL_ABORT, "message": "Queue directory not found"},
}


def classify_error(error: Exception | str, context: str = "") -> ErrorAction:
    """Classify an error and return the appropriate action.

    Args:
        error: The exception or error message string.
        context: Additional context (e.g., the stage name).

    Returns:
        ErrorAction: RETRY, DLQ, or ABORT.
    """
    error_str = str(error).lower() if isinstance(error, Exception) else error.lower()

    for pattern, info in ERROR_PATTERNS.items():
        if pattern in error_str:
            category = info["category"]
            if category == ErrorCategory.TRANSIENT:
                return ErrorAction.RETRY
            elif category == ErrorCategory.FATAL_REJECT:
                return ErrorAction.DLQ
            elif category == ErrorCategory.FATAL_ABORT:
                return ErrorAction.ABORT

    # Default: transient (safe default for unknown API errors)
    return ErrorAction.RETRY


def should_retry(retry_count: int, max_retries: int = 3) -> bool:
    """Determine if a message should be retried based on retry count."""
    return retry_count < max_retries


def get_backoff_delay(retry_count: int, base_delay: float = 2.0, max_delay: float = 60.0) -> float:
    """Calculate exponential backoff delay in seconds.

    Formula: min(base_delay * 2^retry_count, max_delay)
    """
    delay = base_delay * (2 ** retry_count)
    return min(delay, max_delay)


def build_error_payload(
    request_id: str,
    error: Exception | str,
    original_message: dict,
    retry_count: int = 0,
) -> dict:
    """Build a structured error payload for the DLQ."""
    error_str = str(error) if isinstance(error, Exception) else error
    category = classify_error(error_str)

    category_map = {
        ErrorAction.RETRY: "transient",
        ErrorAction.DLQ: "fatal_reject",
        ErrorAction.ABORT: "fatal_abort",
    }

    import uuid
    from datetime import datetime, timezone

    return {
        "request_id": request_id,
        "error": {
            "code": "PIPELINE_ERROR",
            "message": error_str,
            "category": category_map.get(category, "transient"),
        },
        "trace": str(uuid.uuid4()),
        "original_message": original_message,
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": retry_count,
    }
