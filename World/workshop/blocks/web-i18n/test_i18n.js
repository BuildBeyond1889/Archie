globalThis.localStorage = { d: {}, getItem(k) { return this.d[k] || null; }, setItem(k, v) { this.d[k] = v; } };
const T = require("./js/i18n.js");
T.add({ en: { hello: "Hello, {name}", only: "E" }, sw: { hello: "Habari, {name}" } });
if (T("save") !== "Save") throw "en";
T.setLang("sw");
if (T("save") !== "Hifadhi" || T("hello", { name: "Juma" }) !== "Habari, Juma" || T("only") !== "E" || T("nope") !== "nope") throw "sw";
if (localStorage.getItem("archie-lang") !== "sw") throw "remember";
console.log("web i18n ok");
