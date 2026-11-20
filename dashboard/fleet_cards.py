"""Shared fleet / surveyor row cards."""
from dash import dcc, html

from db import classify_surveyor_status
from nav import visualization_href
from theme import COLORS, STATUS_STYLES


def status_legend() -> html.Div:
    return html.Div(
        [
            html.Span("Legend: ", style={"color": COLORS["muted"], "marginRight": "0.5rem"}),
            *[
                html.Span(
                    style["label"],
                    style={
                        "marginRight": "1rem",
                        "padding": "0.2rem 0.6rem",
                        "borderRadius": "6px",
                        "fontSize": "0.85rem",
                        "fontWeight": 600,
                        "backgroundColor": style["bg"],
                        "borderLeft": f"3px solid {style['border']}",
                    },
                )
                for style in STATUS_STYLES.values()
            ],
        ],
        style={"marginBottom": "1rem", "display": "flex", "flexWrap": "wrap", "alignItems": "center"},
    )


def _metric_cell(label: str, value: float, highlight: bool = False) -> html.Div:
    return html.Div(
        [
            html.Div(label, style={"fontSize": "0.75rem", "color": COLORS["muted"]}),
            html.Div(
                f"{value:.4f}",
                style={
                    "fontWeight": 600,
                    "fontVariantNumeric": "tabular-nums",
                    "color": COLORS["status_yellow"] if highlight else COLORS["text"],
                },
            ),
        ]
    )


def surveyor_card(
    row: dict,
    customer_id: str,
    *,
    show_customer: bool = False,
) -> html.Div:
    status_key, status_label = classify_surveyor_status(
        float(row["FlowrateH"]),
        float(row["PeakH"]),
        float(row["FaultH"]),
    )
    style = STATUS_STYLES[status_key]
    warn_flow = float(row["FlowrateH"]) > 0.5
    warn_peak = float(row["PeakH"]) > 0.5
    crit_fault = float(row["FaultH"]) > 0.8

    title_bits = [html.Strong(row["SurveyorUnit"] or "Unknown unit")]
    if show_customer:
        cname = row.get("CustomerName") or row.get("CustomerId") or ""
        title_bits.append(
            html.Span(
                cname,
                style={"marginLeft": "0.75rem", "fontSize": "0.85rem", "color": COLORS["muted"]},
            )
        )
    title_bits.append(
        html.Span(
            status_label,
            style={
                "marginLeft": "0.75rem",
                "fontSize": "0.8rem",
                "fontWeight": 700,
                "color": style["border"],
            },
        )
    )

    card_body = html.Div(
        [
            html.Div(
                [
                    html.Div(title_bits, style={"marginBottom": "0.35rem"}),
                    html.Div(
                        f"Last survey · {row['StartDateTime']}",
                        style={"fontSize": "0.8rem", "color": COLORS["muted"]},
                    ),
                ],
                style={"flex": "1", "minWidth": "200px"},
            ),
            html.Div(
                [
                    _metric_cell("FlowrateH", float(row["FlowrateH"]), warn_flow),
                    _metric_cell("PeakH", float(row["PeakH"]), warn_peak),
                    _metric_cell("FaultH", float(row["FaultH"]), crit_fault),
                ],
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(3, minmax(88px, 1fr))",
                    "gap": "1rem",
                },
            ),
        ],
        style={
            "display": "flex",
            "flexWrap": "wrap",
            "alignItems": "center",
            "justifyContent": "space-between",
            "gap": "1rem",
            "padding": "1rem 1.25rem",
            "borderRadius": "10px",
            "border": f"1px solid {COLORS['border']}",
            "borderLeft": f"5px solid {style['border']}",
            "backgroundColor": style["bg"],
        },
    )

    return html.Div(
        dcc.Link(
            card_body,
            href=visualization_href(customer_id, row["SurveyorUnitId"]),
            className="fleet-card-link",
        ),
        style={"marginBottom": "0.75rem"},
    )