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
# CI Brand colours — 6 core colours (brand guidelines)
# ---------------------------------------------------------------------------
CI_PURPLE = "#981D97"     # Primary brand, print lead
CI_YELLOW = "#FFCD00"     # Accent, highlights
CI_GREEN = "#48A23F"      # Positive, success
CI_RED = "#F4364C"        # Alert, negative, emphasis
CI_CYAN = "#5BC2E7"       # Digital primary, CTAs
CI_CHARCOAL = "#54585A"   # Text, dark backgrounds

# 60% tints
CI_PURPLE_60 = "#C177C1"
CI_YELLOW_60 = "#FFE166"
CI_GREEN_60 = "#91C78C"
CI_RED_60 = "#F88694"
CI_CYAN_60 = "#9DDAF1"
CI_CHARCOAL_60 = "#989B9C"

# 20% tints
CI_PURPLE_20 = "#EAD2EA"
CI_YELLOW_20 = "#FFF5CC"
CI_GREEN_20 = "#DAECD9"
CI_RED_20 = "#FDD7DB"
CI_CYAN_20 = "#DEF3FA"
CI_CHARCOAL_20 = "#DDDEDE"

CI_WHITE = "#FFFFFF"

# Legacy aliases (referenced throughout codebase)
CI_MAGENTA = CI_PURPLE
CI_BLUE = CI_CYAN
CI_GREY = CI_CHARCOAL
CI_LIGHT_GREY = CI_CHARCOAL_20
CI_DARK = CI_CHARCOAL
CI_LGREY = CI_CHARCOAL_20

# Chart colour sequence (brand spec: Cyan, Purple, Yellow, Green, Red,
# Charcoal, then 60% tints, then 20% tints)
BUMP_COLOURS = [
    CI_CYAN, CI_PURPLE, CI_YELLOW, CI_GREEN, CI_RED, CI_CHARCOAL,
    CI_CYAN_60, CI_PURPLE_60, CI_YELLOW_60, CI_GREEN_60, CI_RED_60, CI_CHARCOAL_60,
]

# Visual rules
INSURER_COLOUR = CI_PURPLE
MARKET_COLOUR = CI_CHARCOAL
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

# Legacy aliases for imports that reference old names
CI_NAVY = CI_CHARCOAL
CI_NAVY_LIGHT = CI_CHARCOAL_60
CI_VIOLET = CI_PURPLE
CI_MARKET_PURPLE = CI_CHARCOAL

# ---------------------------------------------------------------------------
# CSS for Streamlit
# ---------------------------------------------------------------------------
FONT = "Montserrat, -apple-system, BlinkMacSystemFont, sans-serif"

