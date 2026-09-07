"""update_defines: point IntelliSense at the kernel's own configuration.

The earlier implementation copied every CONFIG_* assignment out of .config
into the `defines` array.  That is both wrong and needlessly repetitive: it
collapses =m onto =y (see kconfig.py), mangles quoted string values, grows the
file to a couple of thousand entries, and has to be re-run by hand after every
configuration change.

The kernel already generates the authoritative header,
include/generated/autoconf.h, so this now force-includes that file instead of
copying it.  Rebuilding the kernel updates IntelliSense with no further action.
"""

import json
import sys

from . import context, jsonio, kconfig, state

# Mirrors the kernel's own LINUXINCLUDE, minus the flags IntelliSense does not
# need.  Scoping these to the selected architecture is what stops <asm/...>
# resolving into some other arch's headers.
def _include_path(ctx):
    src, obj, arch = ctx.srctree, ctx.objtree, ctx.arch
    return [
        str(src / "arch" / arch / "include"),
        str(obj / "arch" / arch / "include" / "generated"),
        str(src / "include"),
        str(obj / "include"),
        str(src / "arch" / arch / "include" / "uapi"),
        str(obj / "arch" / arch / "include" / "generated" / "uapi"),
        str(src / "include" / "uapi"),
        str(obj / "include" / "generated" / "uapi"),
    ]


def _recursive_globs(entries):
    """Entries that re-index the whole tree and so defeat arch scoping."""
    return [item for item in entries if item.rstrip("/").endswith("/**")]


def _resolve_autoconf(ctx, dry_run):
    """Return the autoconf.h to force-include, synthesising one if needed."""
    if ctx.autoconf is not None:
        return ctx.autoconf, False

    if not ctx.config.is_file():
        raise context.ResolveError(
            f"neither {ctx.objtree}/include/generated/autoconf.h nor "
            f"{ctx.config} exists.\n"
            f"hint: run `make olddefconfig prepare` in the build directory."
        )

    symbols = kconfig.parse_config(ctx.config)
    generated = kconfig.generate_autoconf(symbols, ctx.arch, ctx.kernel_version)
    target = kconfig.cached_autoconf_path(ctx.objtree)

    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(generated)

    return target, True


# The C/C++ extension only knows these four Linux targets; anything else falls
# back to x64, which is no worse than the previous unconditional guess.
_INTELLISENSE_MODES = {
    "x86": "linux-gcc-x64",
    "arm64": "linux-gcc-arm64",
    "arm": "linux-gcc-arm",
}


def _new_configuration(ctx):
    return {
        "name": f"Linux-{ctx.arch}",
        "includePath": [],
        "defines": [],
        "forcedInclude": [],
        "cStandard": "gnu11",
        "intelliSenseMode": _INTELLISENSE_MODES.get(ctx.arch, "linux-gcc-x64"),
    }


def _select_configurations(props, requested):
    configurations = props.get("configurations")
    if not isinstance(configurations, list) or not configurations:
        return None, "empty"

    if requested is not None:
        matched = [c for c in configurations if c.get("name") == requested]
        if not matched:
            names = ", ".join(str(c.get("name")) for c in configurations)
            raise context.ResolveError(
                f"no configuration named {requested!r} in c_cpp_properties.json.\n"
                f"hint: available configurations: {names}"
            )
        return matched, "selected"

    return configurations, "all"


