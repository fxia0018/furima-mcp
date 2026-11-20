#!/usr/bin/env bash
# Build dist/furima-mcp-<version>.mcpb, a one-click Claude Desktop extension.
# Usage: mcpb/build.sh   (needs npx)
set -euo pipefail
cd "$(dirname "$0")/.."
version=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
cp -R pyproject.toml uv.lock README.md LICENSE src "$stage/"
find "$stage/src" -name __pycache__ -prune -exec rm -rf {} +
cp mcpb/main.py "$stage/main.py"
cp docs/logo.png "$stage/icon.png"
sed "s/\"version\": \"0.0.0\"/\"version\": \"$version\"/" mcpb/manifest.json > "$stage/manifest.json"
mkdir -p dist
npx -y @anthropic-ai/mcpb@2.1.2 validate "$stage/manifest.json"
npx -y @anthropic-ai/mcpb@2.1.2 pack "$stage" "dist/furima-mcp-$version.mcpb"
