/* Aplica el tema guardado (o el del sistema) antes de pintar. */
(function () {
  try {
    var stored = localStorage.getItem("frostbase-theme");
    if (stored === "dark" || stored === "light") {
      document.documentElement.dataset.theme = stored;
    } else if (
      window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
    ) {
      document.documentElement.dataset.theme = "dark";
    }
  } catch (error) {
    /* localStorage puede no estar disponible (modo privado). */
  }
})();
