"""Minimal kernel trees for exercising the helpers without a real checkout."""

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))

ARCHES = ["arm64", "mips", "x86"]

SAMPLE_CONFIG = """\
#
# Automatically generated file; DO NOT EDIT.
#
CONFIG_ARM64=y
CONFIG_SERIAL_8250=y
CONFIG_CPU_FREQ_GOV_POWERSAVE=m
CONFIG_NET_IP_TUNNEL=m
CONFIG_CC_VERSION_TEXT="aarch64-oe-linux-gcc (GCC) 13.4.0"
CONFIG_LOCALVERSION=""
CONFIG_INET_TABLE_PERTURB_ORDER=16
CONFIG_PAGE_SHIFT=0x1000
# CONFIG_ATH9K is not set
"""


def make_srctree(root):
    """A directory that looks enough like a kernel source tree to be found."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "Makefile").write_text("# fake kernel Makefile\n")
    (root / "Kconfig").write_text("# fake Kconfig\n")
    for arch in ARCHES:
        (root / "arch" / arch / "include").mkdir(parents=True, exist_ok=True)
    (root / "include" / "linux").mkdir(parents=True, exist_ok=True)
    (root / "include" / "linux" / "kconfig.h").write_text("/* fake */\n")
    return root


def make_objtree(root, config=SAMPLE_CONFIG, arches=("arm64",), autoconf=None):
    """A build directory: .config plus only the architecture that was built."""
    root.mkdir(parents=True, exist_ok=True)
    (root / ".config").write_text(config)
    for arch in arches:
        (root / "arch" / arch / "include" / "generated").mkdir(
            parents=True, exist_ok=True
        )
    if autoconf is not None:
        generated = root / "include" / "generated"
        generated.mkdir(parents=True, exist_ok=True)
        (generated / "autoconf.h").write_text(autoconf)
    return root


class TreeTestCase(unittest.TestCase):
    """Provides self.src and self.obj, plus a scratch XDG cache."""

    split = True

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self._tmp.name)

        self.src = make_srctree(base / "kernel-source")
        if self.split:
            self.obj = make_objtree(base / "kernel-build-artifacts")
        else:
            self.obj = make_objtree(self.src)

        self.cache = base / "cache"
        self.cache.mkdir()

        import os

        self._saved_env = {}
        for key in (
            "KDEV_HELPER_KERNEL_ROOT",
            "KDEV_HELPER_OBJTREE",
            "KDEV_HELPER_VSCODE_DIR",
            "ARCH",
            "O",
            "KBUILD_OUTPUT",
            "XDG_CACHE_HOME",
        ):
            self._saved_env[key] = os.environ.pop(key, None)
        os.environ["XDG_CACHE_HOME"] = str(self.cache)

    def tearDown(self):
        import os

        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def run_defines(self, *argv):
        from kdev import cli_defines

        return cli_defines.main(self._with_tree(argv))

    def run_excludes(self, *argv):
        from kdev import cli_excludes

        return cli_excludes.main(self._with_tree(argv))

    def _with_tree(self, argv):
        argv = list(argv)
        if not any(a == "--srctree" for a in argv):
            argv += ["--srctree", str(self.src)]
        if not any(a == "--objtree" for a in argv):
            argv += ["--objtree", str(self.obj)]
        return argv

    def properties(self):
        from kdev import jsonio

        return jsonio.read_json(self.src / ".vscode" / "c_cpp_properties.json")

    def settings(self):
        from kdev import jsonio

        return jsonio.read_json(self.src / ".vscode" / "settings.json")
