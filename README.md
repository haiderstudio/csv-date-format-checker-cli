# csv-date-format-checker-cli

Check date columns in CSV files match one given format — fail CI when one does not.

[![CI](https://github.com/haiderstudio/csv-date-format-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/csv-date-format-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`csv_date_format_checker` reads each CSV file,
takes the column named with `--column`, and checks
every value in it parses in the one format given
with `--format` (default `%Y-%m-%d`). Each value
that does not parse is reported with the file, the
line and the column, and the tool exits 1, so it
can fail a CI run. A file whose dates all match
exits 0.

- A date in the wrong format (`03/04/2026` —
  March 4 or April 3?) either breaks the import
  or, worse, imports as the wrong day with no
  error. This names the exact line, and the fix
  is re-formatting one value.
- The check is strict about shape as well as
  meaning: a value must round-trip through the
  format, so `2026-1-5` fails `%Y-%m-%d` even
  though it parses — the format asks for two
  digits, and the value has one. A date that
  cannot exist, such as `2026-02-30`, fails too.
- A header row is required: the first row names
  the columns, and `--column` picks one by name.
  Empty values are skipped — an empty cell is a
  missing value, not a wrongly formatted date.
- A file given directly on the command line is
  always checked, whatever its name. A folder is
  walked for files ending in `.csv` only,
  recursively by default (`--no-recursive` stops
  at the top level). `.git` folders are never
  walked, and directory links are never followed.
- `--json` prints the result as JSON, and
  `--stdin` checks one CSV document read from
  standard input.

## Who it is for

Anyone shipping CSV data files — exports, imports,
test fixtures, data drops. One date in the wrong
format and the import either fails outright or
silently lands on the wrong day, found weeks later
when the numbers do not add up. This is the gate
that keeps the dates in shape at the pull request.

## What it does NOT do

- It does not check delimiters — that is repo #95,
  csv-delimiter-checker-cli. Delimiters are a
  different check on the same files.
- It does not check for a byte-order mark — that is
  repo #105, csv-bom-checker-cli. A BOM is a
  different check on the same files.
- It does not check for empty cells — that is
  repo #73, csv-empty-checker-cli. Empty values
  are skipped here on purpose.
- It does not check that a date is in the past or
  the future, or in a sensible range. It only
  checks the format.
- It does not reformat a value for you. It only
  reports the values that do not match.
- It never rewrites a file, and it never touches
  the network.

## How this differs

- A fresh search of GitHub on Nov 16, 2026 found 0
  results for `"csv-date-format-checker-cli"` and 2
  results for `csv date format checker` —
  flying0dancing/data_checker, 0 stars, a
  single-commit script from 2019 tied to one
  internal workflow, which needs a proprietary
  config file, hard-codes project folders and
  three fixed formats, and has no tests, no CI
  and no folder walk; and ManojKumarPatnaik/
  Major-project-list, 262 stars, a list of
  practice projects, not a checker of any kind.
- No rival is a tested stdlib CLI gate for CSV
  date formats, in any format, for any column.

## Install

```sh
git clone https://github.com/haiderstudio/csv-date-format-checker-cli.git
cd csv-date-format-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one CSV file (the date column is `date`):

```sh
python3 src/csv_date_format_checker.py --column date data.csv
```

A file whose dates all match passes:

```sh
$ python3 src/csv_date_format_checker.py --column date examples/clean.csv
OK — 1 file(s) checked, every date matches %Y-%m-%d.
```

A file with dates in the wrong format fails, with
the file, line and column for each one:

```sh
$ python3 src/csv_date_format_checker.py --column date examples/flagged.csv
FAIL examples/flagged.csv: line 3 column "date": value "03/04/2026" does not match format %Y-%m-%d
FAIL examples/flagged.csv: line 4 column "date": value "2026-02-30" does not match format %Y-%m-%d
FAIL examples/flagged.csv: line 5 column "date": value "2026-1-5" does not match format %Y-%m-%d
Checked 1 file(s), 3 value(s) do not match format %Y-%m-%d in 1 file(s).
```

Check a whole folder (`.csv` files only):

```sh
$ python3 src/csv_date_format_checker.py --column date examples/
FAIL examples/euro.csv: line 2 column "date": value "05/01/2026" does not match format %Y-%m-%d
FAIL examples/euro.csv: line 3 column "date": value "28/02/2026" does not match format %Y-%m-%d
FAIL examples/flagged.csv: line 3 column "date": value "03/04/2026" does not match format %Y-%m-%d
FAIL examples/flagged.csv: line 4 column "date": value "2026-02-30" does not match format %Y-%m-%d
FAIL examples/flagged.csv: line 5 column "date": value "2026-1-5" does not match format %Y-%m-%d
Checked 4 file(s), 5 value(s) do not match format %Y-%m-%d in 2 file(s).
```

(The euro file uses day-first dates, so it fails the
default format on purpose — see the examples below.)

Check one document from standard input:

```sh
$ printf 'name,date\nAda,2026-01-05\n' | python3 src/csv_date_format_checker.py --column date --stdin
OK — 1 file(s) checked, every date matches %Y-%m-%d.
```

Machine-readable output:

```sh
$ python3 src/csv_date_format_checker.py --column date --json examples/flagged.csv
{
  "files": [
    {
      "path": "examples/flagged.csv",
      "findings": [
        {
          "line": 3,
          "reason": "column \"date\": value \"03/04/2026\" does not match format %Y-%m-%d"
        },
        {
          "line": 4,
          "reason": "column \"date\": value \"2026-02-30\" does not match format %Y-%m-%d"
        },
        {
          "line": 5,
          "reason": "column \"date\": value \"2026-1-5\" does not match format %Y-%m-%d"
        }
      ],
      "error": null
    }
  ],
  "checked": 1,
  "findings": 3
}
```

Exit codes: 0 when every date matches, 1 when
any value does not match or a file cannot be read
or checked, 2 for a usage error (a missing path,
a missing `--column`, a bad flag, or no CSV files
found).

## Examples

A different format, day-first dates — pass
`--format` and the same gate checks them:

```sh
$ python3 src/csv_date_format_checker.py --column date --format %d/%m/%Y examples/euro.csv
OK — 1 file(s) checked, every date matches %d/%m/%Y.
```

An empty cell and a quoted field holding a comma
are both handled — `examples/edge.csv` has both,
and it passes:

```sh
$ python3 src/csv_date_format_checker.py --column date examples/edge.csv
OK — 1 file(s) checked, every date matches %Y-%m-%d.
```

Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 tests/test_csv_date_format_checker.py
```

The tests run the real CLI on throwaway files and
folders, check the bundled examples against their
saved output, and check every command quoted in
this README by running it.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool is original work, written for this
repository. It builds on the Python standard
library only (`csv` and `datetime`). The idea
was researched against GitHub on Nov 16, 2026 —
no existing tool does this exact job, as noted
above under "How this differs".
