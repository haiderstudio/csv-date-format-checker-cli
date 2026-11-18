"""Tests for csv_date_format_checker.

Run from the repo root:

    python3 tests/test_csv_date_format_checker.py
"""

import ast
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src" / "csv_date_format_checker.py"

sys.path.insert(0, str(REPO / "src"))
import csv_date_format_checker as tool  # noqa: E402


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=encoding)
    return str(path)


def run_cli(args, input=None, cwd=None):
    result = subprocess.run(
        [sys.executable, str(SRC)] + args,
        cwd=cwd or str(REPO), capture_output=True, text=True,
        input=input)
    return result.returncode, result.stdout, result.stderr


class TestValueMatchesFormat(unittest.TestCase):
    def test_matching_date_passes(self):
        self.assertTrue(tool.value_matches_format("2026-01-05", "%Y-%m-%d"))

    def test_other_separator_fails(self):
        self.assertFalse(
            tool.value_matches_format("03/04/2026", "%Y-%m-%d"))

    def test_impossible_date_fails(self):
        self.assertFalse(
            tool.value_matches_format("2026-02-30", "%Y-%m-%d"))

    def test_missing_zero_padding_fails(self):
        self.assertFalse(
            tool.value_matches_format("2026-1-5", "%Y-%m-%d"))

    def test_euro_format_passes(self):
        self.assertTrue(
            tool.value_matches_format("05/01/2026", "%d/%m/%Y"))

    def test_euro_day_month_order_matters(self):
        self.assertFalse(
            tool.value_matches_format("31/04/2026", "%d/%m/%Y"))

    def test_plain_word_is_not_a_date(self):
        self.assertFalse(tool.value_matches_format("soon", "%Y-%m-%d"))

    def test_leap_day_valid_in_leap_year(self):
        self.assertTrue(
            tool.value_matches_format("2024-02-29", "%Y-%m-%d"))
        self.assertFalse(
            tool.value_matches_format("2026-02-29", "%Y-%m-%d"))


class TestCheckText(unittest.TestCase):
    def test_clean_text_passes(self):
        bad, error = tool.check_text(
            "name,date\nAda,2026-01-05\n", "date", "%Y-%m-%d")
        self.assertEqual((bad, error), ([], None))

    def test_bad_value_reports_line_and_column(self):
        bad, error = tool.check_text(
            "name,date\nAda,2026-01-05\nBo,03/04/2026\n",
            "date", "%Y-%m-%d")
        self.assertIsNone(error)
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 3)
        self.assertIn('03/04/2026', bad[0]["reason"])
        self.assertIn('"date"', bad[0]["reason"])

    def test_second_date_column_by_name(self):
        bad, error = tool.check_text(
            "date,shipped\n2026-01-05,2026-13-01\n",
            "shipped", "%Y-%m-%d")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 2)

    def test_empty_value_skipped(self):
        bad, error = tool.check_text(
            "name,date\nAda,\nBo,2026-01-05\n", "date", "%Y-%m-%d")
        self.assertEqual((bad, error), ([], None))

    def test_missing_column_is_an_error(self):
        bad, error = tool.check_text(
            "name,amount\nAda,10\n", "date", "%Y-%m-%d")
        self.assertEqual(bad, [])
        self.assertIn('"date"', error)
        self.assertIn("not in header row", error)

    def test_empty_file_is_an_error(self):
        bad, error = tool.check_text("", "date", "%Y-%m-%d")
        self.assertEqual(bad, [])
        self.assertIn("no header row", error)

    def test_header_only_passes(self):
        bad, error = tool.check_text("name,date\n", "date", "%Y-%m-%d")
        self.assertEqual((bad, error), ([], None))

    def test_quoted_comma_does_not_shift_columns(self):
        bad, error = tool.check_text(
            'name,date,note\nAda,2026-01-05,"paid, in full"\n',
            "date", "%Y-%m-%d")
        self.assertEqual((bad, error), ([], None))

    def test_short_row_is_skipped_not_a_crash(self):
        bad, error = tool.check_text(
            "name,date,amount\nAda\n", "date", "%Y-%m-%d")
        self.assertEqual((bad, error), ([], None))

    def test_custom_format_checked(self):
        bad, error = tool.check_text(
            "name,date\nAda,05/01/2026\n", "date", "%d/%m/%Y")
        self.assertEqual((bad, error), ([], None))
        bad, error = tool.check_text(
            "name,date\nAda,2026-01-05\n", "date", "%d/%m/%Y")
        self.assertEqual(len(bad), 1)


