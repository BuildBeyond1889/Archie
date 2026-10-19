// Read text aloud (for people still learning to read, or with poor eyesight).
//   speak("Karibu!", "sw");   speak("Welcome", "en");   stopSpeaking();
// Uses the voices built into the phone or computer, so it works offline when a voice for that language is installed.
(function (root) {
  function pickVoice(voices, lang) {
    lang = (lang || "en").toLowerCase();
    return voices.find((v) => v.lang.toLowerCase() === lang) || voices.find((v) => v.lang.toLowerCase().startsWith(lang.slice(0, 2))) || null;
  }
  function canSpeak() { return typeof root.speechSynthesis !== "undefined"; }
  function speak(text, lang, rate) {
    if (!canSpeak()) return false;
    const u = new SpeechSynthesisUtterance(text);
    const v = pickVoice(root.speechSynthesis.getVoices(), lang);
    if (v) u.voice = v;
    u.lang = v ? v.lang : (lang || "en");
    u.rate = rate || 0.9;
    root.speechSynthesis.cancel(); root.speechSynthesis.speak(u);
    return true;
  }
  function stopSpeaking() { if (canSpeak()) root.speechSynthesis.cancel(); }
  function hasVoice(lang) { return canSpeak() && !!pickVoice(root.speechSynthesis.getVoices(), lang); }
  const api = { speak, stopSpeaking, hasVoice, canSpeak, pickVoice };
  if (typeof module !== "undefined") module.exports = api; else Object.assign(root, api);
})(typeof window !== "undefined" ? window : globalThis);
