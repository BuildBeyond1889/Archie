"""Simple charts drawn on a tkinter Canvas (no installs).

    c = tk.Canvas(root, width=500, height=300, bg="white"); c.pack()
    bar_chart(c, ["Jan", "Feb", "Mar"], [12, 30, 22], title="Harvest (kg)")
    line_chart(c, labels, values)
"""


def nice_max(v):
    """Round the top of the axis up to a tidy number (5, 10, 20, 50, 100...)."""
    if v <= 0:
        return 1
    p = 1
    while p * 10 <= v:
        p *= 10
    for m in (1, 2, 2.5, 5, 10):
        if m * p >= v:
            return m * p
    return 10 * p


def _frame(c, labels, values, title, pad):
    w, h = int(c["width"]), int(c["height"])
    top = nice_max(max(values) if values else 1)
    c.delete("all")
    if title:
        c.create_text(w / 2, 12, text=title, font=("Segoe UI", 11, "bold"))
    x0, y0, x1, y1 = pad + 20, pad + 10, w - pad, h - pad
    for i in range(5):                                   # light grid lines with numbers
        y = y1 - (y1 - y0) * i / 4
        c.create_line(x0, y, x1, y, fill="#e6e6e6")
        c.create_text(x0 - 6, y, text=("%g" % (top * i / 4)), anchor="e", font=("Segoe UI", 8), fill="#555")
    c.create_line(x0, y1, x1, y1, fill="#888")
    return x0, y0, x1, y1, top


def bar_chart(c, labels, values, title="", color="#4c78a8", pad=30):
    x0, y0, x1, y1, top = _frame(c, labels, values, title, pad)
    n = max(1, len(values))
    slot = (x1 - x0) / n
    for i, (lab, v) in enumerate(zip(labels, values)):
        bx = x0 + i * slot + slot * 0.2
        by = y1 - (y1 - y0) * (v / top)
        c.create_rectangle(bx, by, bx + slot * 0.6, y1, fill=color, outline="")
        c.create_text(bx + slot * 0.3, y1 + 10, text=str(lab), font=("Segoe UI", 8))
        c.create_text(bx + slot * 0.3, by - 8, text="%g" % v, font=("Segoe UI", 8), fill="#333")


def line_chart(c, labels, values, title="", color="#4c78a8", pad=30):
    x0, y0, x1, y1, top = _frame(c, labels, values, title, pad)
    n = len(values)
    if n == 0:
        return
    pts = []
    for i, v in enumerate(values):
        x = x0 + (x1 - x0) * (i / (n - 1) if n > 1 else 0.5)
        y = y1 - (y1 - y0) * (v / top)
        pts.append((x, y))
        c.create_text(x, y1 + 10, text=str(labels[i]), font=("Segoe UI", 8))
    if len(pts) > 1:
        c.create_line(*[k for p in pts for k in p], fill=color, width=2)
    for x, y in pts:
        c.create_oval(x - 4, y - 4, x + 4, y + 4, fill=color, outline="white", width=2)
