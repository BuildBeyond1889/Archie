"""Spreadsheet files in and out (CSV, which Excel, LibreOffice and Google Sheets all open).

    write_csv("harvest.csv", rows)            # rows = list of dicts
    rows = read_csv("harvest.csv")            # numbers come back as numbers
"""
import csv


def write_csv(path, rows, fields=None):
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:      # utf-8-sig so Excel shows accents and Swahili right
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


def _num(v):
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def read_csv(path, numbers=True):
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")       # handles ; and tab files too
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.DictReader(f, dialect=dialect))
    if numbers:
        rows = [{k: _num(v) if isinstance(v, str) and v.strip() else v for k, v in r.items()} for r in rows]
    return rows
