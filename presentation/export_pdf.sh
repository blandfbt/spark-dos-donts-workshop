#!/usr/bin/env bash
# Export the presentation to a shareable PDF (one 16:9 page per slide) with headless Chrome/Chromium.
#
#   ./presentation/export_pdf.sh                       # -> presentation/spark_at_scale.pdf
#   ./presentation/export_pdf.sh deck.html out.pdf     # custom input/output
#
# Uses Google Chrome, Chromium or Microsoft Edge, whichever is found first. Set CHROME=/path/to/browser to override.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
input="$(cd "$(dirname "${1:-$here/spark_at_scale.html}")" && pwd)/$(basename "${1:-$here/spark_at_scale.html}")"
output="${2:-${input%.html}.pdf}"

if [[ -z "${CHROME:-}" ]]; then
  for candidate in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/Applications/Chromium.app/Contents/MacOS/Chromium" \
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
    "$(command -v google-chrome 2>/dev/null || true)" \
    "$(command -v google-chrome-stable 2>/dev/null || true)" \
    "$(command -v chromium 2>/dev/null || true)" \
    "$(command -v chromium-browser 2>/dev/null || true)" \
    "$(command -v msedge 2>/dev/null || true)"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then CHROME="$candidate"; break; fi
  done
fi
if [[ -z "${CHROME:-}" ]]; then
  echo "No Chrome/Chromium/Edge found. Install one, or set CHROME=/path/to/browser." >&2
  exit 1
fi

# The deck's print stylesheet lays out every slide as its own 1920x1080 page.
"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --run-all-compositor-stages-before-draw \
  --virtual-time-budget=10000 --print-to-pdf="$output" "file://$input" 2>/dev/null

echo "Wrote $output"
