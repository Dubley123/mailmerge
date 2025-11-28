from datetime import datetime, timezone

def get_utc_now():
    """
    Get current UTC time with timezone information.
    This replaces datetime.utcnow() which is deprecated.
    """
    return datetime.now(timezone.utc)

def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware UTC"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
