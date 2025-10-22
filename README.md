# VS Code Helper Scripts for Linux Kernel Development

These helpers address two common pain points when reading the Linux kernel in VS Code: IntelliSense gaps caused by `#ifdef`-heavy code and search results populated by unrelated architectures. They assume you already have VS Code’s C/C++ IntelliSense support (typically the Microsoft C/C++ extension) available.

## What’s Included

- `update_defines.sh` keeps `.vscode/c_cpp_properties.json` in sync with the active kernel `.config`, so IntelliSense sees the same configuration symbols as the build.
- `update_arch_excludes.sh` rewrites `.vscode/settings.json` search excludes so only the architecture you care about stays visible.

## Getting Started

1. Copy the entire `vscode/` directory to the root of your kernel source tree (next to the top-level `Makefile`).
2. Make the scripts executable:
   ```sh
   chmod +x vscode/*.sh
   ```

## Usage

1. After regenerating `.config` via `make menuconfig`, `make defconfig`, etc., run:
   ```sh
   ./vscode/update_defines.sh
   ```
2. When you change the target architecture (or set `ARCH` for cross builds), run:
   ```sh
   ./vscode/update_arch_excludes.sh <arch>
   ```
   You can skip the argument if `ARCH` is already exported.

Re-run the scripts each time you update `.config` or switch architectures to keep VS Code aligned with the build environment.
