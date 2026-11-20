import dash
from dash import Input, Output, State, dcc, html
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from db import connect, list_customers, list_surveyors, survey_metrics_by_surveyor
from nav import parse_visualization_query
from theme import (
    CARD_STYLE,
    CHART_SERIES_PALETTE,
    COLORS,
    DROPDOWN_STYLE,
    FILTER_ROW_STYLE,
    PLOT_LAYOUT,
)

dash.register_page(__name__, path="/visualization", name="Visualization", title="Survey metrics", order=2)

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

SURVEYOR_PALETTE = CHART_SERIES_PALETTE

layout = html.Div(
    [
        html.Div(
            [
                html.H2("Detector time series", style={"marginTop": 0, "fontWeight": 700}),
                html.P(
                    "Choose customer, then surveyor. Charts use twin axes on flow and peak panels.",
                    style={"color": COLORS["muted"], "marginBottom": "1rem", "lineHeight": 1.5},
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label("Customer", style={"fontWeight": 600, "marginBottom": "0.35rem"}),
                                dcc.Dropdown(
                                    id="viz-customer-id",
                                    options=_customer_options,
                                    value=_default_customer,
                                    clearable=False,
                                    placeholder="Customer",
                                ),
                            ]
                        ),
                        html.Div(
                            [
                                html.Label("Surveyor", style={"fontWeight": 600, "marginBottom": "0.35rem"}),
                                dcc.Dropdown(
                                    id="viz-surveyor-ids",
                                    options=_initial_surveyor_options,
                                    value=[_initial_surveyor_options[0]["value"]]
                                    if _initial_surveyor_options
                                    else [],
                                    multi=True,
                                    placeholder="Surveyor unit(s)",
                                ),
                            ]
                        ),
                    ],
                    style=FILTER_ROW_STYLE,
                ),
                dcc.Graph(id="viz-timeseries-chart", style={"height": "680px", "marginTop": "0.5rem"}),
            ],
            style=CARD_STYLE,
        ),
    ]
)


@dash.callback(
    Output("viz-customer-id", "value"),
    Input("url", "pathname"),
    Input("url", "search"),
    State("viz-customer-id", "value"),
    prevent_initial_call=False,
)
def sync_customer_from_url(pathname, search, current_customer):
    if pathname != "/visualization":
        raise dash.exceptions.PreventUpdate
    url_customer, _ = parse_visualization_query(search)
    if url_customer:
        return url_customer
    return current_customer


@dash.callback(
    Output("viz-surveyor-ids", "options"),
    Output("viz-surveyor-ids", "value"),
    Input("viz-customer-id", "value"),
    Input("url", "search"),
    State("url", "pathname"),
)
def filter_surveyors(customer_id, search, pathname):
    if not customer_id:
        return [], []
    surveyors = list_surveyors(connect(), customer_id)
    options = [
        {"label": s["SurveyorUnit"] or s["SurveyorUnitId"], "value": s["SurveyorUnitId"]}
        for s in surveyors
    ]
    option_ids = {o["value"] for o in options}
    url_customer, url_surveyor = (
        parse_visualization_query(search) if pathname == "/visualization" else (None, None)
    )
    if url_customer == customer_id and url_surveyor and url_surveyor in option_ids:
        return options, [url_surveyor]
    return options, [options[0]["value"]] if options else []


@dash.callback(
    Output("viz-timeseries-chart", "figure"),
    Input("viz-customer-id", "value"),
    Input("viz-surveyor-ids", "value"),
)
def update_chart(customer_id, selected_ids):
    empty = go.Figure().update_layout(
        title="Select customer and surveyor",
        **PLOT_LAYOUT,
    )
    if not customer_id or not selected_ids:
        return empty

    detail_rows = survey_metrics_by_surveyor(connect(), selected_ids, customer_id)

    ts_fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            "Flow: AverageFlowRate (left) · FlowrateH (right)",
            "Peak: PeakMinutes (left) · PeakI (right)",
            "FaultH",
        ),
        specs=[[{"secondary_y": True}], [{"secondary_y": True}], [{"secondary_y": False}]],
        row_heights=[0.35, 0.35, 0.3],
    )

    by_surveyor: dict[str, list] = {}
    for row in detail_rows:
        by_surveyor.setdefault(row["SurveyorUnitId"], []).append(row)

    for idx, (_sid, rows) in enumerate(by_surveyor.items()):
        color = SURVEYOR_PALETTE[idx % len(SURVEYOR_PALETTE)]
        label = rows[0]["SurveyorUnit"] or _sid[:8]
        x = [r["StartDateTime"] for r in rows]

        ts_fig.add_trace(
            go.Scatter(
                x=x,
                y=[r["AverageFlowRate"] for r in rows],
                mode="lines",
                name=f"{label} · Avg flow",
                legendgroup=label,
                line=dict(color=color, width=2),
            ),
            row=1,
            col=1,
            secondary_y=False,
        )
        ts_fig.add_trace(
            go.Scatter(
                x=x,
                y=[r["FlowrateH"] for r in rows],
                mode="lines",
                name=f"{label} · FlowrateH",
                legendgroup=label,
                line=dict(color=color, width=1.5, dash="dot"),
            ),
            row=1,
            col=1,
            secondary_y=True,
        )
        ts_fig.add_trace(
            go.Scatter(
                x=x,
                y=[r["PeakMinutes"] for r in rows],
                mode="lines",
                name=f"{label} · Peak min",
                legendgroup=label,
                showlegend=False,
                line=dict(color=color, width=2),
            ),
            row=2,
            col=1,
            secondary_y=False,
        )
        ts_fig.add_trace(
            go.Scatter(
                x=x,
                y=[r["PeakI"] for r in rows],
                mode="lines",
                name=f"{label} · PeakI",
                legendgroup=label,
                showlegend=False,
                line=dict(color=color, width=1.5, dash="dash"),
            ),
            row=2,
            col=1,
            secondary_y=True,
        )
        ts_fig.add_trace(
            go.Scatter(
                x=x,
                y=[r["FaultH"] for r in rows],
                mode="lines",
                name=f"{label} · FaultH",
                legendgroup=label,
                showlegend=False,
                line=dict(color=COLORS["fault"], width=2),
            ),
            row=3,
            col=1,
        )

    ts_fig.update_layout(height=660, hovermode="x unified", **PLOT_LAYOUT)
    ts_fig.update_xaxes(
        showgrid=True,
        gridcolor=COLORS["border"],
        linecolor=COLORS["border"],
        row=3,
        col=1,
        title_text="Survey start time",
    )
    ts_fig.update_yaxes(
        title_text="AverageFlowRate",
        row=1,
        col=1,
        secondary_y=False,
        showgrid=True,
        gridcolor=COLORS["border"],
    )
    ts_fig.update_yaxes(
        title_text="FlowrateH",
        row=1,
        col=1,
        secondary_y=True,
        showgrid=False,
        title_font=dict(color=COLORS["flow_h"]),
    )
    ts_fig.update_yaxes(
        title_text="PeakMinutes",
        row=2,
        col=1,
        secondary_y=False,
        showgrid=True,
        gridcolor=COLORS["border"],
    )
    ts_fig.update_yaxes(
        title_text="PeakI",
        row=2,
        col=1,
        secondary_y=True,
        showgrid=False,
        title_font=dict(color=COLORS["peak_i"]),
    )
    ts_fig.update_yaxes(
        title_text="FaultH",
        row=3,
        col=1,
        showgrid=True,
        gridcolor=COLORS["border"],
    )

    return ts_fig