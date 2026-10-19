// Forms with checks. Describe the fields once; get a form and clean values.
//   const FIELDS = [{ name: "crop", label: "Crop", type: "choice", choices: ["maize", "beans"], required: true },
//                   { name: "kg", label: "Weight (kg)", type: "number", min: 0, required: true },
//                   { name: "date", label: "Date", type: "date" }];
//   const form = makeForm(document.getElementById("f"), FIELDS, (values) => db.add("harvests", values));
(function (root) {
  function validate(fields, raw) {
    const vals = {}, errs = {};
    for (const f of fields) {
      const t = f.type || "text";
      let v = raw[f.name] == null ? "" : String(raw[f.name]).trim();
      if (!v) { if (f.required) errs[f.name] = (f.label || f.name) + " is needed"; vals[f.name] = null; continue; }
      if (t === "number") {
        const n = Number(v.replace(",", "."));
        if (!isFinite(n)) { errs[f.name] = "Must be a number"; continue; }
        if (f.min != null && n < f.min) errs[f.name] = "Must be at least " + f.min;
        else if (f.max != null && n > f.max) errs[f.name] = "Must be at most " + f.max;
        vals[f.name] = n;
      } else if (t === "date") {
        let m = v.match(/^(\d{4})-(\d{2})-(\d{2})$/), d = null;
        if (m) d = [m[1], m[2], m[3]];
        else if ((m = v.match(/^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{4})$/))) d = [m[3], m[2].padStart(2, "0"), m[1].padStart(2, "0")];
        const ok = d && !isNaN(Date.parse(d.join("-"))) && new Date(d.join("-")).toISOString().slice(0, 10) === d.join("-");
        if (!ok) errs[f.name] = "Use a date like 2026-03-31"; else vals[f.name] = d.join("-");
      } else if (t === "choice") {
        if (!(f.choices || []).includes(v)) errs[f.name] = "Pick one of the choices";
        vals[f.name] = v;
      } else if (t === "phone") {
        const d = v.replace(/[\s\-()]/g, "");
        if (!/^\+?\d{7,15}$/.test(d)) errs[f.name] = "Doesn't look like a phone number";
        vals[f.name] = d;
      } else {
        if (f.maxlen && v.length > f.maxlen) errs[f.name] = "Too long (most " + f.maxlen + " letters)";
        vals[f.name] = v;
      }
    }
    return { values: vals, errors: errs };
  }

  function makeForm(el, fields, onSave, saveLabel) {
    el.innerHTML = "";
    const inputs = {};
    for (const f of fields) {
      const wrap = document.createElement("label");
      wrap.style.display = "block"; wrap.style.margin = "8px 0";
      wrap.textContent = (f.label || f.name) + (f.required ? " *" : "");
      let inp;
      if (f.type === "choice") {
        inp = document.createElement("select");
        inp.innerHTML = "<option value=''></option>" + (f.choices || []).map((c) => "<option></option>").join("");
        (f.choices || []).forEach((c, i) => { inp.options[i + 1].value = c; inp.options[i + 1].textContent = c; });
      } else {
        inp = document.createElement("input");
        inp.type = f.type === "number" ? "text" : f.type === "date" ? "date" : f.type === "phone" ? "tel" : "text";
        if (f.type === "number") inp.inputMode = "decimal";
      }
      inp.name = f.name; inp.style.display = "block"; inp.style.width = "100%";
      if (f.default != null) inp.value = f.default;
      const err = document.createElement("div"); err.className = "err";
      wrap.appendChild(inp); wrap.appendChild(err); el.appendChild(wrap);
      inputs[f.name] = { inp, err };
    }
    const btn = document.createElement("button");
    btn.textContent = saveLabel || "Save"; btn.type = "button"; el.appendChild(btn);
    const api = {
      read() {
        const raw = {}; for (const k in inputs) raw[k] = inputs[k].inp.value;
        const r = validate(fields, raw);
        for (const k in inputs) inputs[k].err.textContent = r.errors[k] || "";
        return r;
      },
      clear() { for (const f of fields) inputs[f.name].inp.value = f.default != null ? f.default : ""; },
      fill(rec) { for (const k in inputs) if (rec[k] != null) inputs[k].inp.value = rec[k]; },
    };
    btn.onclick = () => { const r = api.read(); if (!Object.keys(r.errors).length && onSave) { onSave(r.values); api.clear(); } };
    return api;
  }
  const api = { validate, makeForm };
  if (typeof module !== "undefined") module.exports = api; else Object.assign(root, api);
})(typeof window !== "undefined" ? window : globalThis);
