import os
from datetime import datetime, timezone

TS_FILE = os.path.join(os.path.dirname(__file__), '.last_email_fetch_ts')


def read_last_fetch_timestamp() -> datetime | None:
    """Read the last fetch timestamp (UTC) from file. Returns None if not present."""
    try:
        if not os.path.exists(TS_FILE):
            return None
        with open(TS_FILE, 'r', encoding='utf-8') as f:
            s = f.read().strip()
            if not s:
                return None
            # Parse ISO format
            return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None


def write_last_fetch_timestamp(dt: datetime) -> None:
    """Write the provided datetime (should be tz-aware) to file in ISO format (UTC)."""
    try:
        if dt.tzinfo is None:
            # assume UTC if naive
            dt = dt.replace(tzinfo=timezone.utc)
        dt_utc = dt.astimezone(timezone.utc)
        with open(TS_FILE, 'w', encoding='utf-8') as f:
            f.write(dt_utc.isoformat())
    except Exception:
        # best-effort; do not raise in scheduler
        pass
