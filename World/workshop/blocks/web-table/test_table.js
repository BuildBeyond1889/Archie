const { filterRows, sortRows, total } = require("./js/table.js");
const C = [{ key: "name" }, { key: "village" }];
const R = [{ name: "Amina", village: "Kisumu", kg: 3 }, { name: "José", village: "Nakuru", kg: 10 }, { name: "Baraka", village: "Kisii", kg: null }];
if (filterRows(R, "jose", C).length !== 1 || filterRows(R, "ki", C).length !== 2) throw "filter";
if (sortRows(R, "kg", 1)[0].name !== "Amina" || sortRows(R, "kg", -1)[0].name !== "José" || sortRows(R, "kg", 1)[2].name !== "Baraka") throw "sort";
if (total(R, "kg") !== 13) throw "total";
console.log("web table ok");
