#!/usr/bin/env bash
# run_scenario.sh <sensitivity> <operation>
# Sends a GVM-SDK-compatible request to the local proxy and prints the decision.
# Used by demo.py and can be called manually from inside the sandbox.

SENSITIVITY=${1:-Medium}
OPERATION=${2:-read.document}
PROXY="http://127.0.0.1:8080"
TARGET="http://demo.api.example.com/v1/data"

RESOURCE_JSON=$(printf '{"sensitivity":"%s","type":"document"}' "$SENSITIVITY")
CONTEXT_JSON=$(printf '{"agent_id":"demo-agent","tenant_id":"acme","environment":"demo"}' )

response=$(curl -s -w "\n%{http_code}" \
    -X POST "$TARGET" \
    -H "X-GVM-Operation: $OPERATION" \
    -H "X-GVM-Resource: $RESOURCE_JSON" \
    -H "X-GVM-Context: $CONTEXT_JSON" \
    -H "Content-Type: application/json" \
    -d '{"query":"demo"}' \
    --max-time 5 2>/dev/null)

body=$(echo "$response" | head -n -1)
code=$(echo "$response" | tail -n 1)

echo "HTTP $code | op=$OPERATION sensitivity=$SENSITIVITY"
if [ "$code" = "403" ] || [ "$code" = "429" ]; then
    echo "$body" | jq -r '"  decision=\(.decision) reason=\(.reason) ic_level=\(.ic_level)"' 2>/dev/null || echo "  $body"
else
    echo "  Allowed — upstream response received"
fi
