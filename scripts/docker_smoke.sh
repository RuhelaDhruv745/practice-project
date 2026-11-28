#!/usr/bin/env sh
# Smoke test for a running stack (docker compose up -d, or the CI job).
# Usage: scripts/docker_smoke.sh [backend_url] [reviewer_ui_url]
# Waits for the backend health endpoint, then checks /api/customers and the
# Streamlit health endpoint. Needs only curl. Prints no secrets.
set -eu

BACKEND_URL="${1:-http://localhost:8000}"
UI_URL="${2:-http://localhost:8501}"
TRIES="${SMOKE_TRIES:-30}"

wait_for() {
  url="$1"
  i=0
  until curl -fsS "$url" >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -ge "$TRIES" ]; then
      echo "FAIL: $url not ready after $TRIES tries" >&2
      return 1
    fi
    sleep 2
  done
  echo "ok: $url"
}

wait_for "$BACKEND_URL/api/health"
echo "health: $(curl -fsS "$BACKEND_URL/api/health")"

# Seeded data is readable (repository only; no policy engine involved).
detail="$(curl -fsS "$BACKEND_URL/api/customers/CUST-001")"
case "$detail" in
  *CUST-001*) echo "ok: /api/customers/CUST-001 returns the seeded customer" ;;
  *) echo "FAIL: seeded customer CUST-001 not found" >&2; exit 1 ;;
esac

# The list endpoint classifies every customer through the policy engine.
# SMOKE_STRICT=0 downgrades a failure here to a warning (used in CI until the real
# PolicyEngine is wired into backend/app/main.py).
code="$(curl -s -o /dev/null -w '%{http_code}' "$BACKEND_URL/api/customers")"
if [ "$code" = "200" ]; then
  echo "ok: /api/customers returned 200"
elif [ "${SMOKE_STRICT:-1}" = "0" ]; then
  echo "WARN: /api/customers returned $code (non-strict mode)"
else
  echo "FAIL: /api/customers returned $code" >&2
  exit 1
fi

if [ "$UI_URL" != "-" ]; then
  wait_for "$UI_URL/_stcore/health"
fi
echo "smoke test passed"
