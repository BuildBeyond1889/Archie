// Printable reports from a web app: opens a clean page and the print dialog (or "Save as PDF").
//   printReport("Harvest - March", [
//     { heading: "Summary" }, { text: "Total: 340 kg" },
//     { table: rows, cols: [{ key: "crop", label: "Crop" }, { key: "kg", label: "Kg" }], totals: ["kg"] }]);
(function (root) {
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  function reportHTML(title, parts) {
    const body = parts.map((p) => {
      if (p.heading) return "<h2>" + esc(p.heading) + "</h2>";
      if (p.text) return "<p>" + esc(p.text).replace(/\n/g, "<br>") + "</p>";
      if (p.table) {
        const cols = p.cols || Object.keys(p.table[0] || {}).map((k) => ({ key: k }));
        const sum = (k) => Math.round(p.table.reduce((s, r) => s + (Number(r[k]) || 0), 0) * 100) / 100;
        return "<table><tr>" + cols.map((c) => "<th>" + esc(c.label || c.key) + "</th>").join("") + "</tr>" +
          p.table.map((r) => "<tr>" + cols.map((c) => "<td>" + esc(r[c.key]) + "</td>").join("") + "</tr>").join("") +
          (p.totals ? "<tr>" + cols.map((c) => "<th>" + (p.totals.includes(c.key) ? sum(c.key) : "") + "</th>").join("") + "</tr>" : "") + "</table>";
      }
      return "";
    }).join("\n");
    return "<!DOCTYPE html><html><head><meta charset='utf-8'><title>" + esc(title) + "</title><style>" +
      "body{font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:24px auto;padding:0 16px}h1{font-size:22px;border-bottom:2px solid #333}" +
      "table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #bbb;padding:4px 7px;text-align:left}th{background:#eee}.m{color:#555;font-size:12px}" +
      "</style></head><body><h1>" + esc(title) + "</h1><p class='m'>Made " + new Date().toLocaleString() + "</p>" + body + "</body></html>";
  }
  function printReport(title, parts) {
    const w = window.open("", "_blank");
    if (!w) { alert("Allow pop-ups to print the report."); return; }
    w.document.write(reportHTML(title, parts)); w.document.close();
    w.onload = () => w.print(); setTimeout(() => { try { w.print(); } catch (e) {} }, 400);
  }
  const api = { reportHTML, printReport };
  if (typeof module !== "undefined") module.exports = api; else Object.assign(root, api);
})(typeof window !== "undefined" ? window : globalThis);
