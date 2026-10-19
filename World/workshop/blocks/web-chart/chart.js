// Bar and line charts on a <canvas>, sharp on phones, no libraries.
//   barChart(document.getElementById("c"), ["Jan", "Feb"], [12, 30], { title: "Harvest (kg)" });
(function (root) {
  function niceMax(v) {
    if (!(v > 0)) return 1;
    let p = 1; while (p * 10 <= v) p *= 10;
    for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p;
    return 10 * p;
  }
  function setup(cv, title) {
    const r = window.devicePixelRatio || 1, w = cv.clientWidth || cv.width, h = cv.clientHeight || cv.height;
    cv.width = w * r; cv.height = h * r;
    const g = cv.getContext("2d"); g.setTransform(r, 0, 0, r, 0, 0); g.clearRect(0, 0, w, h);
    g.font = "12px system-ui, sans-serif"; g.fillStyle = "#222";
    if (title) { g.font = "bold 14px system-ui, sans-serif"; g.textAlign = "center"; g.fillText(title, w / 2, 16); g.font = "12px system-ui, sans-serif"; }
    return { g, w, h };
  }
  function axes(g, w, h, top) {
    const x0 = 44, y0 = 28, x1 = w - 10, y1 = h - 24;
    g.textAlign = "right"; g.textBaseline = "middle";
    for (let i = 0; i <= 4; i++) {
      const y = y1 - (y1 - y0) * i / 4;
      g.strokeStyle = "#e6e6e6"; g.beginPath(); g.moveTo(x0, y); g.lineTo(x1, y); g.stroke();
      g.fillStyle = "#555"; g.fillText(String(+(top * i / 4).toFixed(2)), x0 - 6, y);
    }
    return { x0, y0, x1, y1 };
  }
  function barChart(cv, labels, values, o) {
    o = o || {};
    const { g, w, h } = setup(cv, o.title), top = niceMax(Math.max(0, ...values)), a = axes(g, w, h, top);
    const slot = (a.x1 - a.x0) / Math.max(1, values.length);
    g.textAlign = "center"; g.textBaseline = "top";
    values.forEach((v, i) => {
      const bx = a.x0 + i * slot + slot * 0.2, by = a.y1 - (a.y1 - a.y0) * v / top;
      g.fillStyle = o.color || "#4c78a8"; g.fillRect(bx, by, slot * 0.6, a.y1 - by);
      g.fillStyle = "#222"; g.fillText(String(labels[i]), bx + slot * 0.3, a.y1 + 4);
    });
  }
  function lineChart(cv, labels, values, o) {
    o = o || {};
    const { g, w, h } = setup(cv, o.title), top = niceMax(Math.max(0, ...values)), a = axes(g, w, h, top), n = values.length;
    const pts = values.map((v, i) => [a.x0 + (a.x1 - a.x0) * (n > 1 ? i / (n - 1) : 0.5), a.y1 - (a.y1 - a.y0) * v / top]);
    g.strokeStyle = o.color || "#4c78a8"; g.lineWidth = 2; g.beginPath();
    pts.forEach((p, i) => (i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]))); g.stroke();
    g.textAlign = "center"; g.textBaseline = "top";
    pts.forEach((p, i) => { g.fillStyle = o.color || "#4c78a8"; g.beginPath(); g.arc(p[0], p[1], 4, 0, 7); g.fill(); g.fillStyle = "#222"; g.fillText(String(labels[i]), p[0], a.y1 + 4); });
  }
  function sumBy(rows, key, valueKey) {        // e.g. sumBy(harvests, "crop", "kg") -> {labels, values}
    const m = new Map();
    for (const r of rows) m.set(r[key], (m.get(r[key]) || 0) + (Number(r[valueKey]) || 0));
    return { labels: [...m.keys()], values: [...m.values()] };
  }
  const api = { barChart, lineChart, niceMax, sumBy };
  if (typeof module !== "undefined") module.exports = api; else Object.assign(root, api);
})(typeof window !== "undefined" ? window : globalThis);
