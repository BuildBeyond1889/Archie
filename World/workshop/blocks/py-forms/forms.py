"""Forms with checks: describe the fields once, get a form in the window and clean values back.

    FIELDS = [
        {"name": "crop", "label": "Crop", "type": "choice", "choices": ["maize", "beans"], "required": True},
        {"name": "kg", "label": "Weight (kg)", "type": "number", "min": 0, "required": True},
        {"name": "date", "label": "Date", "type": "date"},
        {"name": "note", "label": "Note"},
    ]
    form = Form(parent, FIELDS)
    values, errors = form.values()      # errors = {"kg": "Must be a number"}

validate(FIELDS, raw) does the checking on its own, so you can use it in web apps and tests too.
"""
import datetime
import re


def validate(fields, raw):
    """raw = {name: text}. Returns (clean values, {name: error message})."""
    vals, errs = {}, {}
    for f in fields:
        n, t = f["name"], f.get("type", "text")
        v = str(raw.get(n, "") if raw.get(n) is not None else "").strip()
        if not v:
            if f.get("required"):
                errs[n] = "%s is needed" % f.get("label", n)
            vals[n] = None
            continue
        if t == "number":
            try:
                num = float(v.replace(",", "."))
                num = int(num) if num.is_integer() and "." not in v and "," not in v else num
            except ValueError:
                errs[n] = "Must be a number"
                continue
            if "min" in f and num < f["min"]:
                errs[n] = "Must be at least %g" % f["min"]
            elif "max" in f and num > f["max"]:
                errs[n] = "Must be at most %g" % f["max"]
            vals[n] = num
        elif t == "date":
            try:
                vals[n] = datetime.date.fromisoformat(v).isoformat()
            except ValueError:
                m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$", v)       # 31/3/2026 too
                try:
                    vals[n] = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat() if m else None
                except ValueError:
                    vals[n] = None
                if not vals[n]:
                    errs[n] = "Use a date like 2026-03-31"
        elif t == "choice":
            if v not in f.get("choices", []):
                errs[n] = "Pick one of the choices"
            vals[n] = v
        elif t == "phone":
            d = re.sub(r"[\s\-()]", "", v)
            if not re.match(r"^\+?\d{7,15}$", d):
                errs[n] = "Doesn't look like a phone number"
            vals[n] = d
        else:
            if "maxlen" in f and len(v) > f["maxlen"]:
                errs[n] = "Too long (most %d letters)" % f["maxlen"]
            vals[n] = v
    return vals, errs


class Form:
    """A tkinter form built from the field list."""
    def __init__(self, parent, fields):
        import tkinter as tk
        from tkinter import ttk
        self.fields, self.vars, self.errs = fields, {}, {}
        self.frame = ttk.Frame(parent)
        for r, f in enumerate(fields):
            ttk.Label(self.frame, text=f.get("label", f["name"]) + (" *" if f.get("required") else "")).grid(row=r, column=0, sticky="w", pady=3, padx=(0, 8))
            var = tk.StringVar(value=str(f.get("default", "")))
            if f.get("type") == "choice":
                w = ttk.Combobox(self.frame, textvariable=var, values=f.get("choices", []), state="readonly")
            else:
                w = ttk.Entry(self.frame, textvariable=var, width=32)
            w.grid(row=r, column=1, sticky="we")
            e = ttk.Label(self.frame, text="", foreground="#b00020")
            e.grid(row=r, column=2, sticky="w", padx=6)
            self.vars[f["name"]], self.errs[f["name"]] = var, e
        self.frame.columnconfigure(1, weight=1)

    def pack(self, **k):
        self.frame.pack(**k)
        return self

    def grid(self, **k):
        self.frame.grid(**k)
        return self

    def values(self):
        vals, errs = validate(self.fields, {k: v.get() for k, v in self.vars.items()})
        for n, lab in self.errs.items():
            lab.config(text=errs.get(n, ""))
        return vals, errs

    def clear(self):
        for f in self.fields:
            self.vars[f["name"]].set(str(f.get("default", "")))
