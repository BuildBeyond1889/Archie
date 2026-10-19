"""Desk clock with reminders. Built from Archie's blocks: window app, Store (settings) and Reminders."""
import datetime as dt
import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk
# archie:imports
from lib.store import Store
from lib.reminders import Reminders

HERE = os.path.dirname(os.path.abspath(__file__))


class Clock(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Clock")
        self.settings = Store("clock")
        self.rem = Reminders(os.path.join(HERE, "data", "reminders.json"))
        self.configure(bg="#111")
        self.time = tk.Label(self, font=("Segoe UI", 64, "bold"), fg="#c6f432", bg="#111")
        self.time.pack(padx=30, pady=(20, 0))
        self.date = tk.Label(self, font=("Segoe UI", 16), fg="#ddd", bg="#111")
        self.date.pack()
        box = ttk.Frame(self, padding=10)
        box.pack(fill="x")
        self.when = ttk.Entry(box, width=17)
        self.when.insert(0, (dt.datetime.now() + dt.timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M"))
        self.what = ttk.Entry(box, width=28)
        self.repeat = ttk.Combobox(box, values=["once", "daily", "weekly", "monthly"], width=8, state="readonly")
        self.repeat.set("once")
        for w in (self.when, self.what, self.repeat):
            w.pack(side="left", padx=3)
        ttk.Button(box, text="Add reminder", command=self.add).pack(side="left", padx=3)
        self.list = tk.Listbox(self, height=6, font=("Segoe UI", 11))
        self.list.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.list.bind("<Delete>", self.remove)
        self.tick()

    def add(self):
        text = self.what.get().strip()
        if not text:
            return messagebox.showinfo("Reminder", "Type what to remind you about.")
        try:
            self.rem.add(self.when.get().strip(), text, None if self.repeat.get() == "once" else self.repeat.get())
        except ValueError:
            return messagebox.showerror("Reminder", "Write the time like 2026-04-01 08:00")
        self.what.delete(0, "end")
        self.refresh()

    def remove(self, _e=None):
        sel = self.list.curselection()
        if sel:
            self.rem.remove(self.rem.upcoming(50)[sel[0]]["id"])
            self.refresh()

    def refresh(self):
        self.list.delete(0, "end")
        for r in self.rem.upcoming(50):
            self.list.insert("end", "%s  %s%s" % (r["when"], r["text"], "  (%s)" % r["repeat"] if r.get("repeat") else ""))

    def tick(self):
        now = dt.datetime.now()
        self.time.config(text=now.strftime("%H:%M:%S"))
        self.date.config(text=now.strftime("%A %d %B %Y"))
        if now.second == 0 or not self.list.size():
            self.refresh()
        for r in self.rem.due(now):
            self.bell()
            messagebox.showinfo("Reminder", r["text"])
            self.refresh()
        self.after(1000 - now.microsecond // 1000, self.tick)


if __name__ == "__main__":
    app = Clock()
    if "--selftest" in sys.argv:
        app.after(1500, lambda: (print("selftest ok" if ":" in app.time.cget("text") else "FAILED"), app.destroy()))
    app.mainloop()
