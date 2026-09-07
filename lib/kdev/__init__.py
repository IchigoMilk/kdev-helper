"""Shared helpers for the kdev-helper scripts.

The public surface is intentionally small:

    context  -- resolve srctree/objtree/ARCH into a KdevContext
    kconfig  -- parse .config and synthesise autoconf.h
    jsonio   -- read JSONC, write JSON atomically with backup/diff support
"""

__all__ = ["context", "jsonio", "kconfig"]
