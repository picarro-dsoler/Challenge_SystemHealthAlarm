#!/usr/bin/env bash
# Configure AWS SSO profile for DataExtractor_Athena.ipynb
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
AWS_DIR="${HOME}/.aws"
AWS_CONFIG="${AWS_DIR}/config"

# Prefer project venv AWS CLI, then local install, then system
if [[ -x "${REPO_ROOT}/.venv/bin/aws" ]]; then
  AWS="${REPO_ROOT}/.venv/bin/aws"
elif [[ -x "${HOME}/.local/bin/aws" ]]; then
  AWS="${HOME}/.local/bin/aws"
else
  AWS="aws"
fi

load_env() {
  if [[ -f "${ENV_FILE}" ]]; then
    eval "$(python3 - <<'PY'
from pathlib import Path
for line in Path(r"'"${ENV_FILE}"'").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    k, v = k.strip(), v.strip()
    if k.startswith("AWS_"):
        v = v.replace("'", "'\\''")
        print(f"export {k}='{v}'")
PY
)"
  fi
}

load_env

PROFILE="${AWS_ATHENA_US_PROFILE:-Data-Analytics-Athena-User-580855453261}"
ACCOUNT_ID="${AWS_ATHENA_ACCOUNT_ID:-580855453261}"
ROLE_NAME="${AWS_ATHENA_ROLE_NAME:-Data-Analytics-Athena-User}"
REGION="${AWS_ATHENA_DYNAMOEXPORTS_REGION:-us-west-2}"
SSO_START_URL="${AWS_SSO_START_URL:-}"
SSO_REGION="${AWS_SSO_REGION:-us-west-2}"

echo "=== Athena AWS setup ==="
echo "Profile:  ${PROFILE}"
echo "Account:  ${ACCOUNT_ID}"
echo "Role:     ${ROLE_NAME}"
echo "Region:   ${REGION}"
echo

if ! command -v "${AWS}" >/dev/null 2>&1; then
  echo "AWS CLI not found."
  echo "Install it with:"
  echo "  curl -fsSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscliv2.zip"
  echo "  python3 -c \"import zipfile; zipfile.ZipFile('/tmp/awscliv2.zip').extractall('/tmp/awscliv2')\""
  echo "  chmod +x /tmp/awscliv2/aws/install && /tmp/awscliv2/aws/install -i ~/.local/aws-cli -b ~/.local/bin"
  exit 1
fi

"${AWS}" --version
echo

if [[ -z "${SSO_START_URL}" ]]; then
  echo "AWS_SSO_START_URL is not set in ${ENV_FILE}"
  echo
  echo "Add your organization's AWS Access Portal URL to .env, for example:"
  echo "  AWS_SSO_START_URL=https://d-xxxxxxxxxx.awsapps.com/start"
  echo "  AWS_SSO_REGION=us-east-1"
  echo
  echo "You can find this URL in the AWS IAM Identity Center console under"
  echo "'AWS access portal URL', or ask your AWS admin."
  echo
  read -r -p "Paste your SSO start URL now (or press Enter to exit): " SSO_START_URL
  if [[ -z "${SSO_START_URL}" ]]; then
    echo "Aborted. Set AWS_SSO_START_URL in .env and re-run this script."
    exit 1
  fi
fi

mkdir -p "${AWS_DIR}"
chmod 700 "${AWS_DIR}"

cat > "${AWS_CONFIG}" <<EOF
[default]
region = ${REGION}

[profile ${PROFILE}]
sso_start_url = ${SSO_START_URL}
sso_region = ${SSO_REGION}
sso_account_id = ${ACCOUNT_ID}
sso_role_name = ${ROLE_NAME}
region = ${REGION}
EOF

chmod 600 "${AWS_CONFIG}"

echo "Wrote ${AWS_CONFIG}"
echo
echo "Logging in to AWS SSO (browser or device code)..."
"${AWS}" sso login --profile "${PROFILE}"

echo
echo "Verifying credentials..."
"${AWS}" sts get-caller-identity --profile "${PROFILE}"

echo
echo "Testing Athena access..."
"${AWS}" athena list-work-groups --profile "${PROFILE}" --region "${REGION}" --max-results 5

echo
echo "Setup complete. Re-run DataExtractor_Athena.ipynb from the top."
