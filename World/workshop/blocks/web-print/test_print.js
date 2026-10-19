const { reportHTML } = require("./js/print.js");
const h = reportHTML("A <b>", [{ heading: "S" }, { text: "x" }, { table: [{ k: 2 }, { k: 3 }], totals: ["k"] }]);
if (!h.includes("A &lt;b&gt;") || !h.includes("<th>5</th>")) throw h;
console.log("web print ok");
