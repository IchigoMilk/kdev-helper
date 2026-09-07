# VS Code Helper Scripts for Linux Kernel Development

These helpers address two common pain points when reading the Linux kernel in VS Code: IntelliSense gaps caused by `#ifdef`-heavy code, and navigation results populated by unrelated architectures. They assume you already have VS Code's C/C++ IntelliSense support (typically the Microsoft C/C++ extension) available.

Requirements: bash and python3. No third-party packages.

## Setup

1. Clone (or copy) this repository somewhere convenient, e.g. `~/opt/kdev-helper`.
2. Source the helper setup script. Pass your kernel tree as the (optional) last argument to set `KDEV_HELPER_KERNEL_ROOT` automatically:

```sh
source /path/to/kdev-helper/setup_kdev_env.sh /path/to/linux
```

If you want to specify a different location for the helper scripts:
```sh
source /path/to/kdev-helper/setup_kdev_env.sh /path/to/kdev-helper /path/to/linux
```

If your kernel was built out of tree — `make O=...`, Yocto, Buildroot, a vendor BSP — also point the helpers at the build directory, which is where `.config` lives:

```sh
source /path/to/kdev-helper/setup_kdev_env.sh --objtree /path/to/build /path/to/linux
```

Add the command above to your shell profile (`~/.bashrc`) to keep the commands available in new terminals.

Both commands also work without any setup at all if you run them from inside a kernel tree: they search upward from the current directory for the source tree.

## Usage

- `update_defines` points IntelliSense at the configuration your kernel was actually built with, so `#ifdef` blocks resolve the same way they do during the build:

```sh
update_defines
```

- `update_arch_excludes` keeps architectures other than the one you are building out of search results, out of the IntelliSense index, and out of the file watcher:

```sh
update_arch_excludes
```

The architecture is detected from your `.config`, so you normally do not need to name it. Pass one explicitly to override:

```sh
update_arch_excludes arm64
```

Note that the kernel's architecture names are not the ones `uname -m` prints: `aarch64` is `arm64` and `x86_64` is `x86`. The helper will tell you if you get it wrong.

### Where things are read from and written to

| | Source | Notes |
|---|---|---|
| Architecture list | `<srctree>/arch/` | The build directory only holds the architecture you built |
| `.config`, `autoconf.h` | `<objtree>/` | Same as the source tree for an in-tree build |
| `.vscode/` | `<srctree>/.vscode` | Override with `--vscode-dir`; build directories get wiped |

Resolution order, most specific first:

| | Options |
|---|---|
| Source tree | `--srctree`, `$KDEV_HELPER_KERNEL_ROOT`, search upward from `$PWD` |
| Build tree | `--objtree`, `$KDEV_HELPER_OBJTREE`, `$O`, `$KBUILD_OUTPUT`, the source tree |
| Architecture | `--arch`, `$ARCH`, `autoconf.h`, `.config`, the one architecture present in the build tree |
| `.vscode` | `--vscode-dir`, `$KDEV_HELPER_VSCODE_DIR`, `<srctree>/.vscode` |

Run `update_defines --json` at any time to see exactly what was resolved.

### Options

Both commands accept:

| Option | Effect |
|---|---|
| `--dry-run` | Print a unified diff of the intended changes and exit |
| `--check` | Exit 1 if the files are out of date, without writing them (for CI) |
| `--json` | Print the resolved paths, architecture and kernel version, then exit |
| `--no-backup` | Skip the `.kdev.bak` copy of the previous contents |

`update_defines` additionally accepts `--configuration NAME` to update a single entry in `c_cpp_properties.json` when you keep several, and `--keep-workspace-glob` to retain recursive `${workspaceFolder}/**` include entries.

`update_arch_excludes` accepts `--arch-only` to manage architecture excludes and nothing else.

### Re-running

`update_arch_excludes` needs re-running when you change the target architecture.

`update_defines` does not need re-running when you change `.config`. It force-includes the kernel's own `include/generated/autoconf.h` rather than copying values out of `.config`, so rebuilding the kernel is enough for IntelliSense to follow. If that header does not exist yet (you have not run `make prepare`), an equivalent one is generated from `.config` into `~/.cache/kdev-helper/` — never into your kernel tree — and re-running is needed until the tree is prepared.

### Editing your VS Code files

The helpers own only the entries they add. `.vscode/.kdev-state.json` records exactly what was written so the next run can replace it without touching anything you added by hand.

Both commands read JSONC, so comments and trailing commas in `settings.json` will not break them. Comments are lost when the file is rewritten, so the previous contents are kept alongside as `settings.json.kdev.bak` and a warning is printed. Writes are atomic: the target is replaced by a rename rather than truncated in place.

`c_cpp_properties.json` is created if it does not exist; there is no need to run `C/C++: Edit Configurations (JSON)` from the command palette first.

## Tests

```sh
python3 -m unittest discover -s tests -t tests
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
