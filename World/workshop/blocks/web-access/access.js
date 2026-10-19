// Easier to read: bigger text and high contrast, switched on with one tap and remembered.
//   addAccessButtons(document.querySelector("header"));
(function (root) {
  const css = "html.big{font-size:125%}html.big body{font-size:1.15rem}" +
    "html.contrast body{background:#000!important;color:#fff!important}html.contrast a{color:#ff0!important}" +
    "html.contrast button{background:#ff0!important;color:#000!important;border:2px solid #fff!important}" +
    "html.contrast input,html.contrast select,html.contrast textarea{background:#000!important;color:#fff!important;border:2px solid #fff!important}" +
    "html.contrast table th,html.contrast table td{border-color:#fff!important}.acc-btns{display:inline-flex;gap:6px}.acc-btns button{min-width:44px}";
  function get(k) { try { return root.localStorage.getItem(k) === "1"; } catch (e) { return false; } }
  function put(k, v) { try { root.localStorage.setItem(k, v ? "1" : "0"); } catch (e) {} }
  function applySaved() {
    const h = document.documentElement;
    h.classList.toggle("big", get("acc-big")); h.classList.toggle("contrast", get("acc-contrast"));
  }
  function addAccessButtons(where) {
    if (!document.getElementById("acc-css")) { const s = document.createElement("style"); s.id = "acc-css"; s.textContent = css; document.head.appendChild(s); }
    const box = document.createElement("span"); box.className = "acc-btns";
    const big = document.createElement("button"); big.type = "button"; big.textContent = "A+"; big.title = "Bigger text"; big.className = "secondary";
    const con = document.createElement("button"); con.type = "button"; con.textContent = "◐"; con.title = "High contrast"; con.className = "secondary";
    big.onclick = () => { put("acc-big", !get("acc-big")); applySaved(); };
    con.onclick = () => { put("acc-contrast", !get("acc-contrast")); applySaved(); };
    box.appendChild(big); box.appendChild(con); (where || document.body).appendChild(box);
    applySaved();
  }
  if (typeof module !== "undefined") module.exports = { addAccessButtons, css }; else { root.addAccessButtons = addAccessButtons; }
})(typeof window !== "undefined" ? window : globalThis);
