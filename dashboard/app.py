"""Multipage Dash: SystemHealthAlarm SurveyData + ConfigParams."""
import os
import sys
from pathlib import Path

import dash
from dash import dcc, html, page_container, page_registry

app_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(app_dir))

import db  # noqa: E402
from theme import COLORS, HEADER_STYLE, PAGE_STYLE  # noqa: E402

dash_app = dash.Dash(
    __name__,
    use_pages=True,
    pages_folder=str(app_dir / "pages"),
    suppress_callback_exceptions=True,
    title="System Health Alarm",
)
server = dash_app.server

try:
    _probe_count = len(db.list_customers(db.connect()))
    _startup_error = None
except Exception as exc:  # noqa: BLE001
    _probe_count = 0
    _startup_error = f"Database error: {exc}"

dash_app.index_string = f"""<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>{{%title%}}</title>
        {{%favicon%}}
        {{%css%}}
        <style>
            body {{ margin: 0; background: {COLORS["bg"]}; color: {COLORS["text"]}; }}
            a {{ color: {COLORS["accent"]}; }}
            .Select-control,
            .Select-menu-outer,
            .Select-menu,
            .VirtualizedSelectOption {{
                background-color: {COLORS["surface_alt"]} !important;
                border-color: {COLORS["border"]} !important;
                color: {COLORS["text"]} !important;
            }}
            .Select-value-label,
            .Select-placeholder,
            .Select-input > input {{
                color: {COLORS["text"]} !important;
            }}
            .VirtualizedSelectFocusedOption {{
                background-color: {COLORS["header_bg"]} !important;
                color: {COLORS["text"]} !important;
            }}
            .Select-option.is-focused,
            .Select-option.is-selected {{
                background-color: {COLORS["header_bg"]} !important;
                color: {COLORS["accent"]} !important;
            }}
            .dash-dropdown .Select-arrow-zone,
            .Select-arrow {{
                color: {COLORS["muted"]} !important;
            }}
            label {{ color: {COLORS["text"]}; }}
            input[type="number"] {{
                background: {COLORS["surface_alt"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 8px;
                color: {COLORS["text"]};
                padding: 0.5rem 0.75rem;
            }}
            a.fleet-card-link {{
                display: block;
                text-decoration: none;
                color: inherit;
                cursor: pointer;
                transition: transform 0.15s ease, box-shadow 0.15s ease;
            }}
            a.fleet-card-link:hover {{
                transform: translateY(-2px);
                box-shadow: 0 12px 28px rgba(0,0,0,0.45);
            }}
            button#cfg-save {{
                background: {COLORS["accent"]};
                border: 1px solid {COLORS["accent_dark"]};
                color: #111111;
                font-weight: 700;
                padding: 0.65rem 1.5rem;
                border-radius: 8px;
                cursor: pointer;
            }}
            button#cfg-save:hover {{
                background: {COLORS["accent_light"]};
            }}
        </style>
    </head>
    <body>
        {{%app_entry%}}
        <footer>{{%config%}}{{%scripts%}}{{%renderer%}}</footer>
    </body>
</html>
"""


def _nav_links():
    links = []
    for page in sorted(page_registry.values(), key=lambda p: p.get("order", 99)):
        links.append(
            dcc.Link(
                page["name"],
                href=page["path"],
                style={
                    "display": "inline-block",
                    "padding": "0.45rem 1rem",
                    "marginRight": "0.5rem",
                    "borderRadius": "8px",
                    "textDecoration": "none",
                    "fontWeight": "600",
                    "fontSize": "0.9rem",
                    "color": COLORS["text"],
                    "backgroundColor": COLORS["surface_alt"],
                    "border": f"1px solid {COLORS['border']}",
                },
            )
        )
    return links


dash_app.layout = html.Div(
    [
        html.Div(
            _startup_error or "",
            style={
                "display": "block" if _startup_error else "none",
                "color": "#f87171",
                "background": "rgba(127,29,29,0.35)",
                "padding": "0.75rem 1rem",
                "borderRadius": "8px",
                "marginBottom": "1rem",
                "border": "1px solid #991b1b",
            },
        ),
        html.Header(
            [
                html.Div(
                    [
                        html.Span("⬤", style={"color": COLORS["accent"], "marginRight": "0.5rem"}),
                        html.H1(
                            "System Health Alarm",
                            style={"margin": 0, "fontSize": "1.35rem", "fontWeight": 700},
                        ),
                    ],
                    style={"display": "flex", "alignItems": "center"},
                ),
                html.Div(_nav_links(), style={"marginTop": "0.85rem"}),
                html.Div(
                    [
                        html.Span(db.db_display_name()),
                        html.Span(
                            f" · {_probe_count} customers" if not _startup_error else "",
                            style={"marginLeft": "0.35rem"},
                        ),
                    ],
                    style={"marginTop": "0.75rem", "color": COLORS["muted"], "fontSize": "0.8rem"},
                ),
            ],
            style=HEADER_STYLE,
        ),
        dcc.Location(id="url", refresh=False),
        page_container,
    ],
    style=PAGE_STYLE,
)


if __name__ == "__main__":
    port = int(os.environ.get("ALARM_DASH_PORT", "8051"))
    dash_app.run(host="0.0.0.0", port=port, debug=False)