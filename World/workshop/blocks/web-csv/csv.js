// Spreadsheet files (CSV) in and out of a web app.
//   downloadCSV("harvests.csv", rows);                 // opens in Excel / LibreOffice / Sheets
//   readCSVFile(input.files[0]).then((rows) => ...)
(function (root) {
  function toCSV(rows, fields) {
    fields = fields || [...new Set(rows.flatMap((r) => Object.keys(r)))];
    const q = (v) => { const s = v == null ? "" : String(v); return /[",\n;]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    return [fields.map(q).join(",")].concat(rows.map((r) => fields.map((f) => q(r[f])).join(","))).join("\r\n");
  }
  function parseCSV(text) {
    text = text.replace(/^﻿/, "");
    const first = text.split(/\r?\n/)[0] || "";
    const sep = (first.match(/;/g) || []).length > (first.match(/,/g) || []).length ? ";" : first.includes("\t") && !first.includes(",") ? "\t" : ",";
    const out = []; let row = [], cell = "", inQ = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (inQ) { if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (c === '"') inQ = false; else cell += c; }
      else if (c === '"') inQ = true;
      else if (c === sep) { row.push(cell); cell = ""; }
      else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(cell); out.push(row); row = []; cell = ""; }
      else cell += c;
    }
    if (cell || row.length) { row.push(cell); out.push(row); }
    const head = out.shift() || [];
    return out.filter((r) => r.some((x) => x !== "")).map((r) => {
      const o = {}; head.forEach((h, i) => { const v = r[i] == null ? "" : r[i]; o[h] = v !== "" && !isNaN(Number(v)) ? Number(v) : v; }); return o;
    });
  }
  function downloadCSV(name, rows, fields) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + toCSV(rows, fields)], { type: "text/csv" }));
    a.download = name; document.body.appendChild(a); a.click(); a.remove();
  }
  function readCSVFile(file) { return file.text().then(parseCSV); }
  const api = { toCSV, parseCSV, downloadCSV, readCSVFile };
  if (typeof module !== "undefined") module.exports = api; else Object.assign(root, api);
})(typeof window !== "undefined" ? window : globalThis);
