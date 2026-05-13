#!/usr/bin/env bash
# generate_sbom.sh — Generate CycloneDX SBOMs for Maquita Webmail
# Usage: bash scripts/generate_sbom.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SBOM_DIR="$REPO_ROOT/sbom"

mkdir -p "$SBOM_DIR"

echo "=== Maquita Webmail — SBOM Generator ==="
echo ""

# ---- Backend SBOM (Python) ----
echo "[1/2] Generating backend SBOM from requirements.txt ..."

if ! command -v cyclonedx-py &>/dev/null; then
  echo "  -> Installing cyclonedx-bom ..."
  pip install --quiet cyclonedx-bom
fi

cyclonedx-py requirements \
  -i "$REPO_ROOT/backend/requirements.txt" \
  -o "$SBOM_DIR/backend-sbom.json" \
  --format json \
  2>/dev/null || \
cyclonedx-py \
  -i "$REPO_ROOT/backend/requirements.txt" \
  -o "$SBOM_DIR/backend-sbom.json" \
  --format json \
  2>/dev/null || \
echo "  [warn] cyclonedx-py failed — try: pip install cyclonedx-bom>=4"

echo "  -> $SBOM_DIR/backend-sbom.json"

# ---- Frontend SBOM (Node) ----
echo "[2/2] Generating frontend SBOM from package.json ..."

if [ ! -d "$REPO_ROOT/frontend/node_modules" ]; then
  echo "  -> Installing npm dependencies first ..."
  (cd "$REPO_ROOT/frontend" && npm ci --quiet)
fi

npx --yes @cyclonedx/cyclonedx-npm \
  --output-file "$SBOM_DIR/frontend-sbom.json" \
  --output-format JSON \
  "$REPO_ROOT/frontend"

echo "  -> $SBOM_DIR/frontend-sbom.json"

# ---- Summary ----
echo ""
echo "=== SBOM generation complete ==="
echo "Files:"
ls -lh "$SBOM_DIR"/*.json 2>/dev/null || echo "  (no files generated)"
echo ""
echo "Format: CycloneDX JSON"
echo "Upload to: https://deps.dev or https://dependency-track.org"
