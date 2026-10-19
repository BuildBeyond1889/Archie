// Your web app in English and Swahili (add more languages the same way).
//   T.add({ en: { harvest: "Harvest" }, sw: { harvest: "Mavuno" } });
//   T.setLang("sw");            // remembered on this phone
//   T("save")  -> "Hifadhi"
// In HTML: <button data-t="save">Save</button> and T.apply() fills in the words.
(function (root) {
  const table = {
    en: { save: "Save", cancel: "Cancel", add: "Add", delete: "Delete", edit: "Edit", search: "Search…", date: "Date", name: "Name",
      total: "Total", yes: "Yes", no: "No", back: "Back", print: "Print", export: "Export", import: "Import", settings: "Settings",
      language: "Language", saved: "Saved", offline: "offline", online: "online" },
    sw: { save: "Hifadhi", cancel: "Ghairi", add: "Ongeza", delete: "Futa", edit: "Hariri", search: "Tafuta…", date: "Tarehe", name: "Jina",
      total: "Jumla", yes: "Ndiyo", no: "Hapana", back: "Rudi", print: "Chapisha", export: "Hamisha", import: "Leta", settings: "Mipangilio",
      language: "Lugha", saved: "Imehifadhiwa", offline: "nje ya mtandao", online: "mtandaoni" },
  };
  let lang = "en";
  try { lang = root.localStorage.getItem("archie-lang") || "en"; } catch (e) {}
  function T(key, fill) {
    let s = (table[lang] || {})[key] || table.en[key] || key;
    if (fill) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in fill ? fill[k] : m));
    return s;
  }
  T.add = (more) => { for (const lg in more) table[lg] = Object.assign(table[lg] || {}, more[lg]); };
  T.setLang = (lg) => { lang = lg; try { root.localStorage.setItem("archie-lang", lg); } catch (e) {} if (root.document) T.apply(); };
  T.lang = () => lang;
  T.languages = () => Object.keys(table);
  T.apply = (el) => {
    (el || root.document).querySelectorAll("[data-t]").forEach((n) => { n.textContent = T(n.dataset.t); });
    (el || root.document).querySelectorAll("[data-t-placeholder]").forEach((n) => { n.placeholder = T(n.dataset.tPlaceholder); });
  };
  if (typeof module !== "undefined") module.exports = T; else root.T = T;
})(typeof window !== "undefined" ? window : globalThis);
