# Security Policy

This tool runs locally, collects no data, sends nothing anywhere, and needs no API key or secret. It only reads the CSV files you point it at, and it never rewrites a file and never changes anything. It writes nothing except the report on standard output (and usage errors on standard error). It never fetches a URL.

It only checks that date values match one given format. It never reformats a value, never deletes a row, and never runs code found in a CSV file.

If you find a case where the tool rewrites a file, opens a URL, or reports a pass for a CSV file with a date in the wrong format, please open an issue describing the exact commands and input. Do not include any real secret in the report.
