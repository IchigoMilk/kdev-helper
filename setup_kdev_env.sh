# shellcheck shell=bash

# Source this file to register convenient aliases for the helper scripts.
# Usage:
#   source /path/to/kdev-helper/setup_kdev_env.sh [helper_dir_override] [kernel_root]
# Place the line above (with an optional kernel_root) into your shell rc file to make the aliases permanent.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "This script must be sourced, not executed." >&2
    exit 1
fi

_helper_override=
_kernel_override=

if [[ $# -ge 2 ]]; then
    _helper_override=$1
    _kernel_override=$2
elif [[ $# -eq 1 ]]; then
    _kernel_override=$1
fi

if [[ -n "$_helper_override" ]]; then
    if [[ ! -d "$_helper_override" ]]; then
        echo "error: helper override path not found: $_helper_override" >&2
        return 1
    fi
    _kdev_helper_dir=$(cd "$_helper_override" && pwd)
else
    _kdev_helper_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
fi

if [[ -n "$_kernel_override" ]]; then
    if [[ ! -d "$_kernel_override" ]]; then
        echo "error: kernel root override not found: $_kernel_override" >&2
        return 1
    fi
    export KDEV_HELPER_KERNEL_ROOT=$(cd "$_kernel_override" && pwd)
fi

alias update_arch_excludes="$_kdev_helper_dir/bin/update_arch_excludes.sh"
alias update_defines="$_kdev_helper_dir/bin/update_defines.sh"

unset _kdev_helper_dir
unset _helper_override
unset _kernel_override
