"""JSONC tolerance and non-destructive writing."""

import io
import json
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout

import support  # noqa: F401  (sets up sys.path)

from kdev import jsonio

COMMENTED = """\
{
    // VS Code writes files like this, and users add comments too.
    "search.exclude": {
        "arch/mips/**": true,  /* other arches */
    },
    "editor.rulers": [80],
}
"""


class StripJsonc(unittest.TestCase):
    def test_parses_comments_and_trailing_commas(self):
        data = json.loads(jsonio.strip_jsonc(COMMENTED))
        self.assertEqual(data["search.exclude"], {"arch/mips/**": True})
        self.assertEqual(data["editor.rulers"], [80])

    def test_leaves_comment_markers_inside_strings(self):
        text = '{"url": "https://example.com/x", "glob": "a/**/*.c"}'
        self.assertEqual(json.loads(jsonio.strip_jsonc(text))["url"],
                         "https://example.com/x")
        self.assertEqual(json.loads(jsonio.strip_jsonc(text))["glob"], "a/**/*.c")

    def test_handles_escaped_quotes(self):
        text = r'{"a": "say \"hi\" // not a comment"}'
        self.assertEqual(
            json.loads(jsonio.strip_jsonc(text))["a"], 'say "hi" // not a comment'
        )

    def test_detects_comments(self):
        self.assertTrue(jsonio.has_comments(COMMENTED))
        self.assertFalse(jsonio.has_comments('{"a": 1}'))
        self.assertFalse(jsonio.has_comments('{"a": "// not a comment"}'))


class WriteJson(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self._tmp.name) / "settings.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_reads_commented_file_without_dying(self):
        self.path.write_text(COMMENTED)
        data = jsonio.read_json(self.path)
        self.assertIn("search.exclude", data)

    def test_missing_file_returns_default(self):
        self.assertEqual(jsonio.read_json(self.path), {})

    def test_invalid_json_reports_the_path(self):
        self.path.write_text("{ this is not json")
        with self.assertRaises(SystemExit) as caught:
            jsonio.read_json(self.path)
        self.assertIn(str(self.path), str(caught.exception))

    def test_writes_and_reports_change(self):
        self.assertTrue(jsonio.write_json(self.path, {"a": 1}))
        self.assertEqual(json.loads(self.path.read_text()), {"a": 1})

    def test_second_identical_write_is_a_no_op(self):
        jsonio.write_json(self.path, {"a": 1})
        self.assertFalse(jsonio.write_json(self.path, {"a": 1}))

    def test_backup_keeps_previous_contents(self):
        self.path.write_text(COMMENTED)
        jsonio.write_json(self.path, {"a": 1})
        backup = self.path.with_name(self.path.name + jsonio.BACKUP_SUFFIX)
        self.assertEqual(backup.read_text(), COMMENTED)

    def test_dry_run_leaves_the_file_alone(self):
        self.path.write_text('{"a": 1}\n')
        captured = io.StringIO()
        with redirect_stdout(captured):
            self.assertTrue(jsonio.write_json(self.path, {"a": 2}, dry_run=True))
        self.assertEqual(json.loads(self.path.read_text()), {"a": 1})
        self.assertIn('-{"a": 1}', captured.getvalue())

    def test_check_leaves_the_file_alone(self):
        self.path.write_text('{"a": 1}\n')
        self.assertTrue(jsonio.write_json(self.path, {"a": 2}, check=True))
        self.assertEqual(json.loads(self.path.read_text()), {"a": 1})

    def test_no_temp_files_are_left_behind(self):
        jsonio.write_json(self.path, {"a": 1})
        leftovers = [p.name for p in self.path.parent.iterdir()
                     if p.name.startswith(".settings.json.")]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
