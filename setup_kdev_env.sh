# shellcheck shell=bash

# Source this file to expose the helper commands in the current shell.
#
# Usage:
#   source /path/to/kdev-helper/setup_kdev_env.sh [--objtree DIR] [helper_dir] [kernel_root]
#
# With one positional argument it is the kernel source tree; with two, the
# first is the kdev-helper checkout and the second the kernel source tree.
# Put the line into ~/.bashrc to make the commands permanent.
#
# bash only.  The script relies on BASH_SOURCE to find its own location and on
# shell functions being exportable, neither of which behaves the same way in
# other shells.

if [ -z "${BASH_VERSION:-}" ]; then
    echo "kdev-helper: setup_kdev_env.sh requires bash." >&2
    return 1 2>/dev/null || exit 1
fi

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "kdev-helper: this script must be sourced, not executed." >&2
    exit 1
fi

_kdev_setup() {
    local helper_override= kernel_override= objtree_override=
    local -a positional=()

    while [[ $# -gt 0 ]]; do
        case $1 in
            -o|--objtree)
                if [[ $# -lt 2 ]]; then
                    echo "kdev-helper: $1 needs a directory argument" >&2
                    return 1
                fi
                objtree_override=$2
                shift 2
                ;;
            -h|--help)
                echo "usage: source setup_kdev_env.sh [--objtree DIR] [helper_dir] [kernel_root]"
                return 0
                ;;
            *)
                positional+=("$1")
                shift
                ;;
        esac
    done

    if [[ ${#positional[@]} -ge 2 ]]; then
        helper_override=${positional[0]}
        kernel_override=${positional[1]}
    elif [[ ${#positional[@]} -eq 1 ]]; then
        kernel_override=${positional[0]}
    fi

    local helper_dir
    if [[ -n "$helper_override" ]]; then
        if [[ ! -d "$helper_override" ]]; then
            echo "kdev-helper: helper override path not found: $helper_override" >&2
            return 1
        fi
        helper_dir=$(cd -- "$helper_override" && pwd)
    else
        # Inside a function BASH_SOURCE[0] is the file the function was
        # defined in, i.e. this script.
        helper_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
    fi

    if [[ ! -x "$helper_dir/bin/update_defines.sh" ]]; then
        echo "kdev-helper: $helper_dir does not contain bin/update_defines.sh" >&2
        return 1
    fi

    if [[ -n "$kernel_override" ]]; then
        if [[ ! -d "$kernel_override" ]]; then
            echo "kdev-helper: kernel root override not found: $kernel_override" >&2
            return 1
        fi
        KDEV_HELPER_KERNEL_ROOT=$(cd -- "$kernel_override" && pwd)
        export KDEV_HELPER_KERNEL_ROOT
    fi

    # Out-of-tree builds keep .config beside the build output rather than in
    # the source tree, so the two locations are configured independently.
    if [[ -n "$objtree_override" ]]; then
        if [[ ! -d "$objtree_override" ]]; then
            echo "kdev-helper: objtree override not found: $objtree_override" >&2
            return 1
        fi
        KDEV_HELPER_OBJTREE=$(cd -- "$objtree_override" && pwd)
        export KDEV_HELPER_OBJTREE
    fi

    KDEV_HELPER_DIR=$helper_dir
    export KDEV_HELPER_DIR

    # Functions rather than aliases: aliases are not expanded in
    # non-interactive shells, so an alias cannot be called from a script,
    # a Makefile or CI.
    unalias update_defines update_arch_excludes 2>/dev/null || true

    update_defines() { "$KDEV_HELPER_DIR/bin/update_defines.sh" "$@"; }
    update_arch_excludes() { "$KDEV_HELPER_DIR/bin/update_arch_excludes.sh" "$@"; }
    export -f update_defines update_arch_excludes
}

_kdev_setup "$@"
_kdev_setup_status=$?
unset -f _kdev_setup
if [[ $_kdev_setup_status -ne 0 ]]; then
    unset _kdev_setup_status
    return 1
fi
unset _kdev_setup_status
