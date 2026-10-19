"""Stock and records. Built from Archie's blocks: window app, DB, forms, search, CSV, report and backup."""
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
# archie:imports
from lib.db import DB
from lib.forms import Form
from lib.search import search
from lib.csvio import write_csv
from lib.report import Report
from lib.backup import make_backup

HERE = os.path.dirname(os.path.abspath(__file__))
FIELDS = [
    {"name": "item", "label": "Item", "required": True, "maxlen": 80},
    {"name": "qty", "label": "Quantity", "type": "number", "min": 0, "required": True},
    {"name": "unit", "label": "Unit", "type": "choice", "choices": ["pieces", "kg", "litres", "boxes", "packets", "bags"], "required": True},
    {"name": "price", "label": "Price each", "type": "number", "min": 0},
    {"name": "place", "label": "Where it is kept"},
]
COLS = ("item", "qty", "unit", "price", "place")


class StockApp(tk.Tk):
    def __init__(self, db_path="stock.db"):
        super().__init__()
        self.title("Stock")
        self.geometry("860x560")
        self.db = DB(db_path)
        self.items = self.db.table("items", item="text", qty="real", unit="text", price="real", place="text")
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Add an item", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.form = Form(left, FIELDS).pack(fill="x", pady=6)
        ttk.Button(left, text="Add", command=self.add).pack(anchor="w")
        ttk.Separator(left).pack(fill="x", pady=10)
        for text, cmd in (("Export to Excel (CSV)", self.export), ("Print stock report", self.report), ("Back up to USB / folder", self.backup)):
            ttk.Button(left, text=text, command=cmd).pack(fill="x", pady=2)
        right = ttk.Frame(self, padding=10)
        right.pack(side="left", fill="both", expand=True)
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *a: self.refresh())
        ttk.Entry(right, textvariable=self.q).pack(fill="x")
        self.tree = ttk.Treeview(right, columns=COLS, show="headings")
        for c in COLS:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=90 if c != "item" else 200, anchor="e" if c in ("qty", "price") else "w")
        self.tree.pack(fill="both", expand=True, pady=6)
        self.tree.bind("<Delete>", self.delete)
        self.tree.bind("<Double-1>", self.change_qty)
        self.status = ttk.Label(right, text="")
        self.status.pack(anchor="w")
        self.refresh()

    def add(self):
        values, errors = self.form.values()
        if errors:
            return
        self.items.add(**values)
        self.form.clear()
        self.refresh()

    def rows(self):
        return search(self.items.all("item"), self.q.get(), ["item", "place", "unit"], limit=100000)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        rows = self.rows()
        for r in rows:
            self.tree.insert("", "end", iid=str(r["id"]), values=[("%g" % r[c]) if isinstance(r[c], float) else (r[c] if r[c] is not None else "") for c in COLS])
        value = sum((r["qty"] or 0) * (r["price"] or 0) for r in rows)
        self.status.config(text="%d items shown · stock value %s" % (len(rows), "{:,.2f}".format(value)))

    def change_qty(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        r = self.items.get(int(sel[0]))
        win = tk.Toplevel(self)
        win.title(r["item"])
        ttk.Label(win, text="Add (+10) or take away (-3):").pack(padx=12, pady=6)
        e = ttk.Entry(win)
        e.pack(padx=12)
        e.focus()

        def ok(_e=None):
            try:
                self.items.update(r["id"], qty=max(0, (r["qty"] or 0) + float(e.get().replace(",", "."))))
            except ValueError:
                return
            win.destroy()
            self.refresh()
        e.bind("<Return>", ok)
        ttk.Button(win, text="OK", command=ok).pack(pady=8)

    def delete(self, _e=None):
        sel = self.tree.selection()
        if sel and messagebox.askyesno("Delete", "Delete %d item(s)?" % len(sel)):
            for i in sel:
                self.items.delete(int(i))
            self.refresh()

    def export(self):
        p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="stock.csv")
        if p:
            write_csv(p, self.rows(), list(COLS))
            messagebox.showinfo("Export", "Saved %s" % p)

    def report(self):
        rows = self.rows()
        for r in rows:
            r["value"] = round((r["qty"] or 0) * (r["price"] or 0), 2)
        Report("Stock report").table(rows, list(COLS) + ["value"], totals=["value"]).open()

    def backup(self):
        d = filedialog.askdirectory(title="Where should the backup go? (a USB stick, say)")
        if d:
            p = make_backup(os.path.join(HERE, "data"), d, "stock")
            messagebox.showinfo("Backup", "Backed up to\n%s" % p)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        import tempfile
        app = StockApp(os.path.join(tempfile.mkdtemp(), "t.db"))
        app.form.vars["item"].set("Exercise books")
        app.form.vars["qty"].set("120")
        app.form.vars["unit"].set("pieces")
        app.form.vars["price"].set("35")
        app.add()
        app.q.set("exer")
        ok = len(app.tree.get_children()) == 1 and "4,200.00" in app.status.cget("text")
        print("selftest ok" if ok else "FAILED " + app.status.cget("text"))
        app.destroy()
        sys.exit(0 if ok else 1)
    StockApp().mainloop()
