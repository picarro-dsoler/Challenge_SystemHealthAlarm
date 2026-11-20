import dash
from dash import Input, Output, dcc, html

from db import classify_surveyor_status, connect, list_customers, surveyor_latest_status_all
from fleet_cards import status_legend, surveyor_card
from theme import CARD_STYLE, COLORS, FILTER_ROW_STYLE

dash.register_page(
    __name__,
    path="/",
    name="Alerts",
    title="Vehicles needing attention",
    order=0,
)

_conn = connect()
_customers = list_customers(_conn)
_customer_options = [{"label": "All customers", "value": "__all__"}] + [
    {"label": c["CustomerName"] or c["CustomerId"], "value": c["CustomerId"]}
    for c in _customers
]


def _section_header(title: str, count: int, accent: str, bg: str) -> html.Div:
    return html.Div(
        [
            html.H3(title, style={"margin": 0, "fontWeight": 700, "fontSize": "1.1rem"}),
            html.Span(
                f"{count} vehicle{'s' if count != 1 else ''}",
                style={
                    "marginLeft": "0.75rem",
                    "fontSize": "0.85rem",
                    "fontWeight": 600,
                    "padding": "0.2rem 0.65rem",
                    "borderRadius": "6px",
                    "backgroundColor": bg,
                    "color": accent,
                },
            ),
        ],
        style={
            "display": "flex",
            "alignItems": "center",
            "marginTop": "1.25rem",
            "marginBottom": "0.75rem",
            "paddingBottom": "0.5rem",
            "borderBottom": f"2px solid {accent}",
        },
    )


def _empty_msg(text: str) -> html.P:
    return html.P(text, style={"color": COLORS["muted"], "marginBottom": "0.5rem"})


layout = html.Div(
    [
        html.Div(
            [
                html.H2("Attention required", style={"marginTop": 0, "fontWeight": 700}),
                html.P(
                    "Vehicles in critical or warning state (latest survey per unit). "
                    "OK vehicles are not listed here — see Fleet for the full list.",
                    style={"color": COLORS["muted"], "marginBottom": "1rem", "lineHeight": 1.5},
                ),
                html.P(
                    "Click a vehicle row to open its time series on Visualization.",
                    style={
                        "color": COLORS["accent"],
                        "fontSize": "0.9rem",
                        "marginTop": "-0.5rem",
                        "marginBottom": "1rem",
                    },
                ),
                html.Div(
                    [
                        html.Label("Customer", style={"fontWeight": 600, "marginBottom": "0.35rem"}),
                        dcc.Dropdown(
                            id="init-customer-id",
                            options=_customer_options,
                            value="__all__",
                            clearable=False,
                        ),
                    ],
                    style={**FILTER_ROW_STYLE, "gridTemplateColumns": "minmax(280px, 420px)"},
                ),
                status_legend(),
                html.Div(id="init-attention-sections"),
            ],
            style=CARD_STYLE,
        ),
    ]
)


@dash.callback(
    Output("init-attention-sections", "children"),
    Input("init-customer-id", "value"),
)
def refresh_init_attention(customer_id):
    rows = surveyor_latest_status_all(connect())
    if customer_id and customer_id != "__all__":
        rows = [r for r in rows if str(r.get("CustomerId", "")) == str(customer_id)]

    red_rows: list[dict] = []
    yellow_rows: list[dict] = []
    for row in rows:
        key, _ = classify_surveyor_status(
            float(row["FlowrateH"]),
            float(row["PeakH"]),
            float(row["FaultH"]),
        )
        if key == "red":
            red_rows.append(row)
        elif key == "yellow":
            yellow_rows.append(row)

    red_rows.sort(key=lambda r: (r.get("CustomerName") or "", r.get("SurveyorUnit") or ""))
    yellow_rows.sort(key=lambda r: (r.get("CustomerName") or "", r.get("SurveyorUnit") or ""))

    show_customer = customer_id == "__all__"

    return html.Div(
        [
            _section_header(
                "Critical — FaultH > 0.8",
                len(red_rows),
                COLORS["status_red"],
                COLORS["status_red_bg"],
            ),
            *(
                [surveyor_card(r, r["CustomerId"], show_customer=show_customer) for r in red_rows]
                if red_rows
                else [_empty_msg("No vehicles in critical state.")]
            ),
            _section_header(
                "Warning — PeakH or FlowrateH > 0.5",
                len(yellow_rows),
                COLORS["status_yellow"],
                COLORS["status_yellow_bg"],
            ),
            *(
                [surveyor_card(r, r["CustomerId"], show_customer=show_customer) for r in yellow_rows]
                if yellow_rows
                else [_empty_msg("No vehicles in warning state.")]
            ),
        ]
    )