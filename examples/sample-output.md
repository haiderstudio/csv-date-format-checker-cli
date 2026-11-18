== examples/clean.csv ==
OK — 1 file(s) checked, every date matches %Y-%m-%d.

== examples/flagged.csv ==
FAIL examples/flagged.csv: line 3 column "date": value "03/04/2026" does not match format %Y-%m-%d
FAIL examples/flagged.csv: line 4 column "date": value "2026-02-30" does not match format %Y-%m-%d
FAIL examples/flagged.csv: line 5 column "date": value "2026-1-5" does not match format %Y-%m-%d
Checked 1 file(s), 3 value(s) do not match format %Y-%m-%d in 1 file(s).

== examples/edge.csv ==
OK — 1 file(s) checked, every date matches %Y-%m-%d.

== examples/euro.csv --format %d/%m/%Y ==
OK — 1 file(s) checked, every date matches %d/%m/%Y.

== examples/ : the whole folder ==
FAIL examples/euro.csv: line 2 column "date": value "05/01/2026" does not match format %Y-%m-%d
FAIL examples/euro.csv: line 3 column "date": value "28/02/2026" does not match format %Y-%m-%d
FAIL examples/flagged.csv: line 3 column "date": value "03/04/2026" does not match format %Y-%m-%d
FAIL examples/flagged.csv: line 4 column "date": value "2026-02-30" does not match format %Y-%m-%d
FAIL examples/flagged.csv: line 5 column "date": value "2026-1-5" does not match format %Y-%m-%d
Checked 4 file(s), 5 value(s) do not match format %Y-%m-%d in 2 file(s).
