#!/usr/bin/env python3
"""Check date columns in CSV files match one given format.

Run: python3 src/csv_date_format_checker.py --column date data.csv
     python3 src/csv_date_format_checker.py --column date --format %d/%m/%Y data/
     python3 src/csv_date_format_checker.py --column date --stdin < data.csv

A date in the wrong format (03/04/2026 — March 4 or
April 3?) either breaks the import or, worse, imports
as the wrong day with no error. This tool reads each
CSV file, takes the column named on the command line,
and checks every value in it parses in the one format
given with --format (default %Y-%m-%d). Each value
that does not parse is reported with the file, the
line and the column, and the tool exits 1, so it can
fail a CI run. A file whose dates all match exits 0.

The check is strict about shape as well as meaning:
a value must round-trip through the format, so
2026-1-5 fails %Y-%m-%d even though it parses — the
format asks for two digits, and the value has one.
A date that cannot exist, such as 2026-02-30, fails
too.

A header row is required: the first row names the
columns, and --column picks one by name. Empty values
are skipped — an empty cell is a missing value, not
a wrongly formatted date (that is the job of
csv-empty-checker-cli, repo #73). A file given
directly on the command line is always checked,
whatever its name. A folder is walked for files
ending in .csv only, recursively by default
(--no-recursive stops at the top level). .git
folders are never walked, and directory links are
never followed.

It never rewrites a file, never touches the network,
and reads only the files and folders you point it at.
"""

import argparse
import csv
import fnmatch
import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path

__version__ = "1.0.0"

CSV_SUFFIXES = (".csv",)
DEFAULT_FORMAT = "%Y-%m-%d"


def value_matches_format(value, fmt):
    """True when value parses in fmt and round-trips exactly."""
    try:
        parsed = datetime.strptime(value, fmt)
    except ValueError:
        return False
    return parsed.strftime(fmt) == value


def check_text(text, column, fmt, delimiter=","):
    """Check one document's text.

    Returns (findings, error): findings is a list of
    {"line": int, "reason": str} in document order, and
    error is None or a string saying why the file could
    not be checked at all.
    """
    findings = []
    try:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        numbered = [(row, reader.line_num) for row in reader]
    except csv.Error as exc:
        return [], "not valid CSV: %s" % exc
    if not numbered:
        return [], "empty file, no header row"
    header, _header_line = numbered[0]
    if column not in header:
        return [], ("column \"%s\" not in header row "
                    "(headers: %s)" % (column, ", ".join(header)))
    index = header.index(column)
    for row, line_no in numbered[1:]:
        value = row[index] if index < len(row) else ""
        if value == "":
            continue
        if not value_matches_format(value, fmt):
            findings.append({
                "line": line_no,
                "reason": ("column \"%s\": value \"%s\" does not match "
                           "format %s" % (column, value, fmt)),
            })
    return findings, None


def check_file(path, column, fmt, delimiter=","):
    """Check one file. Returns (findings, error)."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return [], "not valid UTF-8"
    except OSError as exc:
        return [], str(exc)
    return check_text(text, column, fmt, delimiter)


def _is_csv_file(path):
    return Path(path).name.lower().endswith(CSV_SUFFIXES)


def collect_files(paths, recursive=True, exclude=None):
    """Expand CLI paths into a sorted list of CSV files.

    A file given directly is always checked, whatever its
    name. A folder is walked for files ending in .csv
    only. .git folders are never walked, and directory
    links are never followed.
    """
    exclude = exclude or []
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            found.append(str(path))
        elif path.is_dir():
            for dirpath, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [
                    d for d in dirs
                    if d != ".git"
                    and not any(fnmatch.fnmatch(d, pat) for pat in exclude)
                ]
                for name in files:
                    candidate = Path(dirpath) / name
                    if not _is_csv_file(candidate):
                        continue
                    if any(
                        fnmatch.fnmatch(str(candidate), pat)
                        or fnmatch.fnmatch(name, pat)
                        for pat in exclude
                    ):
                        continue
                    found.append(str(candidate))
                if not recursive:
                    break
        else:
            raise FileNotFoundError("no such file or folder: %s" % raw)
    seen = set()
    unique = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return sorted(unique)


def format_finding(path, finding):
    """One human-readable line for one bad date value."""
    return ("FAIL %s: line %d %s"
            % (path, finding["line"], finding["reason"]))


def run(paths, column, fmt, delimiter=",", recursive=True,
        exclude=None, as_json=False):
    """Check paths, print the report, return the exit code."""
    try:
        files = collect_files(paths, recursive=recursive, exclude=exclude)
    except FileNotFoundError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if not files:
        print("error: no CSV files found", file=sys.stderr)
        return 2
    results = []
    findings = 0
    files_with_findings = 0
    for path in files:
        bad, error = check_file(path, column, fmt, delimiter)
        count = len(bad) + (1 if error else 0)
        if count:
            findings += count
            files_with_findings += 1
        results.append({"path": path, "findings": bad, "error": error})
    if as_json:
        print(json.dumps(
            {"files": results, "checked": len(files),
             "findings": findings},
            indent=2))
    else:
        for result in results:
            if result["error"]:
                print("FAIL %s: %s" % (result["path"], result["error"]))
            for finding in result["findings"]:
                print(format_finding(result["path"], finding))
        if findings:
            print("Checked %d file(s), %d value(s) do not match "
                  "format %s in %d file(s)."
                  % (len(files), findings, fmt, files_with_findings))
        else:
            print("OK — %d file(s) checked, every date matches %s."
                  % (len(files), fmt))
    return 1 if findings else 0


def run_stdin(column, fmt, delimiter=",", as_json=False):
    """Check one CSV document read from standard input."""
    text = sys.stdin.read()
    bad, error = check_text(text, column, fmt, delimiter)
    findings = len(bad) + (1 if error else 0)
    if as_json:
        print(json.dumps(
            {"files": [{"path": "<stdin>", "findings": bad,
                        "error": error}],
             "checked": 1, "findings": findings},
            indent=2))
    else:
        if error:
            print("FAIL <stdin>: %s" % error)
        for finding in bad:
            print(format_finding("<stdin>", finding))
        if findings:
            print("Checked 1 file(s), %d value(s) do not match "
                  "format %s in 1 file(s)." % (findings, fmt))
        else:
            print("OK — 1 file(s) checked, every date matches %s."
                  % fmt)
    return 1 if findings else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="csv_date_format_checker",
        description="Check date columns in CSV files match one "
                    "given format, fail CI when one does not.")
    parser.add_argument("paths", nargs="*",
                        help="CSV files or folders to walk")
    parser.add_argument("--column", required=True,
                        help="name of the date column in the header row")
    parser.add_argument("--format", default=DEFAULT_FORMAT,
                        help="date format to check against "
                             "(default: %(default)s)")
    parser.add_argument("--delimiter", default=",",
                        help="CSV field delimiter (default: ',')")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        help="skip files or folders matching this pattern "
                             "(repeatable)")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one CSV document from standard input")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)
    if args.stdin:
        if args.paths:
            parser.error("--stdin takes no file or folder arguments")
        return run_stdin(args.column, args.format, args.delimiter,
                         as_json=args.json)
    if not args.paths:
        parser.error("give at least one CSV file or folder")
    return run(args.paths, args.column, args.format, args.delimiter,
               recursive=not args.no_recursive,
               exclude=args.exclude, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
