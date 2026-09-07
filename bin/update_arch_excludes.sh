#!/usr/bin/env bash

# Hide architectures other than the one being built from VS Code.
# Run with --help for the full option list.

set -euo pipefail

_here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

PYTHONPATH="$_here/../lib${PYTHONPATH:+:$PYTHONPATH}" \
    exec python3 -c '
import sys
sys.argv[0] = "update_arch_excludes"   # so --help shows the command, not "-c"
from kdev import cli_excludes
sys.exit(cli_excludes.main())
' "$@"
