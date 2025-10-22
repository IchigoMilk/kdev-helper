# VS Code Helper Scripts for Linux Kernel Development

These helpers address two common pain points when reading the Linux kernel in VS Code: IntelliSense gaps caused by `#ifdef`-heavy code and search results populated by unrelated architectures. They assume you already have VS Code’s C/C++ IntelliSense support (typically the Microsoft C/C++ extension) available.

## Setup

1. Clone (or copy) this repository somewhere convenient, e.g. `~/opt/kdev-helper`.
2. Source the helper setup script. Pass your kernel tree as the (optional) second argument to set `KDEV_HELPER_KERNEL_ROOT` automatically:

```sh
source /path/to/kdev-helper/setup_kdev_env.sh /path/to/linux
```

If you want to specify a different location for the helper scripts:
```sh
source /path/to/kdev-helper/setup_kdev_env.sh /path/to/kdev-helper /path/to/linux
```

Add the command above to your shell profile (`~/.bashrc`, `~/.zshrc`, …) to keep the aliases available in new terminals.

## Usage

- `update_defines` keeps `.vscode/c_cpp_properties.json` in sync with the active kernel `.config`, so IntelliSense sees the same configuration symbols as the build:

```sh
update_defines
```

If you want to specify different paths for the `.config` and `c_cpp_properties.json` files:
```sh
update_defines </path/to/.config> </path/to/c_cpp_properties.json>
```

- `update_arch_excludes` rewrites `.vscode/settings.json` search excludes so only the architecture you care about stays visible:

```sh
update_arch_excludes arm64
```

Re-run them whenever you regenerate `.config` or change the target architecture so VS Code stays aligned with your build configuration.

Note that before running the helpers, you should open the VS Code command palette once and execute `C/C++: Edit Configurations (JSON)` so that `.vscode/c_cpp_properties.json` exists for `update_defines` to manage.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
