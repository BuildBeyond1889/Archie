// Class attendance: names, a daily register, absences this month, a printable register.
(function () {
  T.add({
    en: { title: "Attendance", day: "Day", present: "Present", absent: "Absent", addName: "Add a name", classList: "Class", missed: "Days missed this month",
      register: "Register", allPresent: "Everyone present", backup: "Backup", remove: "Remove from the class?" },
    sw: { title: "Mahudhurio", day: "Siku", present: "Yupo", absent: "Hayupo", addName: "Ongeza jina", classList: "Darasa", missed: "Siku alizokosa mwezi huu",
      register: "Rejista", allPresent: "Wote wapo", backup: "Hifadhi nakala", remove: "Ondoa darasani?" },
  });
  const db = new Store("attendance");
  const app = document.getElementById("app");
  addAccessButtons(document.querySelector(".bar"));
  const today = new Date().toISOString().slice(0, 10);
  app.innerHTML = "<div class='row'><select id='lang'><option value='en'>English</option><option value='sw'>Kiswahili</option></select>" +
    "<label><span data-t='day'></span> <input type='date' id='day'></label></div>" +
    "<div class='row' style='margin:10px 0'><input id='nm' style='flex:1'><button id='add' data-t='addName'></button></div>" +
    "<button id='all' class='secondary' data-t='allPresent'></button><div id='reg'></div>" +
    "<h2 data-t='missed'></h2><div id='sum'></div>" +
    "<div class='row' style='margin-top:12px'><button id='print' data-t='register'></button><button id='csv' class='secondary' data-t='export'></button><button id='bk' class='secondary' data-t='backup'></button></div>";
  const day = document.getElementById("day"); day.value = today;
  const lang = document.getElementById("lang"); lang.value = T.lang(); lang.onchange = () => { T.setLang(lang.value); render(); };
  const marks = () => db.get("marks", {});                  // { "2026-03-31": { "<id>": "P" | "A" } }
  function mark(id, v) { const m = marks(); (m[day.value] = m[day.value] || {})[id] = v; db.set("marks", m); render(); }
  function render() {
    T.apply();
    document.title = document.getElementById("title").textContent = T("title");
    document.getElementById("nm").placeholder = T("name");
    const kids = db.list("kids").sort((a, b) => a.name.localeCompare(b.name));
    const m = marks()[day.value] || {};
    const reg = document.getElementById("reg"); reg.innerHTML = "";
    for (const k of kids) {
      const row = document.createElement("div"); row.className = "card row"; row.style.justifyContent = "space-between";
      const n = document.createElement("b"); n.textContent = k.name; n.onclick = () => { if (confirm(T("remove") + " " + k.name)) { db.remove("kids", k.id); render(); } };
      const p = document.createElement("button"); p.textContent = T("present"); p.className = m[k.id] === "P" ? "" : "secondary"; p.onclick = () => mark(k.id, "P");
      const a = document.createElement("button"); a.textContent = T("absent"); a.className = m[k.id] === "A" ? "" : "secondary"; a.onclick = () => mark(k.id, "A");
      if (m[k.id] === "A") a.style.background = "#b00020";
      const btns = document.createElement("span"); btns.className = "row"; btns.append(p, a);
      row.append(n, btns); reg.appendChild(row);
    }
    makeTable(document.getElementById("sum"), [{ key: "name", label: T("name") }, { key: "missed", label: T("absent"), num: true }], { searchLabel: T("search") })
      .show(summary().sort((a, b) => b.missed - a.missed));
  }
  function summary() {
    const month = day.value.slice(0, 7), all = marks();
    return db.list("kids").map((k) => ({ name: k.name, missed: Object.keys(all).filter((d) => d.startsWith(month) && all[d][k.id] === "A").length }));
  }
  document.getElementById("add").onclick = () => { const v = document.getElementById("nm").value.trim(); if (v) { db.add("kids", { name: v }); document.getElementById("nm").value = ""; render(); } };
  document.getElementById("all").onclick = () => { const m = marks(); m[day.value] = {}; db.list("kids").forEach((k) => (m[day.value][k.id] = "P")); db.set("marks", m); render(); };
  day.onchange = render;
  document.getElementById("print").onclick = () => {
    const month = day.value.slice(0, 7), all = marks(), days = Object.keys(all).filter((d) => d.startsWith(month)).sort();
    const rows = db.list("kids").map((k) => { const r = { name: k.name }; days.forEach((d) => (r[d.slice(8)] = all[d][k.id] || "")); return r; });
    printReport(T("register") + " " + month, [{ table: rows, cols: [{ key: "name", label: T("name") }].concat(days.map((d) => ({ key: d.slice(8), label: d.slice(8) }))) }]);
  };
  document.getElementById("csv").onclick = () => downloadCSV("attendance-" + day.value.slice(0, 7) + ".csv", summary());
  document.getElementById("bk").onclick = () => db.exportFile();
  if ("serviceWorker" in navigator && location.protocol !== "file:") navigator.serviceWorker.register("sw.js").catch(() => {});
  render();
})();
