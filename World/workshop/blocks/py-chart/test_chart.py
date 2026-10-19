from lib.chart import nice_max, bar_chart, line_chart
assert nice_max(7) == 10 and nice_max(34) == 50 and nice_max(120) == 200 and nice_max(0) == 1 and nice_max(25) == 25
try:
    import tkinter as tk
    r = tk.Tk()
    c = tk.Canvas(r, width=400, height=240); c.pack()
    bar_chart(c, ["a", "b"], [3, 9], title="t"); assert len(c.find_all()) > 10
    line_chart(c, ["a", "b", "c"], [1, 5, 2]); r.destroy()
except Exception as e:
    if "display" not in str(e).lower(): raise
print("chart ok")
