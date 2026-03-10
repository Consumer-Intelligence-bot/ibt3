"""
Unified configuration for Consumer Intelligence dashboards.
Merges S&S and Claims settings into a single source of truth.
"""

import os

# ---------------------------------------------------------------------------
# Azure / Power BI credentials
# ---------------------------------------------------------------------------
TENANT_ID = "21c877f6-eb38-45b3-82dd-a27ccad676ce"
CLIENT_ID = "9cd99ce2-4c31-46e0-bb7c-eeb8e12e73d6"
SCOPE = ["https://analysis.windows.net/powerbi/api/Dataset.Read.All"]

# Motor insurance fabric instance
MOTOR_WORKSPACE_ID = "db6f5221-fa36-48f7-8c14-259a1f570bc5"
MOTOR_DATASET_ID = "646c070f-5b4f-4ded-b0f9-4ae8a8b8a7ad"

# Home insurance fabric instance
# NOTE: The workspace ID comes from the Fabric URL. The DATASET_ID must point
# to the *semantic model* (not the dataflow).  To find the correct dataset ID:
#   1. Open the workspace in Fabric (groups/1c6e2798-...).
#   2. Locate the semantic model that contains the home insurance survey data.
#   3. Copy the dataset ID from the URL or via GET .../groups/{workspace_id}/datasets.
# The dataflow ID (e6f052b4-...) is NOT the same as the dataset/semantic model ID.
HOME_WORKSPACE_ID = os.getenv(
    "HOME_WORKSPACE_ID", "1c6e2798-9b81-4643-82a2-791780138db3"
)
HOME_DATASET_ID = os.getenv(
    "HOME_DATASET_ID", "71b28688-1e7e-421b-bb28-ccd29518ad94"
)

# Legacy aliases (default to motor)
WORKSPACE_ID = MOTOR_WORKSPACE_ID
DATASET_ID = MOTOR_DATASET_ID

# Fallback table names (auto-discovered at runtime via INFO.TABLES())
MAIN_TABLE = "MainData"
OTHER_TABLE = "AllOtherData"

# Product configuration
PRODUCTS = ["Motor", "Home"]

# ---------------------------------------------------------------------------
# CI Brand colours (Spec Section 11.1)
# ---------------------------------------------------------------------------
CI_MAGENTA = "#981D97"
CI_YELLOW = "#FFCD00"
CI_GREEN = "#48A23F"
CI_RED = "#F4364C"
CI_BLUE = "#5BC2E7"
CI_GREY = "#54585A"
CI_LIGHT_GREY = "#E9EAEB"
CI_WHITE = "#FFFFFF"

# Aliases used by Claims
CI_VIOLET = CI_MAGENTA
CI_DARK = CI_GREY
CI_LGREY = CI_LIGHT_GREY

# Bump chart colour sequence (Spec Section 11.3)
BUMP_COLOURS = [
    CI_MAGENTA, CI_BLUE, CI_GREEN, CI_RED, CI_YELLOW,
    "#C44BE0", "#2FA8CC", "#3A8A32", "#D02840", "#B8A000",
    "#7B3FA0", "#1A8099",
]

# Visual rules
INSURER_COLOUR = CI_MAGENTA
MARKET_COLOUR = CI_GREY
POSITIVE_GAP_COLOUR = CI_GREEN
NEGATIVE_GAP_COLOUR = CI_RED
NEUTRAL_GAP_THRESHOLD = 1.0  # percentage points

# ---------------------------------------------------------------------------
# Confidence-first thresholds (Spec Section 12.1)
# ---------------------------------------------------------------------------

# Layer 1: System floor
SYSTEM_FLOOR_N = 15

# Layer 2: CI-width thresholds (percentage points)
CI_WIDTH_PUBLISHABLE_RATE = 8.0
CI_WIDTH_INDICATIVE_RATE = 12.0
CI_WIDTH_PUBLISHABLE_REASON = 12.0
CI_WIDTH_INDICATIVE_REASON = 16.0
CI_WIDTH_PUBLISHABLE_AWARENESS = 8.0
CI_WIDTH_INDICATIVE_AWARENESS = 12.0
NPS_MIN_N = 30

# Flow cell suppression
MIN_BASE_FLOW_CELL = 10

# Market-level alert
MARKET_CI_ALERT_THRESHOLD = 3.0
MIN_ELIGIBLE_INSURERS_WARNING = 3

# n-based suppression thresholds
MIN_BASE_PUBLISHABLE = 50
MIN_BASE_INDICATIVE = 30
MIN_BASE_REASON = 30
MIN_BASE_TREND = 30
MIN_BASE_MARKET = 100

# Default time windows (Spec Section 4)
DEFAULT_TIME_WINDOW_SHOPPING = 12
DEFAULT_TIME_WINDOW_INSURER = 24

# ---------------------------------------------------------------------------
# Bayesian smoothing (Spec Section 12.2)
# ---------------------------------------------------------------------------
PRIOR_STRENGTH = 30
CONFIDENCE_LEVEL = 0.95
Z_SCORE = 1.96
Z_95 = 1.96
TREND_NOISE_THRESHOLD = 2.0

# ---------------------------------------------------------------------------
# AI-generated narrative
# ---------------------------------------------------------------------------
NARRATIVE_MODEL = os.getenv("NARRATIVE_MODEL", "claude-opus-4-6")
NARRATIVE_ENABLED = os.getenv("NARRATIVE_ENABLED", "true").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# CSS for Streamlit
# ---------------------------------------------------------------------------
CSS = f"""
<style>
html, body, [class*="css"] {{
    font-family: Verdana, sans-serif;
    color: {CI_DARK};
}}
.ci-header {{
    padding: 12px 0 16px 0;
    border-bottom: 3px solid {CI_MAGENTA};
    margin-bottom: 24px;
}}
.ci-logo {{
    font-size: 20px;
    font-weight: bold;
    color: {CI_MAGENTA};
}}
.section-title {{
    font-size: 15px;
    font-weight: bold;
    color: {CI_DARK};
    border-bottom: 2px solid {CI_LGREY};
    padding-bottom: 8px;
    margin-bottom: 16px;
}}
div[data-testid="stMetricValue"] {{
    font-size: 26px !important;
    font-weight: bold !important;
    color: {CI_MAGENTA} !important;
}}
</style>
"""
