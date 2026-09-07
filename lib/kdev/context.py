"""Resolving where the kernel source, the build output and ARCH actually are.

Both helper scripts used to carry their own copy of a resolve_root() that
returned a single directory and derived .config, arch/ and .vscode/ from it.
That works only for an in-tree build.  Out-of-tree builds -- `make O=...`,
Yocto, Buildroot, vendor BSPs -- keep the source and the build output in
separate directories:

    kernel-source/            Makefile, Kconfig, arch/ (every architecture)
    kernel-build-artifacts/   .config, include/generated/, arch/<one arch>/

Pointing a single variable at either directory breaks one of the two helpers,
so srctree and objtree are tracked separately here and everything else is
derived from the pair.
"""

import argparse
import dataclasses
import os
import pathlib
import sys

from . import kconfig

ENV_SRCTREE = "KDEV_HELPER_KERNEL_ROOT"
ENV_OBJTREE = "KDEV_HELPER_OBJTREE"
ENV_VSCODE_DIR = "KDEV_HELPER_VSCODE_DIR"


class ResolveError(SystemExit):
    """Fatal resolution failure.  The message always names a next step."""

    def __init__(self, message):
        super().__init__(f"error: {message}")


@dataclasses.dataclass
class KdevContext:
    srctree: pathlib.Path
    objtree: pathlib.Path
    arch: str
    config: pathlib.Path
    autoconf: pathlib.Path | None
    vscode_dir: pathlib.Path
    kernel_version: str | None

    @property
    def in_tree(self):
        return self.srctree == self.objtree

    @property
    def arch_dir(self):
        return self.srctree / "arch"

    def available_arches(self):
        """Architecture directory names, always enumerated from the srctree.

        The objtree only contains the architecture that was built, so using it
        here would silently shrink the exclude list to a single entry.
        """
        return sorted(p.name for p in self.arch_dir.iterdir() if p.is_dir())

    def as_dict(self):
        data = dataclasses.asdict(self)
        for key, value in list(data.items()):
            if isinstance(value, pathlib.Path):
                data[key] = str(value)
        data["in_tree"] = self.in_tree
        return data

    def describe(self, stream=sys.stderr):
        layout = "in-tree" if self.in_tree else "split tree"
        print(f"  srctree  {self.srctree}", file=stream)
        print(f"  objtree  {self.objtree}  ({layout})", file=stream)
        print(f"  arch     {self.arch}", file=stream)
        if self.kernel_version:
            print(f"  version  {self.kernel_version}", file=stream)


def _is_srctree(path):
    return (
        (path / "Makefile").is_file()
        and (path / "Kconfig").is_file()
        and (path / "arch").is_dir()
    )


def _is_objtree(path):
    return (path / ".config").is_file() or (
        path / "include" / "generated" / "autoconf.h"
    ).is_file()


def _resolved(path, what):
    candidate = pathlib.Path(path).expanduser()
    if not candidate.is_dir():
        raise ResolveError(f"{what} is not a directory: {candidate}")
    return candidate.resolve()


def _find_srctree_upwards(start):
    for candidate in [start, *start.parents]:
        if _is_srctree(candidate):
            return candidate
    return None


def resolve_srctree(explicit=None):
    """Locate the kernel source tree.

    Order: --srctree, $KDEV_HELPER_KERNEL_ROOT, then a walk up from $PWD.  The
    walk starts at the current directory rather than at the install directory
    of these scripts, so running the helpers from inside a kernel tree works
    without any configuration.
    """
    if explicit:
        path = _resolved(explicit, "--srctree")
        if not _is_srctree(path):
            raise ResolveError(
                f"{path} does not look like a kernel source tree "
                f"(expected Makefile, Kconfig and arch/ inside it)."
            )
        return path

    env = os.environ.get(ENV_SRCTREE)
    if env:
        path = _resolved(env, f"${ENV_SRCTREE}")
        if not _is_srctree(path):
            raise ResolveError(
                f"${ENV_SRCTREE} points at {path}, which does not look like a "
                f"kernel source tree (expected Makefile, Kconfig and arch/).\n"
                f"hint: for a split source/build layout this variable must "
                f"point at the source tree; pass the build directory via "
                f"--objtree or ${ENV_OBJTREE}."
            )
        return path

    found = _find_srctree_upwards(pathlib.Path.cwd().resolve())
    if found:
        return found

    raise ResolveError(
        "unable to locate a kernel source tree.\n"
        "hint: run this from inside the kernel tree, or set it explicitly:\n"
        f"      export {ENV_SRCTREE}=/path/to/linux"
    )


def resolve_objtree(srctree, explicit=None):
    """Locate the build output directory that owns .config.

    Order: --objtree, $KDEV_HELPER_OBJTREE, $O, $KBUILD_OUTPUT, then the
    srctree itself for an ordinary in-tree build.  Nothing is guessed beyond
    that: silently falling back to a tree without a .config produced the
    confusing "missing kernel config" failure this replaces.
    """
    for value, what in (
        (explicit, "--objtree"),
        (os.environ.get(ENV_OBJTREE), f"${ENV_OBJTREE}"),
        (os.environ.get("O"), "$O"),
        (os.environ.get("KBUILD_OUTPUT"), "$KBUILD_OUTPUT"),
    ):
        if value:
            path = _resolved(value, what)
            if not _is_objtree(path):
                raise ResolveError(
                    f"{what} points at {path}, which has no .config and no "
                    f"include/generated/autoconf.h.\n"
                    f"hint: run `make O={path} olddefconfig prepare` first."
                )
            return path

    if _is_objtree(srctree):
        return srctree

    raise ResolveError(
        f"no kernel .config found in {srctree}.\n"
        "hint: if this tree was built out-of-tree, point the helper at the "
        "build directory:\n"
        f"      export {ENV_OBJTREE}=/path/to/build\n"
        "      (or pass --objtree /path/to/build)\n"
        "      For an in-tree build, run `make defconfig` first."
    )


