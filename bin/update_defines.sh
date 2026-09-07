#!/usr/bin/env bash

# Point VS Code IntelliSense at the kernel configuration for the current build.
# Run with --help for the full option list.

set -euo pipefail

_here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

PYTHONPATH="$_here/../lib${PYTHONPATH:+:$PYTHONPATH}" \
    exec python3 -c '
import sys
sys.argv[0] = "update_defines"   # so --help shows the command, not "-c"
from kdev import cli_defines
sys.exit(cli_defines.main())
' "$@"
