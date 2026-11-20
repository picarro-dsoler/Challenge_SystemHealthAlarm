import dash
from dash import Input, Output, State, dcc, html

from db import CONFIG_COLUMNS, connect, get_config, list_customers, list_surveyors, upsert_config
from theme import CARD_STYLE, COLORS, FILTER_ROW_STYLE

dash.register_page(__name__, path="/config", name="Config", title="Config params", order=3)

_conn = connect()
_customers = list_customers(_conn)
_customer_options = [
    {"label": c["CustomerName"] or c["CustomerId"], "value": c["CustomerId"]}
    for c in _customers
]
_default_customer = _customer_options[0]["value"] if _customer_options else None
_initial_surveyors = list_surveyors(_conn, _default_customer) if _default_customer else []
_initial_surveyor_options = [
    {"label": s["SurveyorUnit"] or s["SurveyorUnitId"], "value": s["SurveyorUnitId"]}
    for s in _initial_surveyors
]

_field_style = {
    "display": "grid",
    "gridTemplateColumns": "220px 1fr",
    "gap": "0.5rem",
    "marginBottom": "0.5rem",
}


def _num_input(cid: str, label: str) -> html.Div:
    return html.Div(
        [
            html.Label(label, style={"fontWeight": "600", "color": COLORS["text"]}),
            dcc.Input(id=cid, type="number", step="any", style={"width": "100%"}),
        ],
        style=_field_style,
    )


_input_ids = [f"cfg-{col}" for col in CONFIG_COLUMNS]

layout = html.Div(
    [
        html.Div(
            [
                html.H2("Config parameters", style={"marginTop": 0, "fontWeight": 700}),
                html.P(
                    "Select customer, then surveyor. Values persist in ConfigParams.",
                    style={"color": COLORS["muted"], "marginBottom": "1rem"},
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label("Customer", style={"fontWeight": 600, "marginBottom": "0.35rem"}),
                                dcc.Dropdown(
                                    id="cfg-customer-id",
                                    options=_customer_options,
                                    value=_default_customer,
                                    clearable=False,
                                ),
                            ]
                        ),
                        html.Div(
                            [
                                html.Label("Surveyor", style={"fontWeight": 600, "marginBottom": "0.35rem"}),
                                dcc.Dropdown(
                                    id="cfg-surveyor-id",
                                    options=_initial_surveyor_options,
                                    value=_initial_surveyor_options[0]["value"]
                                    if _initial_surveyor_options
                                    else None,
                                ),
                            ]
                        ),
                    ],
                    style=FILTER_ROW_STYLE,
                ),
                html.Div(
                    [_num_input(i, col) for i, col in zip(_input_ids, CONFIG_COLUMNS)],
                    id="cfg-form",
                    style={"marginTop": "1rem"},
                ),
                html.Button("Save to database", id="cfg-save", n_clicks=0),
                html.Div(id="cfg-status", style={"marginTop": "0.75rem", "color": COLORS["accent"]}),
            ],
            style=CARD_STYLE,
        ),
    ]
)


@dash.callback(
    Output("cfg-surveyor-id", "options"),
    Output("cfg-surveyor-id", "value"),
    Input("cfg-customer-id", "value"),
)
def filter_cfg_surveyors(customer_id):
    if not customer_id:
        return [], None
    surveyors = list_surveyors(connect(), customer_id)
    options = [
        {"label": s["SurveyorUnit"] or s["SurveyorUnitId"], "value": s["SurveyorUnitId"]}
        for s in surveyors
    ]
    return options, options[0]["value"] if options else None


@dash.callback(
    [Output(i, "value") for i in _input_ids],
    Input("cfg-surveyor-id", "value"),
)
def load_config(surveyor_id):
    if not surveyor_id:
        return [None] * len(CONFIG_COLUMNS)
    cfg = get_config(connect(), surveyor_id)
    return [cfg.get(col) for col in CONFIG_COLUMNS]


@dash.callback(
    Output("cfg-status", "children"),
    Input("cfg-save", "n_clicks"),
    State("cfg-surveyor-id", "value"),
    [State(i, "value") for i in _input_ids],
    prevent_initial_call=True,
)
def save_config(n_clicks, surveyor_id, *field_values):
    if not surveyor_id:
        return "Select a surveyor first."
    if n_clicks < 1:
        return ""
    values = {col: float(v) if v is not None else 0.0 for col, v in zip(CONFIG_COLUMNS, field_values)}
    try:
        upsert_config(connect(), surveyor_id, values)
    except Exception as exc:
        return f"Save failed: {exc}"
    return "Saved to ConfigParams."