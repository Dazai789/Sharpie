#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

for script in "$ROOT"/examples/basic/*.sh "$ROOT"/examples/advanced/*.sh; do
    output=$(python3 "$ROOT/sharpie.py" "$script")
    tmp=$(mktemp "${TMPDIR:-/tmp}/sharpie.XXXXXX.py")
    printf '%s\n' "$output" > "$tmp"
    python3 -m py_compile "$tmp"
    rm -f "$tmp"
    printf 'ok %s\n' "${script#$ROOT/}"
done
