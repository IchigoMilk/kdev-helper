#!/usr/bin/env bash

# Update .vscode/settings.json search excludes so only the selected ARCH stays searchable.
# Usage: vscode/update_arch_excludes.sh [arch]
# If no argument is provided, ARCH environment variable must be set.

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)
TARGET_ARCH=${1:-${ARCH:-}}
SETTINGS_PATH="$ROOT_DIR/.vscode/settings.json"
ARCH_DIR="$ROOT_DIR/arch"

if [[ -z "${TARGET_ARCH}" ]]; then
    echo "error: ARCH not provided. Pass it as an argument or export ARCH before running." >&2
    exit 1
fi

if [[ ! -d "$ARCH_DIR" ]]; then
    echo "error: missing arch directory at $ARCH_DIR" >&2
    exit 1
fi

if [[ ! -d "$ARCH_DIR/$TARGET_ARCH" ]]; then
    echo "error: arch/$TARGET_ARCH not found. Check the ARCH value." >&2
    exit 1
fi

python3 - "$ARCH_DIR" "$TARGET_ARCH" "$SETTINGS_PATH" <<'PY'
import json
import pathlib
import sys

arch_root = pathlib.Path(sys.argv[1])
target_arch = sys.argv[2]
settings_path = pathlib.Path(sys.argv[3])

arch_dirs = sorted([p.name for p in arch_root.iterdir() if p.is_dir()])

try:
    settings = json.loads(settings_path.read_text())
except FileNotFoundError:
    settings = {}
except Exception as exc:  # pragma: no cover - diagnostic path
    raise SystemExit(f"failed to parse {settings_path}: {exc}")

existing_excludes = settings.get("search.exclude", {})
preserved = {k: v for k, v in existing_excludes.items() if not k.startswith("arch/")}

for name in arch_dirs:
    pattern = f"arch/{name}/**"
    preserved[pattern] = name != target_arch

settings["search.exclude"] = preserved

settings_path.parent.mkdir(parents=True, exist_ok=True)
settings_path.write_text(json.dumps(settings, indent=4) + "\n")
print(f"Updated search.exclude for ARCH={target_arch}.")
PY
