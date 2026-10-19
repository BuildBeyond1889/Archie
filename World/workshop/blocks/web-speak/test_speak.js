const { pickVoice, speak } = require("./js/speak.js");
const V = [{ lang: "en-US", name: "a" }, { lang: "sw-KE", name: "b" }];
if (pickVoice(V, "sw").name !== "b" || pickVoice(V, "en-GB").name !== "a" || pickVoice(V, "fr") !== null) throw "voices";
if (speak("hi") !== false) throw "no speech here, should say false";
console.log("web speak ok");
