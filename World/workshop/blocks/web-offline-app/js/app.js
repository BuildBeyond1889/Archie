// Your app starts here.
(function () {
  const app = document.getElementById("app");
  app.innerHTML = "<div class='card'><p>Hello! This app keeps working with no internet once it has been opened once.</p></div>";

  // Show whether there's internet right now (the app works either way).
  const net = document.getElementById("net");
  function showNet() { net.textContent = navigator.onLine ? "online" : "offline"; }
  addEventListener("online", showNet); addEventListener("offline", showNet); showNet();

  // Register the offline copy. Only works when served from http://localhost, a Pi hotspot, or https.
  if ("serviceWorker" in navigator && location.protocol !== "file:") {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
})();
