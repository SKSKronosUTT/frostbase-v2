import { escapeHtml } from "./helpers.js";

const ICONS = {
  success: "fa-circle-check",
  error: "fa-circle-exclamation",
  warning: "fa-triangle-exclamation",
  info: "fa-circle-info",
};

let toastRoot = null;

function ensureToastRoot() {
  if (toastRoot && document.body.contains(toastRoot)) return toastRoot;
  toastRoot = document.getElementById("toastRoot");
  if (!toastRoot) {
    toastRoot = document.createElement("div");
    toastRoot.id = "toastRoot";
    toastRoot.className = "toast-root";
    document.body.appendChild(toastRoot);
  }
  return toastRoot;
}

function show(message, type = "info", options = {}) {
  const root = ensureToastRoot();
  const toast = document.createElement("div");
  toast.className = `toast toast--${type}`;
  toast.setAttribute("role", "status");
  toast.innerHTML = `
    <span class="toast__icon"><i class="fa-solid ${ICONS[type] || ICONS.info}"></i></span>
    <div class="toast__body">
      ${options.title ? `<strong>${escapeHtml(options.title)}</strong>` : ""}
      <p>${escapeHtml(message)}</p>
    </div>
    <button class="toast__close" type="button" aria-label="Cerrar notificación">
      <i class="fa-solid fa-xmark"></i>
    </button>
    <span class="toast__progress" style="animation-duration:${options.duration || 4500}ms"></span>
  `;
  const close = () => {
    toast.classList.add("toast--leaving");
    setTimeout(() => toast.remove(), 220);
  };
  toast.querySelector(".toast__close").addEventListener("click", close);
  root.appendChild(toast);
  const timeout = setTimeout(close, options.duration || 4500);
  toast.addEventListener("mouseenter", () => clearTimeout(timeout), { once: true });
  return toast;
}

export const notify = {
  success: (message, options) => show(message, "success", options),
  error: (message, options) => show(message, "error", { duration: 6000, ...options }),
  warning: (message, options) => show(message, "warning", options),
  info: (message, options) => show(message, "info", options),
};

export function confirmDialog({
  title = "Confirmar acción",
  message = "¿Deseas continuar?",
  confirmText = "Confirmar",
  cancelText = "Cancelar",
  danger = true,
} = {}) {
  return new Promise((resolve) => {
    const previouslyFocused = document.activeElement;
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

    const close = (value) => {
      document.body.classList.remove("modal-open");
      overlay.classList.add("modal-overlay--leaving");
      setTimeout(() => overlay.remove(), 160);
      document.removeEventListener("keydown", onKeyDown);
      if (previouslyFocused && previouslyFocused.focus) previouslyFocused.focus();
      resolve(value);
    };

    const onKeyDown = (event) => {
      if (event.key === "Escape") close(false);
      if (event.key === "Enter") close(true);
    };

    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) close(false);
      const button = event.target.closest("[data-confirm]");
      if (button) close(button.dataset.confirm === "true");
    });
    overlay.querySelector(".modal__close").addEventListener("click", () => close(false));

    document.body.appendChild(overlay);
    document.body.classList.add("modal-open");
    document.addEventListener("keydown", onKeyDown);
    setTimeout(() => overlay.querySelector('[data-confirm="true"]').focus(), 30);
  });
}
