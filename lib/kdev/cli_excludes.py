"""update_arch_excludes: keep editor noise down to the architecture in use.

Three different VS Code settings are involved, and the previous implementation
only wrote the first of them:

  search.exclude        what full-text search returns
  C_Cpp.files.exclude   what IntelliSense indexes, and therefore where
                        "go to definition" is allowed to land
  files.watcherExclude  what the file watcher follows -- the setting that
                        actually matters once an in-tree build has scattered
                        tens of thousands of .o and .cmd files around

Excluding other architectures from search alone leaves F12 jumping into
arch/mips, because search.exclude has no effect on the language service.
"""

import json
import sys

from . import context, jsonio, state

# Build output from an in-tree `make`.  These dominate both the watcher and
# the search index once the tree has been built in place.
BUILD_ARTIFACT_GLOBS = [
    "**/*.o",
    "**/*.o.*",
    "**/*.cmd",
    "**/*.ko",
    "**/*.mod",
    "**/*.mod.c",
    "**/*.a",
    "**/*.s",
    "**/.tmp_*",
    "**/Module.symvers",
    "**/modules.order",
]


def _arch_patterns(ctx, arches):
    """`arch/<name>/**` for every architecture, false for the selected one."""
    return {f"arch/{name}/**": name != ctx.arch for name in arches}


def main(argv=None):
    parser = context.common_parser(
        "Hide architectures other than the one being built from VS Code."
    )
    parser.add_argument(
        "--arch-only",
        action="store_true",
        help="only manage architecture excludes, leaving build artefacts and "
        "the IntelliSense index untouched",
    )
    # Legacy positional: `update_arch_excludes arm64`.
    parser.add_argument(
        "arch_positional",
        nargs="?",
        metavar="ARCH",
        help="architecture to keep visible (default: detected from .config)",
    )
    args = parser.parse_args(argv)

    if args.arch_positional and not args.arch:
        args.arch = args.arch_positional

    ctx = context.resolve(args)

    if args.json:
        print(json.dumps(ctx.as_dict(), indent=4))
        return 0

    settings_path = ctx.vscode_dir / "settings.json"

    raw = settings_path.read_text() if settings_path.is_file() else ""
    if raw and jsonio.has_comments(raw):
        print(
            f"warning: {settings_path} contains comments; they will be lost "
            f"when the file is rewritten (a copy is kept as "
            f"{settings_path.name}{jsonio.BACKUP_SUFFIX}).",
            file=sys.stderr,
        )

    settings = jsonio.read_json(settings_path, default={})

    # Architectures come from the source tree.  A build directory only holds
    # the one architecture that was built, so enumerating there would leave
    # every other architecture unexcluded.
    arches = ctx.available_arches()
    arch_patterns = _arch_patterns(ctx, arches)

    now = {"search.exclude": dict(arch_patterns)}
    if not args.arch_only:
        now["search.exclude"].update({glob: True for glob in BUILD_ARTIFACT_GLOBS})
        now["C_Cpp.files.exclude"] = dict(arch_patterns)
        now["files.watcherExclude"] = {glob: True for glob in BUILD_ARTIFACT_GLOBS}

    managed = state.load(ctx.vscode_dir)
    previous = managed.get("settings", {})

    for key, values in now.items():
        settings[key] = state.merge_dict(settings.get(key), previous.get(key), values)

    # Keys we managed before but no longer do (e.g. after --arch-only) must be
    # cleaned up, otherwise stale excludes linger forever.
    for key, keys_before in previous.items():
        if key in now:
            continue
        remaining = state.merge_dict(settings.get(key), keys_before, {})
        if remaining:
            settings[key] = remaining
        else:
            settings.pop(key, None)

    changed = jsonio.write_json(
        settings_path,
        settings,
        dry_run=args.dry_run,
        check=args.check,
        backup=not args.no_backup,
    )

    if not args.check:
        managed["settings"] = {key: sorted(values) for key, values in now.items()}
        state.save(ctx.vscode_dir, managed, dry_run=args.dry_run)

    if args.check:
        print(f"{settings_path}: {'out of date' if changed else 'up to date'}")
        return 1 if changed else 0

    if args.dry_run:
        if not changed:
            print(f"{settings_path} is already up to date.")
        return 0

    ctx.describe(sys.stdout)
    hidden = sum(1 for value in arch_patterns.values() if value)
    print(f"  hidden   {hidden} of {len(arches)} architectures")
    if not args.arch_only:
        print(
            f"  excluded {len(BUILD_ARTIFACT_GLOBS)} build-artefact globs from "
            f"search and the file watcher"
        )
    print(
        f"Updated {settings_path}."
        if changed
        else f"{settings_path} was already up to date."
    )
    return 0
