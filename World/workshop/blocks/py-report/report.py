"""Printable reports: builds a clean HTML page and opens it, ready to print or save as PDF.

    r = Report("Harvest - March")
    r.text("Total maize: 340 kg")
    r.table(rows, ["crop", "kg", "date"])
    r.open()          # browser opens it; Ctrl+P prints (or "Save as PDF")
"""
import html
import os
import tempfile
import time
import webbrowser

CSS = """body{font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#111}
h1{font-size:22px;border-bottom:2px solid #333;padding-bottom:6px}h2{font-size:17px;margin-top:22px}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:13px}th,td{border:1px solid #bbb;padding:4px 7px;text-align:left}
th{background:#eee}td.n{text-align:right}.meta{color:#555;font-size:12px}@media print{body{margin:0}}"""


class Report:
    def __init__(self, title):
        self.title = title
        self.parts = []

    def heading(self, text):
        self.parts.append("<h2>%s</h2>" % html.escape(str(text)))
        return self

    def text(self, text):
        self.parts.append("<p>%s</p>" % html.escape(str(text)).replace("\n", "<br>"))
        return self

    def table(self, rows, fields=None, labels=None, totals=None):
        fields = fields or list(dict.fromkeys(k for r in rows for k in r))
        labels = labels or {}
        h = ["<table><tr>%s</tr>" % "".join("<th>%s</th>" % html.escape(labels.get(f, f)) for f in fields)]
        for r in rows:
            h.append("<tr>%s</tr>" % "".join(('<td class="n">%s</td>' if isinstance(r.get(f), (int, float)) else "<td>%s</td>") % html.escape(str(r.get(f, ""))) for f in fields))
        if totals:
            h.append("<tr>%s</tr>" % "".join("<th>%s</th>" % (html.escape(str(round(sum(r.get(f) or 0 for r in rows), 2))) if f in totals else "") for f in fields))
        h.append("</table>")
        self.parts.append("".join(h))
        return self

    def html(self):
        return ('<!DOCTYPE html><html><head><meta charset="utf-8"><title>%s</title><style>%s</style></head><body><h1>%s</h1>'
                '<p class="meta">Made %s</p>%s</body></html>') % (html.escape(self.title), CSS, html.escape(self.title), time.strftime("%d %b %Y, %H:%M"), "\n".join(self.parts))

    def save(self, path=None):
        path = path or os.path.join(tempfile.gettempdir(), "report-%d.html" % int(time.time()))
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.html())
        return path

    def open(self, path=None):
        p = self.save(path)
        webbrowser.open("file://" + os.path.abspath(p))
        return p
