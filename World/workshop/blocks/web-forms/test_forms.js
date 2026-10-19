const { validate } = require("./js/forms.js");
const F = [{ name: "crop", type: "choice", choices: ["maize"], required: true }, { name: "kg", type: "number", min: 0, required: true },
  { name: "date", type: "date" }, { name: "tel", type: "phone" }, { name: "note", maxlen: 5 }];
let r = validate(F, { crop: "maize", kg: "2,5", date: "31/3/2026", tel: "+254 712 345678", note: "ok" });
if (Object.keys(r.errors).length || r.values.kg !== 2.5 || r.values.date !== "2026-03-31" || r.values.tel !== "+254712345678") throw JSON.stringify(r);
r = validate(F, { crop: "rice", kg: "-1", date: "31/2/2026", tel: "12", note: "toolong" });
if (Object.keys(r.errors).sort().join() !== "crop,date,kg,note,tel") throw JSON.stringify(r.errors);
console.log("web forms ok");
