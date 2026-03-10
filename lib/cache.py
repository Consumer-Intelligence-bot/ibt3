"""
Disk-based data cache for Power BI query results.

Persists DataFrames as parquet files so data survives server restarts.
Reload is controlled via the Admin panel, not automatic.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / ".data_cache"

_META_FILE = "metadata.json"


def _meta_path() -> Path:
    return CACHE_DIR / _META_FILE


def is_cached() -> bool:
    """Return True if a valid disk cache exists."""
    return _meta_path().exists()


def save_cache(
    main_table: str,
    other_table: str,
    months: list[int],
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
) -> None:
    """Persist data and metadata to disk."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df_main.to_parquet(CACHE_DIR / "maindata.parquet", index=False)
    df_questions.to_parquet(CACHE_DIR / "questions.parquet", index=False)
    meta = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "main_table": main_table,
        "other_table": other_table,
        "months": months,
        "main_rows": len(df_main),
        "question_rows": len(df_questions),
    }
    _meta_path().write_text(json.dumps(meta, indent=2))
    logger.info("Data cache saved: %d main rows, %d question rows", len(df_main), len(df_questions))


def load_cache() -> dict | None:
    """Load cached data from disk.

    Returns dict with keys: main_table, other_table, months, df_main, df_questions.
    Returns None if no cache exists.
    """
    if not is_cached():
        return None
    try:
        meta = json.loads(_meta_path().read_text())
        df_main = pd.read_parquet(CACHE_DIR / "maindata.parquet")
        df_questions = pd.read_parquet(CACHE_DIR / "questions.parquet")
        return {
            "main_table": meta["main_table"],
            "other_table": meta["other_table"],
            "months": meta["months"],
            "df_main": df_main,
            "df_questions": df_questions,
        }
    except Exception:
        logger.exception("Failed to load disk cache, will re-fetch from Power BI")
        return None


def clear_cache() -> None:
    """Delete all cached data files."""
    if CACHE_DIR.exists():
        for f in CACHE_DIR.iterdir():
            f.unlink()
        CACHE_DIR.rmdir()
    logger.info("Data cache cleared")


def cache_info() -> dict | None:
    """Return metadata about the current cache, or None if no cache."""
    if not _meta_path().exists():
        return None
    try:
        return json.loads(_meta_path().read_text())
    except Exception:
        return None
