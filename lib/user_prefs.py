"""
User preferences and saved views (Spec Section 16).

Stores competitor sets, default time windows, and watched metrics per user.
Currently uses JSON files for persistence. When authentication is added (P0),
this will integrate with user identity.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PREFS_DIR = Path(os.getenv("PREFS_DIR", "data/user_prefs"))


def _user_file(user_id: str) -> Path:
    """Path to a user's preferences JSON file."""
    PREFS_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)
    return PREFS_DIR / f"{safe_id}.json"


def load_prefs(user_id: str) -> dict:
    """Load user preferences. Returns defaults if no saved prefs exist."""
    path = _user_file(user_id)
    defaults = {
        "competitor_set": [],
        "default_time_window": 12,
        "watched_metrics": [],
        "default_product": "Motor",
    }
    if path.exists():
        try:
            with open(path) as f:
                saved = json.load(f)
            defaults.update(saved)
        except (json.JSONDecodeError, OSError):
            pass
    return defaults


def save_prefs(user_id: str, prefs: dict) -> None:
    """Save user preferences to JSON file."""
    path = _user_file(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(prefs, f, indent=2)


def get_competitor_set(user_id: str) -> list[str]:
    """Get the user's saved competitor set."""
    return load_prefs(user_id).get("competitor_set", [])


def save_competitor_set(user_id: str, competitors: list[str]) -> None:
    """Save a competitor set for a user."""
    prefs = load_prefs(user_id)
    prefs["competitor_set"] = competitors
    save_prefs(user_id, prefs)


def get_watched_metrics(user_id: str) -> list[str]:
    """Get metrics the user is watching for alerts."""
    return load_prefs(user_id).get("watched_metrics", [])


def save_watched_metrics(user_id: str, metrics: list[str]) -> None:
    """Save watched metrics for a user."""
    prefs = load_prefs(user_id)
    prefs["watched_metrics"] = metrics
    save_prefs(user_id, prefs)
