"""Picarro / KPIHub dashboard palette + alarm-specific status & chart colors."""
from __future__ import annotations

# Aligned with KPIHub/dashboard/theme.py (Picarro brand green, dark greys).
COLORS = {
    "bg": "#111111",
    "surface": "#1c1c1c",
    "surface_alt": "#232323",
    "border": "#454545",
    "text": "#ffffff",
    "muted": "#788592",
    "accent": "#6eb43f",
    "accent_light": "#7aba7b",
    "accent_dark": "#5a9a33",
    "accent_dim": "#5a9a33",
    "header_bg": "#0b0b0b",
    "unit_row_bg": "#181818",
    # Time-series (readable on dark surfaces)
    "flow": "#7aba7b",
    "flow_h": "#d4a84b",
    "peak": "#6eb43f",
    "peak_i": "#c9a227",
    "fault": "#e07a6e",
    # Fleet status
    "status_green": "#6eb43f",
    "status_yellow": "#d4a84b",
    "status_red": "#e07a6e",
    "status_green_bg": "rgba(110, 180, 63, 0.14)",
    "status_yellow_bg": "rgba(212, 168, 75, 0.14)",
    "status_red_bg": "rgba(224, 122, 110, 0.14)",
}

CHART_SERIES_PALETTE = [
    COLORS["accent"],
    COLORS["accent_light"],
    COLORS["flow_h"],
    "#a7a7a7",
    COLORS["peak_i"],
    COLORS["fault"],
]

STATUS_STYLES = {
    "green": {"border": COLORS["status_green"], "bg": COLORS["status_green_bg"], "label": "OK"},
    "yellow": {"border": COLORS["status_yellow"], "bg": COLORS["status_yellow_bg"], "label": "Warning"},
    "red": {"border": COLORS["status_red"], "bg": COLORS["status_red_bg"], "label": "Critical"},
}

PAGE_STYLE = {
    "minHeight": "100vh",
    "backgroundColor": COLORS["bg"],
    "color": COLORS["text"],
    "fontFamily": "Helvetica, 'Helvetica Neue', Arial, sans-serif",
    "padding": "0 0 2rem",
}

HEADER_STYLE = {
    "padding": "1.25rem 2rem",
    "backgroundColor": COLORS["surface"],
    "borderBottom": f"1px solid {COLORS['border']}",
}

CARD_STYLE = {
    "backgroundColor": COLORS["surface"],
    "border": f"1px solid {COLORS['border']}",
    "borderRadius": "12px",
    "padding": "1.25rem",
    "margin": "1rem 2rem 1.5rem",
}

DROPDOWN_STYLE = {
    "backgroundColor": COLORS["surface_alt"],
    "color": COLORS["text"],
    "borderColor": COLORS["border"],
}

FILTER_ROW_STYLE = {
    "display": "grid",
    "gridTemplateColumns": "repeat(auto-fit, minmax(240px, 1fr))",
    "gap": "1rem",
    "marginBottom": "0.25rem",
}

PLOT_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor=COLORS["surface_alt"],
    font=dict(
        family="Helvetica, Helvetica Neue, Arial, sans-serif",
        color=COLORS["text"],
        size=12,
    ),
    margin=dict(l=56, r=56, t=48, b=48),
    hoverlabel=dict(bgcolor=COLORS["surface"], font_size=12, font_color=COLORS["text"]),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        bgcolor="rgba(0,0,0,0)",
    ),
)