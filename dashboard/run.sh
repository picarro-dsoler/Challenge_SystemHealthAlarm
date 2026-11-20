#!/usr/bin/env bash
# Run System Health Alarm dashboard in Docker (no local Dash install required).
set -euo pipefail
cd "$(dirname "$0")"
docker compose up --build -d
echo "Open http://localhost:8051"
echo "Logs: docker compose logs -f system-health-dash"