def resolve_arch(srctree, objtree, symbols, explicit=None):
    """Determine the arch/ directory name for this build.

    Order: --arch, $ARCH, the autoconf.h banner, the enabled CONFIG_<ARCH>
    symbol, and finally a build directory that contains exactly one arch.
    Auto-detection matters because the kernel's directory names do not match
    uname -m: aarch64 is arm64, x86_64 is x86.
    """
    if explicit:
        return _validated_arch(srctree, explicit, "--arch")

    env = os.environ.get("ARCH")
    if env:
        return _validated_arch(srctree, env, "$ARCH")

    autoconf = objtree / "include" / "generated" / "autoconf.h"
    if autoconf.is_file():
        detected, _ = kconfig.arch_from_autoconf(autoconf)
        if detected and (srctree / "arch" / detected).is_dir():
            return detected

    detected = kconfig.arch_from_symbols(symbols)
    if detected and (srctree / "arch" / detected).is_dir():
        return detected

    built = [p.name for p in (objtree / "arch").iterdir() if p.is_dir()] if (
        objtree / "arch"
    ).is_dir() else []
    if len(built) == 1 and (srctree / "arch" / built[0]).is_dir():
        return built[0]

    raise ResolveError(
        "unable to determine ARCH.\n"
        "hint: pass it explicitly, e.g. `--arch arm64`, or `export ARCH=arm64`.\n"
        f"      available: {', '.join(sorted(p.name for p in (srctree / 'arch').iterdir() if p.is_dir()))}"
    )


def _validated_arch(srctree, arch, what):
    if not (srctree / "arch" / arch).is_dir():
        available = sorted(
            p.name for p in (srctree / "arch").iterdir() if p.is_dir()
        )
        raise ResolveError(
            f"{what}={arch} has no arch/{arch} directory in {srctree}.\n"
            f"hint: the kernel's name may differ from uname -m "
            f"(aarch64 -> arm64, x86_64 -> x86).\n"
            f"      available: {', '.join(available)}"
        )
    return arch


def resolve(args):
    """Build a KdevContext from parsed command line arguments."""
    srctree = resolve_srctree(getattr(args, "srctree", None))
    objtree = resolve_objtree(srctree, getattr(args, "objtree", None))

    config = objtree / ".config"
    symbols = kconfig.parse_config(config) if config.is_file() else {}

    arch = resolve_arch(srctree, objtree, symbols, getattr(args, "arch", None))

    autoconf = objtree / "include" / "generated" / "autoconf.h"
    version = None
    if autoconf.is_file():
        _, version = kconfig.arch_from_autoconf(autoconf)
    else:
        autoconf = None

    vscode_dir = getattr(args, "vscode_dir", None) or os.environ.get(ENV_VSCODE_DIR)
    # Defaults to the source tree: a Yocto build directory can be wiped and
    # regenerated, which would take the editor configuration with it.
    vscode_dir = (
        pathlib.Path(vscode_dir).expanduser().resolve()
        if vscode_dir
        else srctree / ".vscode"
    )

    return KdevContext(
        srctree=srctree,
        objtree=objtree,
        arch=arch,
        config=config,
        autoconf=autoconf,
        vscode_dir=vscode_dir,
        kernel_version=version,
    )


def common_parser(description):
    """Argument parser carrying the options every helper understands."""
    parser = argparse.ArgumentParser(description=description)
    locate = parser.add_argument_group("tree location")
    locate.add_argument(
        "--srctree",
        metavar="DIR",
        help=f"kernel source tree (default: ${ENV_SRCTREE}, else search upward from $PWD)",
    )
    locate.add_argument(
        "--objtree",
        metavar="DIR",
        help=f"build output holding .config (default: ${ENV_OBJTREE}, $O, $KBUILD_OUTPUT, else srctree)",
    )
    locate.add_argument(
        "--arch", metavar="ARCH", help="kernel architecture (default: detected from .config)"
    )
    locate.add_argument(
        "--vscode-dir",
        metavar="DIR",
        help=f"where to write VS Code settings (default: ${ENV_VSCODE_DIR}, else <srctree>/.vscode)",
    )

    output = parser.add_argument_group("output control")
    output.add_argument(
        "--dry-run",
        action="store_true",
        help="show a unified diff of the intended changes and exit",
    )
    output.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the files are out of date, without writing (for CI)",
    )
    output.add_argument(
        "--no-backup",
        action="store_true",
        help="do not leave a .kdev.bak copy of the previous contents",
    )
    output.add_argument(
        "--json", action="store_true", help="print the resolved context as JSON and exit"
    )
    return parser
