"""End-to-end behaviour of the two commands."""

import io
import json
import unittest
from contextlib import redirect_stdout, redirect_stderr

import support
from support import TreeTestCase

from kdev import jsonio, state


def quiet(fn, *args, **kwargs):
    """Run `fn`, swallowing its report, and return (result, stdout+stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        result = fn(*args, **kwargs)
    return result, out.getvalue() + err.getvalue()


class Defines(TreeTestCase):
    def test_creates_properties_file_when_absent(self):
        # The old version refused to run until the user generated the file
        # from the VS Code command palette.
        quiet(self.run_defines)
        props = self.properties()
        self.assertEqual(props["configurations"][0]["name"], "Linux-arm64")

    def test_forced_include_replaces_config_defines(self):
        quiet(self.run_defines)
        entry = self.properties()["configurations"][0]
        forced = entry["forcedInclude"]
        self.assertTrue(any(f.endswith("autoconf.h") for f in forced))
        self.assertTrue(any(f.endswith("kconfig.h") for f in forced))
        self.assertEqual(
            [d for d in entry["defines"] if d.startswith("CONFIG_")], []
        )

    def test_prefers_the_kernels_own_autoconf_header(self):
        support.make_objtree(
            self.obj,
            autoconf="/*\n * Linux/arm64 6.12.57 Kernel Configuration\n */\n",
        )
        quiet(self.run_defines)
        forced = self.properties()["configurations"][0]["forcedInclude"]
        self.assertIn(
            str(self.obj / "include" / "generated" / "autoconf.h"), forced
        )

    def test_synthesises_autoconf_outside_the_kernel_tree(self):
        quiet(self.run_defines)
        forced = self.properties()["configurations"][0]["forcedInclude"]
        autoconf = next(f for f in forced if f.endswith(".h") and "autoconf" in f)
        # Never written into the source or build tree.
        self.assertTrue(autoconf.startswith(str(self.cache)))
        body = open(autoconf).read()
        self.assertIn("#define CONFIG_NET_IP_TUNNEL_MODULE 1", body)
        self.assertNotIn("#define CONFIG_NET_IP_TUNNEL 1", body)

    def test_include_path_is_scoped_to_the_selected_arch(self):
        quiet(self.run_defines)
        includes = self.properties()["configurations"][0]["includePath"]
        self.assertIn(str(self.src / "arch" / "arm64" / "include"), includes)
        self.assertFalse([i for i in includes if "/arch/mips/" in i])
        # Generated headers come from the build tree, not the source tree.
        self.assertIn(
            str(self.obj / "arch" / "arm64" / "include" / "generated"), includes
        )

    def test_drops_recursive_glob_that_defeats_arch_scoping(self):
        vscode = self.src / ".vscode"
        vscode.mkdir()
        (vscode / "c_cpp_properties.json").write_text(
            json.dumps(
                {
                    "configurations": [
                        {"name": "Linux", "includePath": ["${workspaceFolder}/**"]}
                    ]
                }
            )
        )
        _, output = quiet(self.run_defines)
        includes = self.properties()["configurations"][0]["includePath"]
        self.assertNotIn("${workspaceFolder}/**", includes)
        self.assertIn("--keep-workspace-glob", output)

    def test_keep_workspace_glob_opt_out(self):
        vscode = self.src / ".vscode"
        vscode.mkdir()
        (vscode / "c_cpp_properties.json").write_text(
            json.dumps(
                {
                    "configurations": [
                        {"name": "Linux", "includePath": ["${workspaceFolder}/**"]}
                    ]
                }
            )
        )
        quiet(self.run_defines, "--keep-workspace-glob")
        self.assertIn(
            "${workspaceFolder}/**",
            self.properties()["configurations"][0]["includePath"],
        )

    def test_preserves_user_defines_and_include_paths(self):
        vscode = self.src / ".vscode"
        vscode.mkdir()
        (vscode / "c_cpp_properties.json").write_text(
            json.dumps(
                {
                    "configurations": [
                        {
                            "name": "Linux",
                            "defines": ["MY_OWN_FLAG=1"],
                            "includePath": ["/opt/vendor/include"],
                            "compilerPath": "/usr/bin/aarch64-linux-gnu-gcc",
                        }
                    ]
                }
            )
        )
        quiet(self.run_defines)
        entry = self.properties()["configurations"][0]
        self.assertIn("MY_OWN_FLAG=1", entry["defines"])
        self.assertIn("/opt/vendor/include", entry["includePath"])
        self.assertEqual(entry["compilerPath"], "/usr/bin/aarch64-linux-gnu-gcc")

    def test_rerun_does_not_duplicate_entries(self):
        quiet(self.run_defines)
        first = self.properties()
        quiet(self.run_defines)
        self.assertEqual(self.properties(), first)

    def test_switching_arch_removes_the_previous_include_paths(self):
        quiet(self.run_defines)
        quiet(self.run_defines, "--arch", "mips")
        includes = self.properties()["configurations"][0]["includePath"]
        self.assertFalse([i for i in includes if "/arch/arm64/" in i])
        self.assertIn(str(self.src / "arch" / "mips" / "include"), includes)

    def test_configuration_flag_targets_one_entry(self):
        vscode = self.src / ".vscode"
        vscode.mkdir()
        (vscode / "c_cpp_properties.json").write_text(
            json.dumps(
                {
                    "configurations": [
                        {"name": "Linux-arm64"},
                        {"name": "Linux-x86"},
                    ]
                }
            )
        )
        quiet(self.run_defines, "--configuration", "Linux-arm64")
        configs = self.properties()["configurations"]
        self.assertTrue(configs[0].get("forcedInclude"))
        self.assertNotIn("forcedInclude", configs[1])

    def test_unknown_configuration_lists_the_available_ones(self):
        vscode = self.src / ".vscode"
        vscode.mkdir()
        (vscode / "c_cpp_properties.json").write_text(
            json.dumps({"configurations": [{"name": "Linux-arm64"}]})
        )
        with self.assertRaises(SystemExit) as caught:
            quiet(self.run_defines, "--configuration", "nope")
        self.assertIn("Linux-arm64", str(caught.exception))

    def test_multiple_configurations_warn_by_default(self):
        vscode = self.src / ".vscode"
        vscode.mkdir()
        (vscode / "c_cpp_properties.json").write_text(
            json.dumps(
                {"configurations": [{"name": "Linux-arm64"}, {"name": "Linux-x86"}]}
            )
        )
        _, output = quiet(self.run_defines)
        self.assertIn("--configuration", output)

    def test_dry_run_writes_nothing(self):
        _, output = quiet(self.run_defines, "--dry-run")
        self.assertFalse((self.src / ".vscode" / "c_cpp_properties.json").exists())
        self.assertIn("forcedInclude", output)

    def test_check_reports_drift_with_exit_code(self):
        code, _ = quiet(self.run_defines, "--check")
        self.assertEqual(code, 1)
        quiet(self.run_defines)
        code, _ = quiet(self.run_defines, "--check")
        self.assertEqual(code, 0)

    def test_json_dumps_the_resolved_context(self):
        _, output = quiet(self.run_defines, "--json")
        data = json.loads(output)
        self.assertEqual(data["arch"], "arm64")
        self.assertEqual(data["objtree"], str(self.obj))
        self.assertFalse(data["in_tree"])


class Excludes(TreeTestCase):
    def test_hides_every_other_architecture(self):
        quiet(self.run_excludes)
        excludes = self.settings()["search.exclude"]
        self.assertIs(excludes["arch/arm64/**"], False)
        self.assertIs(excludes["arch/mips/**"], True)
        self.assertIs(excludes["arch/x86/**"], True)

    def test_split_tree_still_sees_all_architectures(self):
        # Regression: enumerating arch/ in the build tree found only arm64.
        quiet(self.run_excludes)
        arch_keys = [k for k in self.settings()["search.exclude"] if k.startswith("arch/")]
        self.assertEqual(len(arch_keys), len(support.ARCHES))

    def test_scopes_the_intellisense_index_too(self):
        # search.exclude alone does not stop "go to definition" landing in
        # another architecture.
        quiet(self.run_excludes)
        self.assertIs(self.settings()["C_Cpp.files.exclude"]["arch/mips/**"], True)

    def test_excludes_build_artefacts_from_the_watcher(self):
        quiet(self.run_excludes)
        watcher = self.settings()["files.watcherExclude"]
        self.assertIs(watcher["**/*.o"], True)
        self.assertIs(watcher["**/*.cmd"], True)

    def test_arch_only_keeps_the_narrow_behaviour(self):
        quiet(self.run_excludes, "--arch-only")
        settings = self.settings()
        self.assertNotIn("files.watcherExclude", settings)
        self.assertNotIn("C_Cpp.files.exclude", settings)

    def test_switching_to_arch_only_cleans_up_after_itself(self):
        quiet(self.run_excludes)
        quiet(self.run_excludes, "--arch-only")
        self.assertNotIn("files.watcherExclude", self.settings())

    def test_preserves_unrelated_settings_and_excludes(self):
        vscode = self.src / ".vscode"
        vscode.mkdir()
        (vscode / "settings.json").write_text(
            json.dumps(
                {
                    "editor.rulers": [80],
                    "search.exclude": {"**/node_modules": True},
                }
            )
        )
        quiet(self.run_excludes)
        settings = self.settings()
        self.assertEqual(settings["editor.rulers"], [80])
        self.assertIs(settings["search.exclude"]["**/node_modules"], True)

    def test_survives_a_commented_settings_file(self):
        # The old implementation exited with "Expecting value" here.
        vscode = self.src / ".vscode"
        vscode.mkdir()
        (vscode / "settings.json").write_text(
            '{\n    // my notes\n    "editor.rulers": [80],\n}\n'
        )
        _, output = quiet(self.run_excludes)
        self.assertIn("comments", output)
        self.assertEqual(self.settings()["editor.rulers"], [80])

    def test_backs_up_before_rewriting(self):
        vscode = self.src / ".vscode"
        vscode.mkdir()
        original = '{\n    // keep me\n    "editor.rulers": [80]\n}\n'
        (vscode / "settings.json").write_text(original)
        quiet(self.run_excludes)
        backup = vscode / ("settings.json" + jsonio.BACKUP_SUFFIX)
        self.assertEqual(backup.read_text(), original)

    def test_arch_defaults_to_the_detected_one(self):
        quiet(self.run_excludes)
        self.assertIs(self.settings()["search.exclude"]["arch/arm64/**"], False)

    def test_legacy_positional_arch_still_works(self):
        quiet(self.run_excludes, "mips")
        excludes = self.settings()["search.exclude"]
        self.assertIs(excludes["arch/mips/**"], False)
        self.assertIs(excludes["arch/arm64/**"], True)

    def test_rerun_is_idempotent(self):
        quiet(self.run_excludes)
        first = self.settings()
        quiet(self.run_excludes)
        self.assertEqual(self.settings(), first)


class SharedState(TreeTestCase):
    def test_both_commands_share_one_state_file(self):
        quiet(self.run_defines)
        quiet(self.run_excludes)
        managed = state.load(self.src / ".vscode")
        self.assertIn("c_cpp_properties", managed)
        self.assertIn("settings", managed)

    def test_dry_run_does_not_record_state(self):
        quiet(self.run_defines, "--dry-run")
        self.assertEqual(state.load(self.src / ".vscode"), {})


if __name__ == "__main__":
    unittest.main()
