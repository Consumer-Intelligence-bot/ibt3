"""
Unified configuration for Consumer Intelligence dashboards.
Merges S&S and Claims settings into a single source of truth.
"""

import os

# ---------------------------------------------------------------------------
# Azure / Power BI credentials
# ---------------------------------------------------------------------------
TENANT_ID = os.getenv("AZURE_TENANT_ID", "21c877f6-eb38-45b3-82dd-a27ccad676ce")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "9cd99ce2-4c31-46e0-bb7c-eeb8e12e73d6")
SCOPE = ["https://analysis.windows.net/powerbi/api/Dataset.Read.All"]

# Motor insurance fabric instance (IBT_Reboot_Motor)
MOTOR_WORKSPACE_ID = os.getenv("MOTOR_WORKSPACE_ID", "1c6e2798-9b81-4643-82a2-791780138db3")
MOTOR_DATASET_ID = os.getenv("MOTOR_DATASET_ID", "e15497a6-e022-45b3-80c3-80a5c0657ff5")

# Home insurance fabric instance
HOME_WORKSPACE_ID = os.getenv(
    "HOME_WORKSPACE_ID", "1c6e2798-9b81-4643-82a2-791780138db3"
)
HOME_DATASET_ID = os.getenv(
    "HOME_DATASET_ID", "71b28688-1e7e-421b-bb28-ccd29518ad94"
)

# Pet insurance fabric instance
PET_WORKSPACE_ID = os.getenv(
    "PET_WORKSPACE_ID", "1c6e2798-9b81-4643-82a2-791780138db3"
)
PET_DATASET_ID = os.getenv(
    "PET_DATASET_ID", "4a1347c3-547a-4360-ae1c-a7f48261c678"
)

# Legacy aliases (default to motor)
WORKSPACE_ID = MOTOR_WORKSPACE_ID
DATASET_ID = MOTOR_DATASET_ID

# Fallback table names (auto-discovered at runtime via INFO.TABLES())
MAIN_TABLE = "MainData"
OTHER_TABLE = "AllOtherData"

# Product configuration
PRODUCTS = ["Motor", "Home", "Pet"]

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

# CI Violet (brand spec) — distinct from CI_MAGENTA
CI_VIOLET = "#AD278C"
CI_DARK = CI_GREY
CI_LGREY = CI_LIGHT_GREY

# Distinct purple for market reference lines/bars (visually distinct from CI_MAGENTA)
CI_MARKET_PURPLE = "#6B1D6B"

# Bump chart colour sequence (Spec Section 11.3)
BUMP_COLOURS = [
    CI_MAGENTA, CI_BLUE, CI_GREEN, CI_RED, CI_YELLOW,
    "#C44BE0", "#2FA8CC", "#3A8A32", "#D02840", "#B8A000",
    "#7B3FA0", "#1A8099",
]

# Visual rules
INSURER_COLOUR = CI_MAGENTA
MARKET_COLOUR = CI_MARKET_PURPLE
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
# Sister brand / shared handler mapping (Spec Section 11.4)
# ---------------------------------------------------------------------------
SISTER_BRANDS = {
    "Direct Line": ["Churchill", "Privilege", "Green Flag"],
    "Churchill": ["Direct Line", "Privilege", "Green Flag"],
    "Privilege": ["Direct Line", "Churchill", "Green Flag"],
    "Aviva": ["Quotemehappy.com"],
    "Quotemehappy.com": ["Aviva"],
    # Pet insurance sister brands
    "Petplan": ["Allianz"],
    "Allianz": ["Petplan"],
}

# Comparable insurer sets for competitor cross-referencing (Spec Section 13.3)
COMPARABLE_INSURERS = {
    "direct": ["Direct Line", "Churchill", "Admiral", "Hastings"],
    "aggregator": ["Admiral", "Hastings", "esure"],
    "composite": ["Aviva", "AXA", "Zurich", "RSA"],
    "mutual": ["NFU Mutual", "LV="],
}

# ---------------------------------------------------------------------------
# AI-generated narrative
# ---------------------------------------------------------------------------
NARRATIVE_MODEL = os.getenv("NARRATIVE_MODEL", "claude-opus-4-6")
NARRATIVE_ENABLED = os.getenv("NARRATIVE_ENABLED", "true").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# CSS for Streamlit
# ---------------------------------------------------------------------------
# Brand palette: navy foundation
CI_NAVY = "#1A2B4A"
CI_NAVY_LIGHT = "#2A3D5E"
CI_WARM_WHITE = "#FAFAF8"
CI_CREAM = "#F5F4F0"

