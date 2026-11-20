"""Deep links between pages (query string helpers)."""
from __future__ import annotations

from urllib.parse import parse_qs, urlencode


def parse_visualization_query(search: str | None) -> tuple[str | None, str | None]:
    if not search:
        return None, None
    qs = parse_qs(search.lstrip("?"))
    customer = (qs.get("customer") or qs.get("customer_id") or [None])[0]
    surveyor = (qs.get("surveyor") or qs.get("surveyor_id") or [None])[0]
    return customer, surveyor


def visualization_href(customer_id: str, surveyor_id: str) -> str:
    return f"/visualization?{urlencode({'customer': customer_id, 'surveyor': surveyor_id})}"