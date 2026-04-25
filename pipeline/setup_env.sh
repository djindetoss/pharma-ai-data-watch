#!/bin/bash
# ── Pharma AI & Data Watch — first-time environment setup ────────────────────
# Run this once after cloning the repo:
#   bash pipeline/setup_env.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Pharma AI & Data Watch — environment setup"
echo "═══════════════════════════════════════════════════"
echo ""

if [ -f "$ENV_FILE" ]; then
  echo "  .env already exists — skipping creation."
else
  cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
  echo "  Created .env from template."
fi

echo ""
echo "  You need to add your API keys to: $ENV_FILE"
echo ""
echo "  1. PERPLEXITY_API_KEY  → https://www.perplexity.ai/settings/api"
echo "  2. ANTHROPIC_API_KEY   → https://console.anthropic.com/ (optional)"
echo "  3. NCBI_API_KEY        → https://www.ncbi.nlm.nih.gov/account/ (optional)"
echo ""

# Install Python dependencies
echo "  Installing Python dependencies…"
pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
echo "  ✓ Dependencies installed."
echo ""
echo "  Setup complete. Add your API keys to .env then run:"
echo "    python pipeline/pipeline.py --dry-run"
echo ""
