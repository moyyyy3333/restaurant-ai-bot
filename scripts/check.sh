#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 -m unittest discover tests
python3 -m tests.test_site_quality
python3 -m tests.test_website_accuracy

check_dir="$(mktemp -d)"
port="${CHECK_PORT:-41873}"
server_pid=""
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  rm -rf "$check_dir"
}
trap cleanup EXIT

LOCAL_DB_PATH="$check_dir/check.db" \
PORT="$port" \
PIPELINE_SCAN_BUDGET=0 \
DAILY_SEND_LIMIT=0 \
python3 server.py >"$check_dir/server.log" 2>&1 &
server_pid=$!

for _ in {1..20}; do
  if curl --fail --silent --max-time 1 \
    "http://127.0.0.1:$port/health" >"$check_dir/health.json"; then
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    cat "$check_dir/server.log"
    exit 1
  fi
  sleep 0.25
done

python3 -c \
  'import json,sys; data=json.load(open(sys.argv[1])); assert data["ok"]' \
  "$check_dir/health.json"

LOCAL_DB_PATH="$check_dir/dry-run.db" \
PIPELINE_SCAN_BUDGET=0 \
python3 scripts/pipeline_dry_run.py --scan-budget 0

echo "check: tests, pipeline dry run, and /health passed"