CSS = f"""
<style>
/* ── Import distinctive typography ────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&display=swap');

/* ── Base ─────────────────────────────────────────────────────── */
html, body, [class*="css"] {{
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    color: {CI_NAVY};
    -webkit-font-smoothing: antialiased;
}}

/* ── Main container background ────────────────────────────────── */
.stApp {{
    background: linear-gradient(168deg, {CI_WARM_WHITE} 0%, #F0EFE9 100%);
}}

/* ── Sidebar refinement ───────────────────────────────────────── */
section[data-testid="stSidebar"] {{
    background: {CI_NAVY};
    border-right: none;
}}
section[data-testid="stSidebar"] * {{
    color: #C8CDDA !important;
}}
section[data-testid="stSidebar"] label {{
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.8px !important;
    color: #8B94A8 !important;
}}
section[data-testid="stSidebar"] .stSelectbox > div > div {{
    background: {CI_NAVY_LIGHT} !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: white !important;
}}
section[data-testid="stSidebar"] hr {{
    border-color: rgba(255,255,255,0.08) !important;
}}
section[data-testid="stSidebar"] .stButton > button {{
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    color: #C8CDDA !important;
    font-size: 12px !important;
    transition: all 0.2s ease !important;
}}
section[data-testid="stSidebar"] .stButton > button:hover {{
    background: rgba(255,255,255,0.06) !important;
    border-color: {CI_MAGENTA} !important;
    color: white !important;
}}

/* ── Tab bar (main navigation) ────────────────────────────────── */
.stMainBlockContainer .stHorizontalBlock .stButton > button {{
    font-family: 'DM Sans', sans-serif !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px !important;
    padding: 10px 6px !important;
    border-radius: 0 !important;
    border: none !important;
    border-bottom: 3px solid transparent !important;
    background: transparent !important;
    color: {CI_GREY} !important;
    transition: all 0.25s ease !important;
}}
.stMainBlockContainer .stHorizontalBlock .stButton > button:hover {{
    color: {CI_NAVY} !important;
    border-bottom-color: {CI_LIGHT_GREY} !important;
    background: transparent !important;
}}
.stMainBlockContainer .stHorizontalBlock .stButton > button[kind="primary"] {{
    color: {CI_MAGENTA} !important;
    border-bottom-color: {CI_MAGENTA} !important;
    background: transparent !important;
}}

/* ── Headers ──────────────────────────────────────────────────── */
h1, h2, .stSubheader {{
    font-family: 'Fraunces', Georgia, serif !important;
    color: {CI_NAVY} !important;
    font-weight: 600 !important;
}}
h2 {{
    font-size: 1.6rem !important;
    letter-spacing: -0.3px !important;
}}

/* ── Metric cards ─────────────────────────────────────────────── */
div[data-testid="stMetricValue"] {{
    font-family: 'Fraunces', Georgia, serif !important;
    font-size: 28px !important;
    font-weight: 700 !important;
    color: {CI_MAGENTA} !important;
}}
div[data-testid="stMetricLabel"] {{
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
    color: {CI_GREY} !important;
}}

/* ── Section dividers ─────────────────────────────────────────── */
.section-title {{
    font-family: 'DM Sans', sans-serif;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: {CI_NAVY};
    border-bottom: 2px solid {CI_MAGENTA};
    padding-bottom: 8px;
    margin-bottom: 16px;
}}

/* ── Expanders (narrative panels) ─────────────────────────────── */
.streamlit-expanderHeader {{
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    color: {CI_NAVY} !important;
    background: {CI_CREAM} !important;
    border-radius: 4px !important;
}}

/* ── DataFrames & tables ──────────────────────────────────────── */
.stDataFrame {{
    border: 1px solid {CI_LIGHT_GREY} !important;
    border-radius: 4px !important;
}}

/* ── Alert badges ─────────────────────────────────────────────── */
.alert-badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.3px;
    margin-top: 4px;
}}
.alert-red {{
    background-color: {CI_RED};
    color: white;
}}
.alert-yellow {{
    background-color: {CI_YELLOW};
    color: {CI_NAVY};
}}
.alert-green {{
    background-color: {CI_GREEN};
    color: white;
}}

/* ── Tooltips & captions ──────────────────────────────────────── */
.stCaption {{
    font-size: 11px !important;
    color: #8B94A8 !important;
}}

/* ── Plotly chart container spacing ───────────────────────────── */
.stPlotlyChart {{
    border-radius: 6px;
    overflow: hidden;
}}

/* ── Scrollbar (subtle, not default blue) ─────────────────────── */
::-webkit-scrollbar {{
    width: 6px;
    height: 6px;
}}
::-webkit-scrollbar-track {{
    background: transparent;
}}
::-webkit-scrollbar-thumb {{
    background: {CI_LIGHT_GREY};
    border-radius: 3px;
}}
::-webkit-scrollbar-thumb:hover {{
    background: {CI_GREY};
}}
</style>
"""
