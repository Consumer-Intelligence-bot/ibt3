"""
Consumer Intelligence branded navbar.

White background, magenta accent bar at top, clean nav links.
Admin page is hidden from navigation (direct URL only per spec Section 8.9).
"""
from dash import html
import dash_bootstrap_components as dbc


NAV_ITEMS = [
    {"label": "Market Overview", "href": "/"},
    {"label": "Insurer Diagnostic", "href": "/insurer-diagnostic"},
    {"label": "Insurer Comparison", "href": "/insurer-comparison"},
    {"label": "Awareness: Market", "href": "/awareness-market"},
    {"label": "Awareness: Insurer", "href": "/awareness-insurer"},
]


def ci_navbar(current_path: str = "/") -> html.Div:
    """Render the CI-branded navbar. Highlights the active page."""
    nav_links = []
    for item in NAV_ITEMS:
        is_active = current_path == item["href"]
        link_style = {
            "color": "#FFFFFF" if is_active else "#54585A",
            "backgroundColor": "#981D97" if is_active else "transparent",
            "borderRadius": "4px",
            "padding": "6px 12px",
            "fontSize": "13px",
            "fontWeight": "500",
            "textDecoration": "none",
            "marginLeft": "4px",
        }
        nav_links.append(
            dbc.NavItem(
                dbc.NavLink(
                    item["label"],
                    href=item["href"],
                    active=is_active,
                    style=link_style,
                )
            )
        )

    return html.Div(
        html.Div(
            style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "padding": "10px 24px"},
            children=[
                html.A(
                    [
                        html.Span("Consumer Intelligence", style={"fontWeight": 700, "color": "#981D97", "fontSize": "16px"}),
                        html.Span(" | ", style={"color": "#CCC", "margin": "0 8px"}),
                        html.Span("IBT Shopping & Switching", style={"fontWeight": 400, "fontSize": "13px", "color": "#54585A"}),
                    ],
                    href="/",
                    style={"textDecoration": "none"},
                ),
                html.Div(
                    nav_links,
                    style={"display": "flex", "alignItems": "center"},
                ),
            ],
        ),
        style={
            "backgroundColor": "#FFFFFF",
            "borderTop": "3px solid #981D97",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.08)",
            "marginBottom": "16px",
        },
    )
