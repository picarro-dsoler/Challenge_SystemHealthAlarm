import dash
from dash import Input, Output, dcc, html

from db import classify_surveyor_status, connect, list_customers, surveyor_latest_status
from fleet_cards import status_legend, surveyor_card
from theme import CARD_STYLE, COLORS, FILTER_ROW_STYLE

dash.register_page(
    __name__,
    path="/fleet",
    name="Fleet",
    title="Fleet status",
    order=1,
)

_conn = connect()
_customers = list_customers(_conn)
_customer_options = [
    {"label": c["CustomerName"] or c["CustomerId"], "value": c["CustomerId"]}
    for c in _customers
]
_default_customer = _customer_options[0]["value"] if _customer_options else None

layout = html.Div(
    [
        html.Div(
            [
                html.H2("Fleet overview", style={"marginTop": 0, "fontWeight": 700}),
                html.P(
                    "Latest survey per surveyor. "
                    "Warning if PeakH or FlowrateH > 0.5; critical if FaultH > 0.8; else OK.",
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
                            id="fleet-customer-id",
                            options=_customer_options,
                            value=_default_customer,
                            clearable=False,
                        ),
                    ],
                    style={**FILTER_ROW_STYLE, "gridTemplateColumns": "minmax(280px, 420px)"},
                ),
                status_legend(),
                html.Div(id="fleet-surveyor-list"),
            ],
            style=CARD_STYLE,
        ),
    ]
)


@dash.callback(
    Output("fleet-surveyor-list", "children"),
    Input("fleet-customer-id", "value"),
)
def refresh_fleet(customer_id):
    if not customer_id:
        return html.P("Select a customer.", style={"color": COLORS["muted"]})

    rows = surveyor_latest_status(connect(), customer_id)
    if not rows:
        return html.P("No surveyors for this customer.", style={"color": COLORS["muted"]})

    counts = {"green": 0, "yellow": 0, "red": 0}
    cards = []
    for row in rows:
        key, _ = classify_surveyor_status(
            float(row["FlowrateH"]), float(row["PeakH"]), float(row["FaultH"])
        )
        counts[key] += 1
        cards.append(surveyor_card(row, customer_id))

    summary = html.Div(
        [
            html.Span(f"{len(rows)} surveyors", style={"marginRight": "1.25rem"}),
            html.Span(
                f"OK {counts['green']}",
                style={"color": COLORS["status_green"], "marginRight": "1rem"},
            ),
            html.Span(
                f"Warning {counts['yellow']}",
                style={"color": COLORS["status_yellow"], "marginRight": "1rem"},
            ),
            html.Span(f"Critical {counts['red']}", style={"color": COLORS["status_red"]}),
        ],
        style={"marginBottom": "1rem", "fontWeight": 600, "fontSize": "0.95rem"},
    )

    return html.Div([summary, *cards])