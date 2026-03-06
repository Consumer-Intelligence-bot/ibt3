"""
Filter dropdown components for slicers.
"""
from dash import dcc
import dash_bootstrap_components as dbc


def _safe_option(label, value) -> dict | None:
    """Return option dict only if both label and value are valid (non-null, non-nan)."""
    if label is None or value is None:
        return None
    s_label, s_val = str(label).strip(), str(value).strip()
    if not s_label or not s_val or s_label.lower() == "nan" or s_val.lower() == "nan":
        return None
    return {"label": s_label, "value": s_val}


def insurer_dropdown(id: str, options: list[dict], value: str | None = None) -> dcc.Dropdown:
    """Insurer dropdown. options from DimInsurer."""
    opts = []
    for o in options:
        opt = _safe_option(o.get("Insurer"), o.get("Insurer") or o.get("value"))
        if opt:
            opts.append(opt)
    return dcc.Dropdown(
        id=id,
        options=opts,
        value=value,
        placeholder="Select insurer",
        clearable=True,
        searchable=True,
        className="mb-2",
    )


def age_band_dropdown(id: str, options: list[dict], value: str | None = None) -> dcc.Dropdown:
    """Age band dropdown. First option 'All Ages' returns None."""
    opts = [{"label": "All Ages", "value": "ALL"}]
    for o in sorted(options, key=lambda x: x.get("SortOrder", 0)):
        opt = _safe_option(o.get("AgeBand"), o.get("AgeBand") or o.get("value"))
        if opt and opt["value"] != "ALL":
            opts.append(opt)
    return dcc.Dropdown(
        id=id,
        options=opts,
        value=value if value else "ALL",
        className="mb-2",
    )


def region_dropdown(id: str, options: list[dict], value: str | None = None) -> dcc.Dropdown:
    """Region dropdown. 'All Regions' returns None."""
    opts = [{"label": "All Regions", "value": "ALL"}]
    for o in sorted(options, key=lambda x: x.get("SortOrder", 0)):
        opt = _safe_option(o.get("Region"), o.get("Region") or o.get("value"))
        if opt and opt["value"] != "ALL":
            opts.append(opt)
    return dcc.Dropdown(
        id=id,
        options=opts,
        value=value if value else "ALL",
        className="mb-2",
    )


def payment_type_dropdown(id: str, options: list[dict], value: str | None = None) -> dcc.Dropdown:
    """Payment type dropdown. 'All Payment Types' returns None."""
    opts = [{"label": "All Payment Types", "value": "ALL"}]
    for o in sorted(options, key=lambda x: x.get("SortOrder", 0)):
        opt = _safe_option(o.get("PaymentType"), o.get("PaymentType") or o.get("value"))
        if opt and opt["value"] != "ALL":
            opts.append(opt)
    return dcc.Dropdown(
        id=id,
        options=opts,
        value=value if value else "ALL",
        className="mb-2",
    )


def product_toggle(id: str, value: str = "Motor") -> dcc.RadioItems:
    """Product toggle Motor/Home."""
    return dcc.RadioItems(
        id=id,
        options=[
            {"label": " Motor", "value": "Motor"},
            {"label": " Home", "value": "Home"},
        ],
        value=value,
        inline=True,
        className="mb-2",
    )


def time_window_dropdown(id: str, value: str = "24 months") -> dcc.Dropdown:
    """Time window dropdown (legacy, kept for backwards compatibility)."""
    return dcc.Dropdown(
        id=id,
        options=[
            {"label": "6 months", "value": "6"},
            {"label": "12 months", "value": "12"},
            {"label": "24 months", "value": "24"},
        ],
        value=str(value) if value else "24",
        className="mb-2",
    )


def renewal_month_dropdown(
    id: str,
    options: list[dict],
    value: list | None = None,
) -> dcc.Dropdown:
    """Multi-select renewal month picker.

    Parameters
    ----------
    options : list of {'label': 'Mon YY', 'value': YYYYMM}
    value   : list of selected YYYYMM ints (default last 12 months)
    """
    return dcc.Dropdown(
        id=id,
        options=options,
        value=value,
        multi=True,
        placeholder="Select months...",
        clearable=True,
        className="mb-2",
    )
