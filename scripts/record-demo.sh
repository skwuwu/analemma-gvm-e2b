#!/usr/bin/env bash
# Record the e2b demo with asciinema.
# Run from the repo root inside WSL or Linux:
#   bash scripts/record-demo.sh
#
# Prerequisites:
#   pip install asciinema
#   e2b auth login (or set E2B_API_KEY)
#   pip install -r requirements.txt

set -euo pipefail
cd "$(dirname "$0")/.."

CAST_FILE="demo.cast"

echo "Recording demo to ${CAST_FILE} ..."
asciinema rec \
  --title "Analemma GVM — e2b Demo" \
  --command "python demo.py" \
  --overwrite \
  "${CAST_FILE}"

echo ""
echo "Done. Upload with:"
echo "  asciinema upload ${CAST_FILE}"
echo ""
echo "Then paste the URL into README.md."
