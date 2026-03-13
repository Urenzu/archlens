#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENGINE_DIR="$SCRIPT_DIR/../engine"

cd "$ENGINE_DIR"

export CFLAGS_wasm32_unknown_unknown="-isystem $ENGINE_DIR/wasm-stubs -Wno-everything -DNDEBUG"

wasm-pack build --target web --out-dir ../frontend/pkg "$@"

echo "WASM bundle built: frontend/pkg/"
ls -lh ../frontend/pkg/*.wasm
