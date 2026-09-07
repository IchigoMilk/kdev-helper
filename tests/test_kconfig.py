"""The =m regression is the reason this file exists first."""

import pathlib
import unittest

import support  # noqa: F401  (sets up sys.path)

from kdev import kconfig


class ParseConfig(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self._tmp.name) / ".config"
        self.path.write_text(support.SAMPLE_CONFIG)
        self.symbols = kconfig.parse_config(self.path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_reads_assignments(self):
        self.assertEqual(self.symbols["CONFIG_SERIAL_8250"], "y")
        self.assertEqual(self.symbols["CONFIG_CPU_FREQ_GOV_POWERSAVE"], "m")

    def test_ignores_not_set_comments(self):
        self.assertNotIn("CONFIG_ATH9K", self.symbols)

    def test_keeps_quoted_values_intact(self):
        self.assertEqual(
            self.symbols["CONFIG_CC_VERSION_TEXT"],
            '"aarch64-oe-linux-gcc (GCC) 13.4.0"',
        )


class GenerateAutoconf(unittest.TestCase):
    def setUp(self):
        symbols = {
            "CONFIG_ARM64": "y",
            "CONFIG_NET_IP_TUNNEL": "m",
            "CONFIG_CC_VERSION_TEXT": '"aarch64-oe-linux-gcc (GCC) 13.4.0"',
            "CONFIG_INET_TABLE_PERTURB_ORDER": "16",
            "CONFIG_PAGE_SHIFT": "0x1000",
        }
        self.text = kconfig.generate_autoconf(symbols, "arm64", "6.12.57")
        self.lines = set(self.text.splitlines())

    def test_builtin_becomes_plain_define(self):
        self.assertIn("#define CONFIG_ARM64 1", self.lines)

    def test_module_becomes_module_suffix(self):
        # The whole point: =m must not turn into CONFIG_NET_IP_TUNNEL 1, or
        # IS_MODULE() and #ifdef CONFIG_NET_IP_TUNNEL_MODULE read as disabled.
        self.assertIn("#define CONFIG_NET_IP_TUNNEL_MODULE 1", self.lines)
        self.assertNotIn("#define CONFIG_NET_IP_TUNNEL 1", self.lines)

    def test_string_value_keeps_c_quoting(self):
        self.assertIn(
            '#define CONFIG_CC_VERSION_TEXT "aarch64-oe-linux-gcc (GCC) 13.4.0"',
            self.lines,
        )

    def test_numeric_values_pass_through(self):
        self.assertIn("#define CONFIG_INET_TABLE_PERTURB_ORDER 16", self.lines)
        self.assertIn("#define CONFIG_PAGE_SHIFT 0x1000", self.lines)

    def test_banner_records_arch_and_version(self):
        self.assertIn(" * Linux/arm64 6.12.57 Kernel Configuration", self.lines)


class ArchDetection(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_reads_arch_and_version_from_autoconf_banner(self):
        path = self.dir / "autoconf.h"
        path.write_text(
            "/*\n"
            " * Automatically generated file; DO NOT EDIT.\n"
            " * Linux/arm64 6.12.57 Kernel Configuration\n"
            " */\n"
            "#define CONFIG_ARM64 1\n"
        )
        self.assertEqual(kconfig.arch_from_autoconf(path), ("arm64", "6.12.57"))

    def test_missing_banner_is_not_fatal(self):
        path = self.dir / "autoconf.h"
        path.write_text("#define CONFIG_ARM64 1\n")
        self.assertEqual(kconfig.arch_from_autoconf(path), (None, None))

    def test_infers_arch_from_symbols(self):
        self.assertEqual(kconfig.arch_from_symbols({"CONFIG_ARM64": "y"}), "arm64")
        self.assertEqual(kconfig.arch_from_symbols({"CONFIG_X86_64": "y"}), "x86")
        self.assertIsNone(kconfig.arch_from_symbols({"CONFIG_ARM64": "n"}))


if __name__ == "__main__":
    unittest.main()
