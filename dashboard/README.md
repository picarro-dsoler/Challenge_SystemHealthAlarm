# System Health Alarm dashboard

Multipage Plotly Dash over **`SystemHealth_EU`** on PostgreSQL (same instance as KPIHub: `kpihub-postgis`).

| Page | Route | Purpose |
|------|-------|---------|
| **Fleet / Init overview** | `/fleet`, `/init` | Surveyor status cards by customer |
| **Visualization** | `/` | Fleet metrics and per-survey time series |
| **Config** | `/config` | Load/update `ConfigParams` (writes to the DB) |

Port **8051** (KPIHub weekly KPI dashboard uses **8052**).

## Run (recommended — Docker)

```bash
docker network create kpihub-net 2>/dev/null || true
cd Challenges/Challenge_SystemHealthAlarm/r2/dashboard
./run.sh
```

Open **http://localhost:8051**

Uses repo `.env` (`ALARM_USER`, `ALARM_PASSWORD`, …) and connects to **`ALARM_HOST=kpihub-postgis`**, **`ALARM_DATABASE=SystemHealth_EU`**.

Ensure `SystemHealth_EU` exists (first boot of `kpihub-postgis` runs `02-init-systemhealth.sh`) and alarm tables are populated (e.g. `lib/Setup.py` / detector pipeline against Postgres).

Stop: `docker compose down`

## Run locally (Postgres on localhost)

```bash
cd Challenges/Challenge_SystemHealthAlarm/r2/dashboard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export ALARM_HOST=localhost
export ALARM_PORT=5432
export ALARM_DATABASE=SystemHealth_EU
export ALARM_USER=dsoler
export ALARM_PASSWORD=dsoler
python app.py
```

Optional: load from repo root `.env` with `python-dotenv` (enabled in `db_conn.py`).

## SQLite (legacy / offline file only)

```bash
export ALARM_DB_BACKEND=sqlite
export ALARM_DB_PATH=../database/SystemHealthAlarm_Alarms.db
python app.py
```

## Layout vs KPIHub dashboard

Same pattern as [`KPIHub/dashboard`](../../../../KPIHub/dashboard): Docker + shared **`kpihub-net`**, Postgres env vars instead of a SQLite bind mount.