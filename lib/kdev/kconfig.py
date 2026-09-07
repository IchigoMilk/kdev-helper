"""Reading Linux .config files and reproducing include/generated/autoconf.h.

The kernel does not define CONFIG_FOO for a symbol set to 'm'; it defines
CONFIG_FOO_MODULE instead.  include/linux/kconfig.h relies on that split:

    #define IS_BUILTIN(option) __is_defined(option)
    #define IS_MODULE(option)  __is_defined(option##_MODULE)
    #define IS_ENABLED(option) __or(IS_BUILTIN(option), IS_MODULE(option))

Collapsing 'y' and 'm' onto the same macro makes IS_MODULE() and every
#ifdef CONFIG_FOO_MODULE block read as disabled, which hides exactly the code
a reader is looking for.  generate_autoconf() therefore mirrors Kconfig's own
output rules.

Prefer the real include/generated/autoconf.h whenever the tree has been
prepared; this module exists for trees where `make prepare` has not run yet.
"""

import hashlib
import os
import pathlib
import re

# CONFIG_FOO=y / =m / =123 / =0x10 / ="text".  Disabled symbols are written by
# Kconfig as "# CONFIG_FOO is not set" and never as "=n", so there is no 'n'
# case to handle here.
_ASSIGNMENT = re.compile(r"^(CONFIG_[A-Za-z0-9_]+)=(.*)$")

_ARCH_BY_SYMBOL = [
    ("CONFIG_X86_64", "x86"),
    ("CONFIG_X86", "x86"),
    ("CONFIG_ARM64", "arm64"),
    ("CONFIG_ARM", "arm"),
    ("CONFIG_RISCV", "riscv"),
    ("CONFIG_LOONGARCH", "loongarch"),
    ("CONFIG_PPC", "powerpc"),
    ("CONFIG_S390", "s390"),
    ("CONFIG_MIPS", "mips"),
    ("CONFIG_SPARC", "sparc"),
    ("CONFIG_PARISC", "parisc"),
    ("CONFIG_M68K", "m68k"),
    ("CONFIG_SUPERH", "sh"),
    ("CONFIG_XTENSA", "xtensa"),
    ("CONFIG_CSKY", "csky"),
    ("CONFIG_HEXAGON", "hexagon"),
    ("CONFIG_OPENRISC", "openrisc"),
    ("CONFIG_MICROBLAZE", "microblaze"),
    ("CONFIG_ARC", "arc"),
    ("CONFIG_ALPHA", "alpha"),
    ("CONFIG_NIOS2", "nios2"),
    ("CONFIG_UML", "um"),
]

# autoconf.h opens with a banner such as
#   * Linux/arm64 6.12.57 Kernel Configuration
_AUTOCONF_BANNER = re.compile(r"Linux/(\S+)\s+(\S+)\s+Kernel Configuration")


def parse_config(path):
    """Return {symbol: value} for every assignment in a .config."""
    symbols = {}
    for line in path.read_text(errors="replace").splitlines():
        if not line or line.startswith("#"):
            continue
        match = _ASSIGNMENT.match(line)
        if match:
            symbols[match.group(1)] = match.group(2)
    return symbols


def generate_autoconf(symbols, arch=None, version=None):
    """Render .config assignments using Kconfig's own macro naming rules."""
    banner = "Linux"
    if arch:
        banner += f"/{arch}"
    if version:
        banner += f" {version}"

    lines = [
        "/*",
        " * Automatically generated file; DO NOT EDIT.",
        f" * {banner} Kernel Configuration",
        " * Synthesised by kdev-helper from .config because",
        " * include/generated/autoconf.h was not present.",
        " */",
    ]

    for name, value in symbols.items():
        if value == "y":
            lines.append(f"#define {name} 1")
        elif value == "m":
            # The distinguishing case: 'm' becomes a _MODULE macro, not name=1.
            lines.append(f"#define {name}_MODULE 1")
        else:
            # Integers, hex and quoted strings pass through as Kconfig wrote
            # them; the quoting in .config is already C-compatible.
            lines.append(f"#define {name} {value}")

    return "\n".join(lines) + "\n"


def arch_from_autoconf(autoconf_path):
    """Read (arch, version) from an autoconf.h banner, or (None, None)."""
    try:
        with autoconf_path.open(errors="replace") as handle:
            for _ in range(10):
                line = handle.readline()
                if not line:
                    break
                match = _AUTOCONF_BANNER.search(line)
                if match:
                    return match.group(1), match.group(2)
    except OSError:
        pass
    return None, None


def arch_from_symbols(symbols):
    """Infer the kernel's ARCH directory name from enabled config symbols."""
    for symbol, arch in _ARCH_BY_SYMBOL:
        if symbols.get(symbol) == "y":
            return arch
    return None


def cache_dir():
    """Directory for artefacts kdev-helper derives from the user's tree.

    Deliberately outside the kernel tree: Yocto and other BSP workflows put
    the build output in directories that are wiped and regenerated, and some
    shared source trees are read-only.
    """
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return pathlib.Path(base) / "kdev-helper"


def cached_autoconf_path(objtree):
    """Stable per-objtree location for a synthesised autoconf.h.

    The basename stays autoconf.h so the path reads the same as the kernel's
    own header wherever it is reported; the parent directory disambiguates
    between build trees.
    """
    digest = hashlib.sha256(str(objtree).encode()).hexdigest()[:16]
    return cache_dir() / "autoconf" / f"{objtree.name}-{digest}" / "autoconf.h"
