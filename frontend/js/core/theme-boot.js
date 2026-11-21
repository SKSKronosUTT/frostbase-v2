/* Aplica el tema guardado antes de pintar para evitar el destello claro. */
(function () {
  try {
    var stored = localStorage.getItem("frostbase-theme");
    if (stored === "dark" || stored === "light") {
      document.documentElement.dataset.theme = stored;
    }
  } catch (error) {
    /* localStorage puede no estar disponible (modo privado). */
  }
})();
