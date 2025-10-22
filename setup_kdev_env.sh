# shellcheck shell=bash

# Source this file to register convenient aliases for the helper scripts.
# Usage:
#   export KDEV_HELPER_KERNEL_ROOT=/path/to/linux
#   source /path/to/kdev-helper/setup_kdev_env.sh
# Place the two lines above into your shell rc file to make the aliases permanent.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "This script must be sourced, not executed." >&2
    exit 1
fi

_kdev_kdev_helper_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

alias update_arch_excludes="$_kdev_helper_dir/bin/update_arch_excludes.sh"
alias update_defines="$_kdev_helper_dir/bin/update_defines.sh"

unset _kdev_helper_dir
