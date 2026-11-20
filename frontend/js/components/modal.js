const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

function focusable(overlay) {
  return Array.from(overlay.querySelectorAll(FOCUSABLE)).filter(
    (element) => element.offsetParent !== null || element === document.activeElement
  );
}

export function activateModal(
  overlay,
  { onClose, initialFocus, closeOnBackdrop = true } = {}
) {
  const previouslyFocused = document.activeElement;
  const deactivators = [];

  const onKeyDown = (event) => {
    if (event.key === "Escape" && onClose) {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;
    const items = focusable(overlay);
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  document.addEventListener("keydown", onKeyDown);
  deactivators.push(() => document.removeEventListener("keydown", onKeyDown));

  if (closeOnBackdrop) {
    const onBackdrop = (event) => {
      if (event.target === overlay && onClose) onClose();
    };
    overlay.addEventListener("click", onBackdrop);
    deactivators.push(() => overlay.removeEventListener("click", onBackdrop));
  }

  window.setTimeout(() => {
    const target = initialFocus || focusable(overlay)[0];
    target?.focus();
  }, 30);

  return function deactivate() {
    deactivators.forEach((fn) => fn());
    if (previouslyFocused?.focus) previouslyFocused.focus();
  };
}

export function confirmDialog({
  title = "Confirmar acción",
  message = "¿Deseas continuar?",
  confirmText = "Confirmar",
  cancelText = "Cancelar",
  danger = true,
} = {}) {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal modal--sm" role="dialog" aria-modal="true" aria-labelledby="confirmTitle">
        <div class="modal__header">
          <h2 id="confirmTitle">${escapeHtml(title)}</h2>
          <button class="icon-button modal__close" type="button" aria-label="Cerrar">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
        <div class="modal__body">
          <p class="confirm-message">${escapeHtml(message)}</p>
        </div>
        <div class="modal__footer">
          <button class="btn btn--ghost" data-confirm="false" type="button">${escapeHtml(cancelText)}</button>
          <button class="btn ${danger ? "btn--danger" : "btn--primary"}" data-confirm="true" type="button">${escapeHtml(confirmText)}</button>
        </div>
      </div>
    `;

    let deactivate = () => {};
    const close = (value) => {
      document.body.classList.remove("modal-open");
      overlay.classList.add("modal-overlay--leaving");
      deactivate();
      setTimeout(() => overlay.remove(), 160);
      resolve(value);
    };

    overlay.querySelectorAll("[data-confirm]").forEach((button) => {
      button.addEventListener("click", () => close(button.dataset.confirm === "true"));
    });
    overlay
      .querySelector(".modal__close")
      .addEventListener("click", () => close(false));

    document.body.appendChild(overlay);
    document.body.classList.add("modal-open");
    deactivate = activateModal(overlay, { onClose: () => close(false) });
    window.setTimeout(
      () => overlay.querySelector('[data-confirm="true"]')?.focus(),
      35
    );
  });
}

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