CSS = f"""
<style>
/* ── Import Montserrat (brand web font, 400/700) ─────────────── */
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap');

/* ── Base ─────────────────────────────────────────────────────── */
html, body, [class*="css"] {{
    font-family: {FONT};
    color: {CI_CHARCOAL};
    -webkit-font-smoothing: antialiased;
}}

/* ── Main container background ────────────────────────────────── */
.stApp {{
    background: {CI_WHITE};
}}

/* ── Sidebar (Charcoal per brand spec) ────────────────────────── */
section[data-testid="stSidebar"] {{
    background: {CI_CHARCOAL};
    border-right: none;
}}
section[data-testid="stSidebar"] * {{
    color: rgba(255,255,255,0.85) !important;
}}
section[data-testid="stSidebar"] label {{
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.8px !important;
    color: {CI_CHARCOAL_60} !important;
}}
section[data-testid="stSidebar"] .stSelectbox > div > div {{
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: white !important;
}}
section[data-testid="stSidebar"] hr {{
    border-color: rgba(255,255,255,0.08) !important;
}}
section[data-testid="stSidebar"] .stButton > button {{
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    color: rgba(255,255,255,0.85) !important;
    font-size: 12px !important;
    transition: all 0.2s ease !important;
}}
section[data-testid="stSidebar"] .stButton > button:hover {{
    background: rgba(255,255,255,0.06) !important;
    border-color: {CI_PURPLE} !important;
    color: white !important;
}}

/* ── Tab bar (main navigation) ────────────────────────────────── */
.stMainBlockContainer .stHorizontalBlock .stButton > button {{
    font-family: {FONT} !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px !important;
    padding: 10px 6px !important;
    border-radius: 0 !important;
    border: none !important;
    border-bottom: 3px solid transparent !important;
    background: transparent !important;
    color: {CI_CHARCOAL} !important;
    transition: all 0.25s ease !important;
}}
.stMainBlockContainer .stHorizontalBlock .stButton > button:hover {{
    color: {CI_PURPLE} !important;
    border-bottom-color: {CI_CHARCOAL_20} !important;
    background: transparent !important;
}}
.stMainBlockContainer .stHorizontalBlock .stButton > button[kind="primary"] {{
    color: {CI_PURPLE} !important;
    border-bottom-color: {CI_PURPLE} !important;
    background: transparent !important;
}}

/* ── Headers (Montserrat 700) ────────────────────────────────── */
h1, h2, .stSubheader {{
    font-family: {FONT} !important;
    color: {CI_CHARCOAL} !important;
    font-weight: 700 !important;
}}
h2 {{
    font-size: 1.6rem !important;
    letter-spacing: -0.3px !important;
}}

/* ── Metric cards ─────────────────────────────────────────────── */
div[data-testid="stMetricValue"] {{
    font-family: {FONT} !important;
    font-size: 28px !important;
    font-weight: 700 !important;
    color: {CI_PURPLE} !important;
}}
div[data-testid="stMetricLabel"] {{
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
    color: {CI_CHARCOAL} !important;
}}

/* ── Section dividers ─────────────────────────────────────────── */
.section-title {{
    font-family: {FONT};
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: {CI_CHARCOAL};
    border-bottom: 2px solid {CI_PURPLE};
    padding-bottom: 8px;
    margin-bottom: 16px;
}}

/* ── Expanders (narrative panels) ─────────────────────────────── */
.streamlit-expanderHeader {{
    font-family: {FONT} !important;
    font-weight: 600 !important;
    color: {CI_CHARCOAL} !important;
    background: {CI_CHARCOAL_20} !important;
    border-radius: 12px !important;
}}

/* ── DataFrames & tables ──────────────────────────────────────── */
.stDataFrame {{
    border: 1px solid {CI_CHARCOAL_20} !important;
    border-radius: 12px !important;
}}

/* ── White cards with shadow-on-hover (brand design language) ── */
div[data-testid="stMetric"],
div[data-testid="stExpander"] {{
    background: white;
    border-radius: 12px;
    transition: box-shadow 0.2s ease;
}}
div[data-testid="stMetric"]:hover,
div[data-testid="stExpander"]:hover {{
    box-shadow: 0 2px 8px rgba(84,88,90,0.12);
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
    color: {CI_CHARCOAL};
}}
.alert-green {{
    background-color: {CI_GREEN};
    color: white;
}}

/* ── Tooltips & captions ──────────────────────────────────────── */
.stCaption {{
    font-size: 11px !important;
    color: {CI_CHARCOAL_60} !important;
}}

/* ── Tab bar buttons ──────────────────────────────────────────── */
div[data-testid="stHorizontalBlock"] > div > div > button[kind="secondary"] {{
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    color: {CI_CHARCOAL_60} !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    padding: 8px 4px !important;
}}
div[data-testid="stHorizontalBlock"] > div > div > button[kind="primary"] {{
    background: transparent !important;
    border: none !important;
    border-bottom: 3px solid {CI_PURPLE} !important;
    border-radius: 0 !important;
    color: {CI_CHARCOAL} !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    padding: 8px 4px !important;
}}

/* ── Plotly chart container spacing ───────────────────────────── */
.stPlotlyChart {{
    border-radius: 12px;
    overflow: hidden;
}}

/* ── Decision Screen components ───────────────────────────────── */
.decision-kpi {{
    background: white;
    border: 1px solid {CI_CHARCOAL_20};
    border-radius: 12px;
    padding: 14px 18px;
    transition: box-shadow 0.2s ease;
}}
.decision-kpi:hover {{
    box-shadow: 0 2px 8px rgba(84,88,90,0.12);
}}
.confidence-badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}
.context-footer {{
    border-top: 1px solid {CI_CHARCOAL_20};
    margin-top: 24px;
    padding-top: 10px;
    font-size: 11px;
    color: {CI_CHARCOAL_60};
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
    background: {CI_CHARCOAL_20};
    border-radius: 3px;
}}
::-webkit-scrollbar-thumb:hover {{
    background: {CI_CHARCOAL};
}}
</style>
"""
