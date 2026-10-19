const { toCSV, parseCSV } = require("./js/csv.js");
const rows = [{ crop: "mahindi", kg: 40, note: 'big, "good"' }, { crop: "maharagwe", kg: 12.5 }];
const back = parseCSV(toCSV(rows));
if (back[0].note !== 'big, "good"' || back[1].kg !== 12.5 || back[0].kg !== 40) throw JSON.stringify(back);
if (parseCSV("﻿a;b\r\n1;2\r\n")[0].b !== 2) throw "semicolon";
console.log("web csv ok");
