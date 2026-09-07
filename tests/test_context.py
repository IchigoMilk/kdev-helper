"""Tree resolution, with the split source/build layout as the headline case."""

import os
import pathlib
import unittest

import support
from support import TreeTestCase

from kdev import context


class Args:
    """Stand-in for the parsed argparse namespace."""

    def __init__(self, **kwargs):
        self.srctree = None
        self.objtree = None
        self.arch = None
        self.vscode_dir = None
        self.__dict__.update(kwargs)


class SplitTree(TreeTestCase):
    """A Yocto/BSP style layout: source and build output in separate trees."""

    def test_resolves_both_trees(self):
        ctx = context.resolve(Args(srctree=str(self.src), objtree=str(self.obj)))
        self.assertEqual(ctx.srctree, self.src)
        self.assertEqual(ctx.objtree, self.obj)
        self.assertFalse(ctx.in_tree)

    def test_config_comes_from_the_build_tree(self):
        ctx = context.resolve(Args(srctree=str(self.src), objtree=str(self.obj)))
        self.assertEqual(ctx.config, self.obj / ".config")
        self.assertTrue(ctx.config.is_file())

    def test_architectures_are_enumerated_from_the_source_tree(self):
        # The build tree only holds arm64; enumerating there would leave mips
        # and x86 unexcluded.
        ctx = context.resolve(Args(srctree=str(self.src), objtree=str(self.obj)))
        self.assertEqual(ctx.available_arches(), support.ARCHES)

    def test_vscode_dir_defaults_to_the_source_tree(self):
        # Build directories get wiped and regenerated; editor config should
        # not live there.
        ctx = context.resolve(Args(srctree=str(self.src), objtree=str(self.obj)))
        self.assertEqual(ctx.vscode_dir, self.src / ".vscode")

    def test_source_tree_alone_is_a_clear_error(self):
        os.environ["KDEV_HELPER_KERNEL_ROOT"] = str(self.src)
        with self.assertRaises(SystemExit) as caught:
            context.resolve(Args())
        message = str(caught.exception)
        self.assertIn("no kernel .config found", message)
        self.assertIn("KDEV_HELPER_OBJTREE", message)

    def test_objtree_env_var(self):
        os.environ["KDEV_HELPER_KERNEL_ROOT"] = str(self.src)
        os.environ["KDEV_HELPER_OBJTREE"] = str(self.obj)
        ctx = context.resolve(Args())
        self.assertEqual(ctx.objtree, self.obj)

    def test_kbuild_output_env_var(self):
        os.environ["KDEV_HELPER_KERNEL_ROOT"] = str(self.src)
        os.environ["KBUILD_OUTPUT"] = str(self.obj)
        self.assertEqual(context.resolve(Args()).objtree, self.obj)


class InTree(TreeTestCase):
    split = False

    def test_objtree_falls_back_to_srctree(self):
        ctx = context.resolve(Args(srctree=str(self.src)))
        self.assertEqual(ctx.objtree, self.src)
        self.assertTrue(ctx.in_tree)


class SrctreeDiscovery(TreeTestCase):
    def test_searches_upward_from_cwd(self):
        # The old implementation searched relative to the script's install
        # directory, which never finds the kernel tree.
        nested = self.src / "drivers" / "tty" / "serial"
        nested.mkdir(parents=True)
        saved = pathlib.Path.cwd()
        try:
            os.chdir(nested)
            ctx = context.resolve(Args(objtree=str(self.obj)))
            self.assertEqual(ctx.srctree, self.src)
        finally:
            os.chdir(saved)

    def test_unrelated_directory_gives_actionable_error(self):
        saved = pathlib.Path.cwd()
        try:
            os.chdir(self.cache)
            with self.assertRaises(SystemExit) as caught:
                context.resolve(Args(objtree=str(self.obj)))
            self.assertIn("KDEV_HELPER_KERNEL_ROOT", str(caught.exception))
        finally:
            os.chdir(saved)

    def test_pointing_kernel_root_at_a_build_dir_explains_itself(self):
        os.environ["KDEV_HELPER_KERNEL_ROOT"] = str(self.obj)
        with self.assertRaises(SystemExit) as caught:
            context.resolve(Args())
        self.assertIn("--objtree", str(caught.exception))


class ArchResolution(TreeTestCase):
    def test_detected_from_config_symbols(self):
        ctx = context.resolve(Args(srctree=str(self.src), objtree=str(self.obj)))
        self.assertEqual(ctx.arch, "arm64")

    def test_autoconf_banner_wins_over_symbols(self):
        support.make_objtree(
            self.obj,
            autoconf="/*\n * Linux/x86 6.8.12 Kernel Configuration\n */\n",
        )
        ctx = context.resolve(Args(srctree=str(self.src), objtree=str(self.obj)))
        self.assertEqual(ctx.arch, "x86")
        self.assertEqual(ctx.kernel_version, "6.8.12")

    def test_explicit_arch_wins(self):
        ctx = context.resolve(
            Args(srctree=str(self.src), objtree=str(self.obj), arch="mips")
        )
        self.assertEqual(ctx.arch, "mips")

    def test_uname_style_name_is_rejected_with_a_hint(self):
        with self.assertRaises(SystemExit) as caught:
            context.resolve(
                Args(srctree=str(self.src), objtree=str(self.obj), arch="aarch64")
            )
        message = str(caught.exception)
        self.assertIn("aarch64 -> arm64", message)
        self.assertIn("arm64, mips, x86", message)


if __name__ == "__main__":
    unittest.main()
