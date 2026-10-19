const { niceMax, sumBy } = require("./js/chart.js");
if (niceMax(7) !== 10 || niceMax(34) !== 50 || niceMax(120) !== 200 || niceMax(0) !== 1 || niceMax(25) !== 25) throw "niceMax";
const s = sumBy([{ c: "a", kg: 2 }, { c: "b", kg: 1 }, { c: "a", kg: "3" }], "c", "kg");
if (s.labels.join() !== "a,b" || s.values.join() !== "5,1") throw "sumBy";
console.log("web chart ok");
