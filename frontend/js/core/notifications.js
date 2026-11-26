import { escapeHtml } from "./helpers.js";

export { confirmDialog } from "../components/modal.js";

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
  // Los errores se anuncian de inmediato y no se autodescartan (FE-013).
  toast.setAttribute("role", type === "error" ? "alert" : "status");
  toast.setAttribute("aria-atomic", "true");
  toast.innerHTML = `
    <span class="toast__icon"><i class="fa-solid ${ICONS[type] || ICONS.info}"></i></span>
    <div class="toast__body">
      ${options.title ? `<strong>${escapeHtml(options.title)}</strong>` : ""}
      <p>${escapeHtml(message)}</p>
    </div>
    <button class="toast__close" type="button" aria-label="Cerrar notificación">
      <i class="fa-solid fa-xmark"></i>
    </button>
    <span class="toast__progress"></span>
  `;

  const duration = type === "error" ? 0 : options.duration || 4500;
  const progress = toast.querySelector(".toast__progress");
  if (progress) {
    if (duration > 0) progress.style.animationDuration = `${duration}ms`;
    else progress.remove();
  }

  const close = () => {
    toast.classList.add("toast--leaving");
    setTimeout(() => toast.remove(), 220);
  };
  toast.querySelector(".toast__close").addEventListener("click", close);
  root.appendChild(toast);

  if (duration > 0) {
    const timeout = setTimeout(close, duration);
    const pause = () => clearTimeout(timeout);
    toast.addEventListener("mouseenter", pause, { once: true });
    toast.addEventListener("focusin", pause, { once: true });
  }

  return toast;
}

export const notify = {
  success: (message, options) => show(message, "success", options),
  error: (message, options) => show(message, "error", options),
  warning: (message, options) => show(message, "warning", options),
  info: (message, options) => show(message, "info", options),
};
