#!/usr/bin/env bash

# Update .vscode/c_cpp_properties.json defines array from a Linux kernel .config.
# Usage: vscode/update_defines.sh [path-to-.config] [path-to-c_cpp_properties.json]

set -euo pipefail

resolve_root() {
    local candidate

    if [[ -n "${KDEV_HELPER_KERNEL_ROOT:-}" ]]; then
        candidate=${KDEV_HELPER_KERNEL_ROOT}
        if [[ ! -d "$candidate" ]]; then
            echo "error: KDEV_HELPER_KERNEL_ROOT points to a missing directory: $candidate" >&2
            exit 1
        fi
        (cd "$candidate" && pwd)
        return
    fi

    local script_dir
    script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    for candidate in "$script_dir" "$script_dir/.." "$script_dir/../.."; do
        if [[ -f "$candidate/.config" || -d "$candidate/arch" ]]; then
            (cd "$candidate" && pwd)
            return
        fi
    done

    echo "error: unable to locate kernel root. Set KDEV_HELPER_KERNEL_ROOT to your kernel tree." >&2
    exit 1
}

ROOT_DIR=$(resolve_root)
CONFIG_PATH=${1:-"$ROOT_DIR/.config"}
PROPERTIES_PATH=${2:-"$ROOT_DIR/.vscode/c_cpp_properties.json"}

if [[ ! -f "$CONFIG_PATH" ]]; then
    echo "error: missing kernel config at $CONFIG_PATH" >&2
    exit 1
fi

if [[ ! -f "$PROPERTIES_PATH" ]]; then
    echo "error: missing VS Code properties file at $PROPERTIES_PATH" >&2
    exit 1
fi

python3 - "$CONFIG_PATH" "$PROPERTIES_PATH" <<'PY'
import json
import pathlib
import re
import sys

config_path = pathlib.Path(sys.argv[1])
props_path = pathlib.Path(sys.argv[2])

try:
    props = json.loads(props_path.read_text())
except Exception as exc:  # pragma: no cover - diagnostic path
    raise SystemExit(f"failed to parse {props_path}: {exc}")

define_pattern = re.compile(r"^CONFIG_([A-Za-z0-9_]+)=(.*)$")
defines_from_config = []

for line in config_path.read_text().splitlines():
    if not line or line.startswith('#'):
        continue
    match = define_pattern.match(line)
    if not match:
        continue
    name, value = match.groups()
    if value in {'y', 'm'}:
        defines_from_config.append(f"CONFIG_{name}=1")
    elif value == 'n':
        continue
    else:
        defines_from_config.append(f"CONFIG_{name}={value}")

for entry in props.get("configurations", []):
    existing = entry.get("defines", [])
    preserved = [item for item in existing if not item.startswith("CONFIG_")]
    merged = []
    for item in preserved + defines_from_config:
        if item not in merged:
            merged.append(item)
    entry["defines"] = merged

props_path.write_text(json.dumps(props, indent=4) + "\n")
print(f"Updated defines for {len(props.get('configurations', []))} configuration(s) using {config_path}.")
PY

