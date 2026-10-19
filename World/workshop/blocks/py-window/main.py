"""A desktop window app (tkinter is built into Python)."""
import sys
import tkinter as tk
from tkinter import messagebox, ttk
# archie:imports

APP_NAME = "My App"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("720x480")
        self.minsize(400, 300)
        self._menu()
        self.main = ttk.Frame(self, padding=12)          # your widgets go in here
        self.main.pack(fill="both", expand=True)
        self.bar = ttk.Label(self, text="Ready", anchor="w", padding=(8, 2))
        self.bar.pack(fill="x", side="bottom")
        self.build()

    def _menu(self):
        m = tk.Menu(self)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label="Quit", command=self.destroy, accelerator="Ctrl+Q")
        m.add_cascade(label="File", menu=f)
        h = tk.Menu(m, tearoff=0)
        h.add_command(label="About", command=lambda: messagebox.showinfo(APP_NAME, APP_NAME + "\nMade with Archie."))
        m.add_cascade(label="Help", menu=h)
        self.config(menu=m)
        self.bind("<Control-q>", lambda e: self.destroy())

    def build(self):
        ttk.Label(self.main, text="Hello! Build your app here.", font=("Segoe UI", 14)).pack(pady=20)
        ttk.Button(self.main, text="Click me", command=lambda: self.status("Clicked")).pack()

    def status(self, text):
        self.bar.config(text=text)


if __name__ == "__main__":
    app = App()
    if "--selftest" in sys.argv:                          # used by Archie's test: open, then close
        app.after(300, app.destroy)
    app.mainloop()
