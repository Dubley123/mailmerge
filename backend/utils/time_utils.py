from datetime import datetime, timezone, timedelta

# Define Beijing Timezone (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8), name='Asia/Shanghai')

def get_utc_now():
    """
    Get current time with timezone information (Beijing Time).
    NOTE: Function name kept for compatibility, but returns Beijing Time (UTC+8).
    """
    return datetime.now(BEIJING_TZ)

def ensure_utc(dt: datetime) -> datetime:
    """
    Ensure datetime is timezone-aware (Beijing Time).
    If naive, assume it is already in Beijing time.
    NOTE: Function name kept for compatibility, but converts to Beijing Time (UTC+8).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=BEIJING_TZ)
    return dt.astimezone(BEIJING_TZ)
