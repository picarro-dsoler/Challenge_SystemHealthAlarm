"""PostgreSQL connection for System Health dashboard (SystemHealth_EU)."""
from __future__ import annotations

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv(override=True)

_ENGINE = None


def get_engine():
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    host = os.environ.get("ALARM_HOST", os.environ.get("PGHOST", "localhost"))
    database = os.environ.get("ALARM_DATABASE", os.environ.get("PGDATABASE", "SystemHealth_EU"))
    user = os.environ.get("ALARM_USER", os.environ.get("PGUSER", "dsoler"))
    password = os.environ.get("ALARM_PASSWORD", os.environ.get("PGPASSWORD", ""))
    port = os.environ.get("ALARM_PORT", os.environ.get("PGPORT", "5432"))
    url = (
        f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(database)}"
    )
    _ENGINE = create_engine(url, pool_pre_ping=True)
    return _ENGINE


def connection_label() -> str:
    database = os.environ.get("ALARM_DATABASE", os.environ.get("PGDATABASE", "SystemHealth_EU"))
    host = os.environ.get("ALARM_HOST", os.environ.get("PGHOST", "localhost"))
    return f"PostgreSQL · {database} @ {host}"