def main(argv=None):
    parser = context.common_parser(
        "Point VS Code IntelliSense at the kernel configuration for this build."
    )
    parser.add_argument(
        "--configuration",
        metavar="NAME",
        help="only update the named configuration in c_cpp_properties.json "
        "(default: every configuration)",
    )
    parser.add_argument(
        "--keep-workspace-glob",
        action="store_true",
        help="keep recursive ${workspaceFolder}/** include entries, which "
        "otherwise defeat per-architecture include scoping",
    )
    # Positional forms kept so existing muscle memory and scripts keep working.
    parser.add_argument("config_path", nargs="?", help=".config path (legacy positional)")
    parser.add_argument(
        "properties_path", nargs="?", help="c_cpp_properties.json path (legacy positional)"
    )
    args = parser.parse_args(argv)

    if args.config_path and not args.objtree:
        # A .config path implies its build directory.
        import pathlib

        config = pathlib.Path(args.config_path).expanduser().resolve()
        if not config.is_file():
            raise context.ResolveError(f"missing kernel config at {config}")
        args.objtree = str(config.parent)

    ctx = context.resolve(args)

    if args.json:
        print(json.dumps(ctx.as_dict(), indent=4))
        return 0

    if args.properties_path:
        import pathlib

        props_path = pathlib.Path(args.properties_path).expanduser().resolve()
        vscode_dir = props_path.parent
    else:
        vscode_dir = ctx.vscode_dir
        props_path = vscode_dir / "c_cpp_properties.json"

    autoconf, synthesised = _resolve_autoconf(ctx, args.dry_run)

    raw = props_path.read_text() if props_path.is_file() else ""
    if raw and jsonio.has_comments(raw):
        print(
            f"warning: {props_path} contains comments; they will be lost when "
            f"the file is rewritten (a copy is kept as "
            f"{props_path.name}{jsonio.BACKUP_SUFFIX}).",
            file=sys.stderr,
        )

    props = jsonio.read_json(props_path, default={})
    configurations, mode = _select_configurations(props, args.configuration)

    created = False
    if mode == "empty":
        configurations = [_new_configuration(ctx)]
        props["configurations"] = configurations
        props.setdefault("version", 4)
        created = True
    elif mode == "all" and len(configurations) > 1:
        print(
            f"note: applying the {ctx.arch} context to all "
            f"{len(configurations)} configurations; use --configuration NAME "
            f"to target just one.",
            file=sys.stderr,
        )

    managed = state.load(vscode_dir)
    previous = managed.get("c_cpp_properties", {})
    now = {}

    include_path = _include_path(ctx)
    forced = [str(autoconf), str(ctx.srctree / "include" / "linux" / "kconfig.h")]
    defines = ["__KERNEL__"]

    dropped_globs = []
    for entry in configurations:
        name = str(entry.get("name", ""))
        prev = previous.get(name, {})

        existing_includes = entry.get("includePath", [])
        if not args.keep_workspace_glob:
            globs = _recursive_globs(existing_includes)
            # Anything indexed recursively pulls in every architecture again.
            if globs:
                dropped_globs.extend(globs)
                existing_includes = [
                    item for item in existing_includes if item not in globs
                ]

        entry["includePath"] = state.merge_list(
            existing_includes, prev.get("includePath"), include_path
        )
        entry["forcedInclude"] = state.merge_list(
            entry.get("forcedInclude", []), prev.get("forcedInclude"), forced
        )
        # CONFIG_* defines are no longer emitted; drop any left by older runs
        # so IntelliSense stops seeing the incorrect =m expansions.
        existing_defines = [
            item
            for item in entry.get("defines", [])
            if not str(item).startswith("CONFIG_")
        ]
        entry["defines"] = state.merge_list(
            existing_defines, prev.get("defines"), defines
        )

        now[name] = {
            "includePath": include_path,
            "forcedInclude": forced,
            "defines": defines,
        }

    changed = jsonio.write_json(
        props_path,
        props,
        dry_run=args.dry_run,
        check=args.check,
        backup=not args.no_backup,
    )

    if not args.check:
        managed["c_cpp_properties"] = now
        state.save(vscode_dir, managed, dry_run=args.dry_run)

    _report(
        ctx,
        props_path,
        autoconf,
        synthesised,
        created,
        dropped_globs,
        changed,
        args,
    )

    if args.check and changed:
        return 1
    return 0


def _report(ctx, props_path, autoconf, synthesised, created, dropped, changed, args):
    if args.check:
        status = "out of date" if changed else "up to date"
        print(f"{props_path}: {status}")
        return

    if args.dry_run:
        if not changed:
            print(f"{props_path} is already up to date.")
        return

    ctx.describe(sys.stdout)
    if created:
        print(f"  created  {props_path}")
    print(f"  defines  via forcedInclude {autoconf}")
    if synthesised:
        print(
            "           (synthesised from .config; run `make prepare` in "
            f"{ctx.objtree} for the kernel's own header)"
        )
    if dropped:
        print(
            "  removed  recursive include entries that defeat arch scoping: "
            + ", ".join(sorted(set(dropped)))
        )
        print("           (pass --keep-workspace-glob to keep them)")
    print(
        f"Updated {props_path}."
        if changed
        else f"{props_path} was already up to date."
    )
