import os
from datetime import datetime
from backend.utils.time_utils import ensure_utc

TS_FILE = os.path.join(os.path.dirname(__file__), '.last_email_fetch_ts')


def read_last_fetch_timestamp() -> datetime | None:
    """Read the last fetch timestamp from file. Returns None if not present."""
    try:
        if not os.path.exists(TS_FILE):
            return None
        with open(TS_FILE, 'r', encoding='utf-8') as f:
            s = f.read().strip()
            if not s:
                return None
            # Parse ISO format and ensure it is treated as Beijing Time
            dt = datetime.fromisoformat(s)
            return ensure_utc(dt)
    except Exception:
        return None


def write_last_fetch_timestamp(dt: datetime) -> None:
    """Write the provided datetime to file in ISO format (Beijing Time)."""
    try:
        # Convert to Beijing Time before writing
        dt_bj = ensure_utc(dt)
        with open(TS_FILE, 'w', encoding='utf-8') as f:
            f.write(dt_bj.isoformat())
    except Exception:
        pass
    except Exception:
        # best-effort; do not raise in scheduler
        pass
