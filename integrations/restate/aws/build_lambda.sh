#!/bin/bash
# Build the Restate Lambda deployment package.
# Run BEFORE terraform apply.
#
# Usage:
#   cd integrations/restate/aws
#   bash build_lambda.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PKG_DIR="$SCRIPT_DIR/lambda_package"

echo "Installing Restate SDK into lambda_package/..."
uv pip install \
  --python python3.13 \
  --target "$PKG_DIR" \
  -r "$PKG_DIR/requirements.txt"

echo "Lambda package ready at: $PKG_DIR"
echo "Run 'terraform apply' to deploy."
