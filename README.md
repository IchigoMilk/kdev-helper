# VS Code Helper Scripts for Linux Kernel Development

These helpers address two common pain points when reading the Linux kernel in VS Code: IntelliSense gaps caused by `#ifdef`-heavy code and search results populated by unrelated architectures. They assume you already have VS Code’s C/C++ IntelliSense support (typically the Microsoft C/C++ extension) available.

## Helpers

- `update_defines` keeps `.vscode/c_cpp_properties.json` in sync with the active kernel `.config`, so IntelliSense sees the same configuration symbols as the build.
- `update_arch_excludes` rewrites `.vscode/settings.json` search excludes so only the architecture you care about stays visible.

## Setup

1. Clone (or copy) this repository somewhere convenient, e.g. `~/opt/kdev-helper`.
2. Export the kernel tree you want these helpers to operate on:
  ```sh
  export KDEV_HELPER_KERNEL_ROOT=/path/to/linux
  ```
3. Source the provided alias definitions so the helpers (living in `bin/`) are available as regular commands:
  ```sh
  source /path/to/kdev-helper/setup_kdev_env.sh
  ```

Add the two lines above to your shell profile (`~/.bashrc`, `~/.zshrc`, …) to keep the aliases available in new terminals.

## Usage

- Refresh IntelliSense defines after updating `.config`:
  ```sh
  update_defines                # optional: update_defines </path/to/.config> </path/to/c_cpp_properties.json>
  ```
- Narrow VS Code search results to a single `ARCH` (argument wins, otherwise `ARCH` is read from the environment):
  ```sh
  update_arch_excludes x86      # omit the argument if ARCH is already exported
  ```

Both commands operate on the tree pointed to by `KDEV_HELPER_KERNEL_ROOT`. Re-run them whenever you regenerate `.config` or change the target architecture so VS Code stays aligned with your build configuration.
