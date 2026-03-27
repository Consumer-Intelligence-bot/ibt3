"""
Screen registry for the IBT Customer Lifecycle Dashboard.

Each screen module exposes a `render()` function that takes a filters dict.
"""

SCREENS = [
    {"key": "pre_renewal", "label": "Pre-Renewal", "icon": "📋"},
    {"key": "awareness", "label": "Awareness", "icon": "📢"},
    {"key": "switching", "label": "Switching", "icon": "🔄"},
    {"key": "reasons", "label": "Reasons", "icon": "💡"},
    {"key": "shopping", "label": "Shopping", "icon": "🛒"},
    {"key": "channels", "label": "Channels", "icon": "📡"},
    {"key": "satisfaction", "label": "Satisfaction", "icon": "⭐"},
    {"key": "claims", "label": "Claims", "icon": "📝"},
]

ADMIN_SCREENS = [
    {"key": "admin", "label": "Admin / Governance", "icon": "⚙️"},
    {"key": "methodology", "label": "Methodology", "icon": "📖"},
]

ALL_SCREEN_KEYS = [s["key"] for s in SCREENS] + [s["key"] for s in ADMIN_SCREENS]
