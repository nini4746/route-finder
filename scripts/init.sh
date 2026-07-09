#!/usr/bin/env bash
# Idempotent harness skeleton creator. Safe to run multiple times.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$ROOT/docs/design-docs"
mkdir -p "$ROOT/docs/exec-plans/active"
mkdir -p "$ROOT/docs/exec-plans/completed"
mkdir -p "$ROOT/docs/generated"
mkdir -p "$ROOT/docs/product-specs"
mkdir -p "$ROOT/docs/references"

echo "harness skeleton ready under $ROOT"
