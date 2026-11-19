#!/usr/bin/env bash
# End-to-end check of a running deployment: page, API, login flow, CSRF and a
# real verification with all three provers.
#   scripts/smoke_test.sh https://localhost
set -euo pipefail

BASE="${1:-https://localhost}"
JAR="$(mktemp)"
trap 'rm -f "$JAR"' EXIT
CURL=(curl -fsS --insecure -c "$JAR" -b "$JAR" -H "Origin: ${BASE}")
json() { python3 -c "import json,sys; print(json.load(sys.stdin)$1)"; }

"${CURL[@]}" "$BASE/" | grep -q "<title>Formal Verification Platform</title>"
"${CURL[@]}" "$BASE/api/health" | grep -q '"ok"'

token=$("${CURL[@]}" "$BASE/api/auth/csrf" | json "['csrf_token']")
email="smoke-$(date +%s)@example.com"
token=$("${CURL[@]}" -H "X-CSRF-Token: $token" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$email\",\"password\":\"smoke-test-password-1\"}" "$BASE/api/auth/register" | json "['csrf_token']")

status=$(curl -sS --insecure -b "$JAR" -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' \
  -d '{"source":"fof(a, axiom, p)."}' "$BASE/api/validate")
[ "$status" = "403" ] || { echo "CSRF protection missing (got $status)"; exit 1; }

result=$("${CURL[@]}" -H "X-CSRF-Token: $token" -H 'Content-Type: application/json' -d '{
  "title": "Smoke test",
  "source": "fof(a, axiom, ![X]: (man(X) => mortal(X))).\nfof(b, axiom, man(socrates)).\nfof(c, conjecture, mortal(socrates)).",
  "provers": ["spass", "vampire", "otter"], "time_limit": 10}' "$BASE/api/verify")
echo "$result" | python3 -c '
import json, sys
run = json.load(sys.stdin)
print("verdict:", run["verdict"], run["statuses"])
assert run["verdict"] == "theorem", run
assert set(run["statuses"].values()) == {"Theorem"}, run["statuses"]
'
echo "smoke test passed"
