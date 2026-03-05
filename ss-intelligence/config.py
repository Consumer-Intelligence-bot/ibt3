"""
Configuration for Shopping & Switching Intelligence.
All thresholds, colours, and settings centralised here.
"""

# ---------------------------------------------------------------------------
# Confidence-first thresholds (Spec Section 12.1)
# ---------------------------------------------------------------------------

# Layer 1: System floor — hardcoded, never configurable, never displayed
SYSTEM_FLOOR_N = 15

# Layer 2: CI-width thresholds (percentage points) — configurable via Admin
CI_WIDTH_PUBLISHABLE_RATE = 8.0        # retention / shopping / switching
CI_WIDTH_INDICATIVE_RATE = 12.0
CI_WIDTH_PUBLISHABLE_REASON = 12.0     # Q8 / Q18 / Q19 / Q31 / Q33
CI_WIDTH_INDICATIVE_REASON = 16.0
CI_WIDTH_PUBLISHABLE_AWARENESS = 8.0   # Q2 / Q27 (Q1 absent this wave)
CI_WIDTH_INDICATIVE_AWARENESS = 12.0
NPS_MIN_N = 30                         # NPS uses n floor, not CI width

# Flow cell suppression (separate rule, not CI-width-based)
MIN_BASE_FLOW_CELL = 10

# Market-level alert
MARKET_CI_ALERT_THRESHOLD = 3.0        # pp — alert if market CI exceeds this
MIN_ELIGIBLE_INSURERS_WARNING = 3

# Spec Section 12.1 — n-based suppression thresholds
MIN_BASE_PUBLISHABLE = 50
MIN_BASE_INDICATIVE = 30
MIN_BASE_REASON = 30
MIN_BASE_TREND = 30
MIN_BASE_MARKET = 100

# Default time windows (Spec Section 4)
DEFAULT_TIME_WINDOW_SHOPPING = 12    # months — Market Overview
DEFAULT_TIME_WINDOW_INSURER = 24     # months — Insurer pages

# ---------------------------------------------------------------------------
# Bayesian smoothing (Spec Section 12.2)
# ---------------------------------------------------------------------------
PRIOR_STRENGTH = 30
CONFIDENCE_LEVEL = 0.95
Z_SCORE = 1.96
TREND_NOISE_THRESHOLD = 2.0  # pp — change must exceed avg CI width

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

# Bump chart colour sequence (Spec Section 11.3) — rotates after 12 brands
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
