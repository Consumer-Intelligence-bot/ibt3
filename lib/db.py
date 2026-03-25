"""
DuckDB-backed local data persistence.

Survives browser refresh — avoids re-importing from Power BI on every page load.
All functions degrade gracefully if DuckDB is not installed.
"""

import logging
import os
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_DB_PATH = os.getenv("IBT3_DB_PATH", str(Path.home() / ".ibt3" / "cache.duckdb"))

# Valid table names: alphanumeric + underscore only
_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_table_name(table_name: str) -> str:
    """Validate table name to prevent SQL injection."""
    if not _TABLE_NAME_RE.match(table_name):
        raise ValueError(f"Invalid table name: {table_name!r}")
    return table_name


def _ensure_dir():
    Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)


def _set_restrictive_perms(path: str | Path):
    """Set file permissions to owner-only (0o600)."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows or other platforms may not support chmod


def _get_conn():
    import duckdb
    _ensure_dir()
    conn = duckdb.connect(_DB_PATH)
    _set_restrictive_perms(_DB_PATH)
    return conn


def save_dataframe(df: pd.DataFrame, table_name: str) -> None:
    """Persist a DataFrame to a DuckDB table (overwrites existing)."""
    if df is None or df.empty:
        return
    table_name = _validate_table_name(table_name)
    try:
        conn = _get_conn()
    except ImportError:
        return
    try:
        conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
    except Exception:
        logger.warning("Failed to save %s to DuckDB cache", table_name, exc_info=True)
    finally:
        conn.close()


def save_metadata(key: str, value: str) -> None:
    """Save a key-value metadata pair (e.g., time window info)."""
    try:
        conn = _get_conn()
    except ImportError:
        return
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS _metadata (key VARCHAR PRIMARY KEY, value VARCHAR)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO _metadata VALUES (?, ?)", [key, value]
        )
    except Exception:
        logger.warning("Failed to save metadata key=%s", key, exc_info=True)
    finally:
        conn.close()


def load_metadata(key: str) -> str | None:
    """Load a metadata value by key. Returns None if not found."""
    try:
        conn = _get_conn()
    except ImportError:
        return None
    try:
        tables = conn.execute("SHOW TABLES").fetchall()
        if not any(t[0] == "_metadata" for t in tables):
            return None
        result = conn.execute(
            "SELECT value FROM _metadata WHERE key = ?", [key]
        ).fetchone()
        return result[0] if result else None
    except Exception:
        return None
    finally:
        conn.close()


def load_dataframe(table_name: str) -> pd.DataFrame:
    """Load a DataFrame from a DuckDB table. Returns empty DataFrame if not found."""
    table_name = _validate_table_name(table_name)
    try:
        conn = _get_conn()
    except ImportError:
        return pd.DataFrame()
    try:
        tables = conn.execute("SHOW TABLES").fetchall()
        if not any(t[0] == table_name for t in tables):
            return pd.DataFrame()
        return conn.execute(f"SELECT * FROM {table_name}").fetchdf()
    except Exception:
        logger.warning("Failed to load %s from DuckDB cache", table_name, exc_info=True)
        return pd.DataFrame()
    finally:
        conn.close()


def has_data(table_name: str = "df_motor") -> bool:
    """Check if cached data exists."""
    table_name = _validate_table_name(table_name)
    try:
        conn = _get_conn()
    except ImportError:
        return False
    try:
        tables = conn.execute("SHOW TABLES").fetchall()
        if not any(t[0] == table_name for t in tables):
            return False
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        return count > 0
    except Exception:
        return False
    finally:
        conn.close()


def clear_data() -> None:
    """Remove all cached data."""
    try:
        if Path(_DB_PATH).exists():
            Path(_DB_PATH).unlink()
    except OSError:
        logger.warning("Failed to delete DuckDB cache at %s", _DB_PATH, exc_info=True)
