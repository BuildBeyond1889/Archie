// A table people can search and sort by tapping a column.
//   const t = makeTable(document.getElementById("list"), [
//     { key: "date", label: "Date" }, { key: "crop", label: "Crop" }, { key: "kg", label: "Kg", num: true }],
//     { onRow: (row) => edit(row), totals: ["kg"] });
//   t.show(db.list("harvests"));
(function (root) {
  function norm(s) { return String(s == null ? "" : s).normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
  function filterRows(rows, q, cols) {
    const words = norm(q).split(/\s+/).filter(Boolean);
    if (!words.length) return rows.slice();
    return rows.filter((r) => { const hay = cols.map((c) => norm(r[c.key])).join(" "); return words.every((w) => hay.includes(w)); });
  }
  function sortRows(rows, key, dir) {
    return rows.slice().sort((a, b) => {
      const x = a[key], y = b[key];
      if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
      const r = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true });
      return dir < 0 ? -r : r;
    });
  }
  function total(rows, key) { return Math.round(rows.reduce((s, r) => s + (Number(r[key]) || 0), 0) * 100) / 100; }

  function makeTable(el, cols, opts) {
    opts = opts || {};
    let rows = [], q = "", sortKey = null, dir = 1;
    el.innerHTML = "";
    const search = document.createElement("input");
    search.type = "search"; search.placeholder = opts.searchLabel || "Search…"; search.style.width = "100%"; search.style.marginBottom = "8px";
    const table = document.createElement("table");
    const info = document.createElement("div"); info.style.fontSize = ".85rem"; info.style.color = "#555";
    const scroll = document.createElement("div"); scroll.style.overflowX = "auto"; scroll.appendChild(table);   // wide tables scroll on small phones
    el.appendChild(search); el.appendChild(scroll); el.appendChild(info);
    search.oninput = () => { q = search.value; draw(); };
    function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]); }
    function draw() {
      let shown = filterRows(rows, q, cols);
      if (sortKey) shown = sortRows(shown, sortKey, dir);
      const head = "<tr>" + cols.map((c) => "<th data-k='" + c.key + "' style='cursor:pointer'>" + esc(c.label != null ? c.label : c.key) + (sortKey === c.key ? (dir > 0 ? " ▲" : " ▼") : "") + "</th>").join("") + "</tr>";
      const body = shown.map((r, i) => "<tr data-i='" + i + "'>" + cols.map((c) => "<td" + (c.num ? " style='text-align:right'" : "") + ">" + esc(c.show ? c.show(r[c.key], r) : r[c.key]) + "</td>").join("") + "</tr>").join("");
      const tot = opts.totals ? "<tr>" + cols.map((c) => "<th" + (c.num ? " style='text-align:right'" : "") + ">" + (opts.totals.includes(c.key) ? total(shown, c.key) : "") + "</th>").join("") + "</tr>" : "";
      table.innerHTML = head + body + tot;
      info.textContent = shown.length + " of " + rows.length;
      table.querySelectorAll("th[data-k]").forEach((th) => th.onclick = () => { const k = th.dataset.k; dir = sortKey === k ? -dir : 1; sortKey = k; draw(); });
      if (opts.onRow) table.querySelectorAll("tr[data-i]").forEach((tr) => { tr.style.cursor = "pointer"; tr.onclick = () => opts.onRow(shown[+tr.dataset.i]); });
    }
    return { show(r) { rows = r || []; draw(); } };
  }
  const api = { makeTable, filterRows, sortRows, total };
  if (typeof module !== "undefined") module.exports = api; else Object.assign(root, api);
})(typeof window !== "undefined" ? window : globalThis);
