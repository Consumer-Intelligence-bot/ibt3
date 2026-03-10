# Consumer Intelligence — Streamlit Dashboard

Analytics dashboard for insurance market intelligence, combining Claims Intelligence and Shopping & Switching Intelligence in a single multipage Streamlit app. All data sourced from Power BI via DAX queries.

## Quick start

### Option A: Local development

**Prerequisites:** Python 3.11+

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run the app (default port 8501)
streamlit run app.py
```

Open **http://localhost:8501**

### Option B: Docker

```bash
docker build -t consumer-intelligence .
docker run -d --name consumer-intelligence -p 8501:8501 consumer-intelligence
```

Open **http://localhost:8501**

### Option C: Production (Render)

Deployed via `render.yaml`:

```bash
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

---

## Project structure

```
app.py                      # Main entry point (landing page, auth, shared state)
.streamlit/config.toml      # Streamlit theme and server config
pages/                      # Streamlit multipage navigation
  1_Claims_Intelligence.py
  2_Market_Overview.py
  3_Headline.py
  4_Customer_Flows.py
  5_Awareness_Market.py
  6_Awareness_Insurer.py
  7_Price_Sensitivity.py
  8_Channel_PCW.py
  9_Admin.py
lib/                        # Core library
  config.py                 # Branding, thresholds, CSS
  powerbi.py                # Power BI auth (MSAL) & DAX queries
  narrative.py              # AI narrative generation (Claude API)
  state.py                  # Session state & data caching
  analytics/                # Analytics modules
    awareness.py, bayesian.py, channels.py, confidence.py,
    demographics.py, dimensions.py, flows.py, price.py,
    queries.py, rates.py, reasons.py, suppression.py,
    transforms.py, trends.py
public/data/                # Demo/fallback CSV data
```

## Data

The app connects to Power BI and auto-discovers table names at startup. If Power BI is unavailable, it falls back to demo CSV files in `public/data/`.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for AI-generated narratives |
| `NARRATIVE_ENABLED` | No | Toggle AI narratives on/off (default: `true`) |
| `NARRATIVE_MODEL` | No | Claude model ID (default: `claude-opus-4-6`) |

Copy `.env.example` to `.env` and fill in values.

---

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs an import check on all library modules against Python 3.12.