class TestCli(unittest.TestCase):
    def test_clean_file_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", "name,date\nAda,2026-01-05\n")
            code, out, err = run_cli(
                ["--column", "date", path])
            self.assertEqual(code, 0)
            self.assertIn("every date matches %Y-%m-%d", out)

    def test_flagged_file_exits_one_with_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv",
                         "name,date\nAda,2026-01-05\nBo,03/04/2026\n")
            code, out, err = run_cli(
                ["--column", "date", path])
            self.assertEqual(code, 1)
            self.assertIn("line 3", out)
            self.assertIn("03/04/2026", out)
            self.assertIn("Checked 1 file(s), 1 value(s)", out)

    def test_folder_walks_csv_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.csv", "name,date\nAda,2026-01-05\n")
            write(tmp, "b.csv", "name,date\nBo,03/04/2026\n")
            write(tmp, "notes.txt", "name,date\nBo,03/04/2026\n")
            code, out, err = run_cli(["--column", "date", tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 2 file(s), 1 value(s)", out)

    def test_no_recursive_stops_at_top_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.csv", "name,date\nAda,2026-01-05\n")
            write(tmp, "sub/b.csv", "name,date\nBo,03/04/2026\n")
            code, out, err = run_cli(
                ["--column", "date", "--no-recursive", tmp])
            self.assertEqual(code, 0)
            code, out, err = run_cli(["--column", "date", tmp])
            self.assertEqual(code, 1)

    def test_exclude_skips_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.csv", "name,date\nAda,2026-01-05\n")
            write(tmp, "b.csv", "name,date\nBo,03/04/2026\n")
            code, out, err = run_cli(
                ["--column", "date", "--exclude", "b.csv", tmp])
            self.assertEqual(code, 0)

    def test_git_folder_never_walked(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.csv", "name,date\nAda,2026-01-05\n")
            write(tmp, ".git/b.csv", "name,date\nBo,03/04/2026\n")
            code, out, err = run_cli(["--column", "date", tmp])
            self.assertEqual(code, 0)

    def test_file_given_directly_checked_whatever_its_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "data.txt",
                         "name,date\nBo,03/04/2026\n")
            code, out, err = run_cli(["--column", "date", path])
            self.assertEqual(code, 1)

    def test_missing_path_is_usage_error(self):
        code, out, err = run_cli(
            ["--column", "date", "no-such-file.csv"])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_missing_column_flag_is_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", "name,date\nAda,2026-01-05\n")
            code, out, err = run_cli([path])
            self.assertEqual(code, 2)

    def test_missing_column_in_file_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", "name,amount\nAda,10\n")
            code, out, err = run_cli(["--column", "date", path])
            self.assertEqual(code, 1)
            self.assertIn("not in header row", out)

    def test_invalid_utf8_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.csv"
            path.write_bytes(b"name,date\nAda,\xff\xfe\n")
            code, out, err = run_cli(["--column", "date", str(path)])
            self.assertEqual(code, 1)
            self.assertIn("not valid UTF-8", out)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv",
                         "name,date\nBo,03/04/2026\n")
            code, out, err = run_cli(
                ["--column", "date", "--json", path])
            self.assertEqual(code, 1)
            self.assertIn('"line": 2', out)
            self.assertIn("03/04/2026", out)

    def test_stdin_clean(self):
        code, out, err = run_cli(
            ["--column", "date", "--stdin"],
            input="name,date\nAda,2026-01-05\n")
        self.assertEqual(code, 0)
        self.assertIn("every date matches", out)

    def test_stdin_flagged(self):
        code, out, err = run_cli(
            ["--column", "date", "--stdin"],
            input="name,date\nBo,03/04/2026\n")
        self.assertEqual(code, 1)
        self.assertIn("FAIL <stdin>: line 2", out)

    def test_delimiter_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv",
                         "name;date\nAda;2026-01-05\n")
            code, out, err = run_cli(
                ["--column", "date", "--delimiter", ";", path])
            self.assertEqual(code, 0)

    def test_input_files_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv",
                         "name,date\nBo,03/04/2026\n")
            before = Path(path).read_text()
            run_cli(["--column", "date", path])
            self.assertEqual(Path(path).read_text(), before)

    def test_cli_runs_from_another_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.csv", "name,date\nAda,2026-01-05\n")
            result = subprocess.run(
                [sys.executable, str(SRC), "--column", "date", "a.csv"],
                cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertIn("every date matches", result.stdout)

    def test_cli_runs_under_fake_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", "name,date\nAda,2026-01-05\n")
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                code, out, err = run_cli(["--column", "date", path])
            finally:
                if old_home is None:
                    del os.environ["HOME"]
                else:
                    os.environ["HOME"] = old_home
            self.assertEqual(code, 0)


class TestExamples(unittest.TestCase):
    def test_run_example_output_matches_sample(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        expected = (REPO / "examples/sample-output.md").read_text()
        self.assertEqual(result.stdout, expected)

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        clean = subprocess.run(
            [sys.executable, "src/csv_date_format_checker.py",
             "--column", "date", "examples/clean.csv"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(clean.returncode, 0)
        self.assertIn(clean.stdout.strip(), readme)
        flagged = subprocess.run(
            [sys.executable, "src/csv_date_format_checker.py",
             "--column", "date", "examples/flagged.csv"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(flagged.returncode, 1)
        self.assertIn(flagged.stdout.strip(), readme)
        folder = subprocess.run(
            [sys.executable, "src/csv_date_format_checker.py",
             "--column", "date", "examples/"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(folder.returncode, 1)
        self.assertIn("Checked 4 file(s), 5 value(s) do not match "
                      "format %Y-%m-%d in 2 file(s).", folder.stdout)
        self.assertIn("Checked 4 file(s), 5 value(s) do not match "
                      "format %Y-%m-%d in 2 file(s).", readme)
        edge = subprocess.run(
            [sys.executable, "src/csv_date_format_checker.py",
             "--column", "date", "examples/edge.csv"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(edge.returncode, 0)
        self.assertIn(edge.stdout.strip(), readme)
        euro = subprocess.run(
            [sys.executable, "src/csv_date_format_checker.py",
             "--column", "date", "--format", "%d/%m/%Y",
             "examples/euro.csv"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(euro.returncode, 0)
        self.assertIn(euro.stdout.strip(), readme)
        js = subprocess.run(
            [sys.executable, "src/csv_date_format_checker.py",
             "--column", "date", "--json", "examples/flagged.csv"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(js.returncode, 1)
        self.assertIn(js.stdout.strip(), readme)


class TestHygiene(unittest.TestCase):
    def _repo_files(self, skip_tests=True, skip_examples=True):
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__")
                       and not (skip_tests and d == "tests")
                       and not (skip_examples and d == "examples")]
            for name in files:
                if name.endswith(".pyc"):
                    continue
                yield Path(root) / name

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "FIXME", "XXX"]
        hits = []
        for path in self._repo_files(skip_tests=True,
                                     skip_examples=False):
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append("%s: %s" % (path.name, word))
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files(skip_tests=True,
                                     skip_examples=False):
            text = path.read_text(errors="ignore")
            for marker in ("/home/", "/Users/", "C:\\"):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_no_real_secrets_outside_tests_and_examples(self):
        # The source holds no key values at all; the tests
        # and examples hold fake values only, so they are
        # excluded from this scan.
        patterns = [
            re.compile(r"AKIA[0-9A-Z]{16}"),
            re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
            re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
            re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
            re.compile(r"AIza[0-9A-Za-z_-]{35}"),
            re.compile(r"[rs]k_(?:live|test)_[A-Za-z0-9]{16,}"),
            re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
            re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ"),
        ]
        hits = []
        for path in self._repo_files():
            text = path.read_text(errors="ignore")
            for pattern in patterns:
                if pattern.search(text):
                    hits.append("%s: %s" % (path.name, pattern.pattern))
        self.assertEqual(hits, [])

    def test_stdlib_imports_only(self):
        stdlib = set(sys.stdlib_module_names)
        for target in (REPO / "src/csv_date_format_checker.py",
                       REPO / "tests/test_csv_date_format_checker.py"):
            tree = ast.parse(target.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0]
                                    for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertFalse(
                imported - stdlib - {"csv_date_format_checker"},
                (target.name, imported))
            self.assertNotIn("yaml", imported)

    def test_no_network_use_in_src(self):
        src = (REPO / "src/csv_date_format_checker.py").read_text()
        for marker in ("urllib.request", "requests", "socket",
                       "http.client", "urlopen", "urlretrieve"):
            self.assertNotIn(marker, src, marker)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (REPO / ".github/workflows/ci.yml").read_text()
        self.assertIn("tests/test_csv_date_format_checker.py", ci)
        self.assertIn("ubuntu-latest", ci)
        self.assertIn("3.12", ci)
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)

    def test_readme_names_the_neighbouring_repos(self):
        readme = (REPO / "README.md").read_text()
        self.assertIn("csv-empty-checker-cli", readme)
        self.assertIn("csv-delimiter-checker-cli", readme)
        self.assertIn("csv-bom-checker-cli", readme)


if __name__ == "__main__":
    unittest.main()
