import { api } from "./api.js";
import { logout, requireAuth } from "./auth.js";
import { renderSidebar } from "../components/sidebar.js";
import { initTheme } from "./theme.js";
import { qs, setButtonLoading } from "./helpers.js";
import { notify } from "./notifications.js";
import { activateModal } from "../components/modal.js";

const MIN_PASSWORD_LENGTH = 12;

function buildPasswordModal(mandatory) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.id = "passwordChangeOverlay";
  overlay.innerHTML = `
    <div class="modal modal--sm" role="dialog" aria-modal="true" aria-labelledby="passwordChangeTitle">
      <div class="modal__header">
        <h2 id="passwordChangeTitle">Cambiar contraseña</h2>
        ${
          mandatory
            ? ""
            : `<button class="icon-button modal__close" id="passwordChangeClose" type="button" aria-label="Cerrar">
                 <i class="fa-solid fa-xmark"></i>
               </button>`
        }
      </div>
      <form class="modal__body" id="passwordChangeForm" novalidate>
        <p class="muted">
          ${
            mandatory
              ? "Por seguridad debes definir una nueva contraseña antes de continuar."
              : "La nueva contraseña debe tener al menos 12 caracteres y no contener tu usuario."
          }
        </p>
        <div class="form-field">
          <label for="currentPassword">Contraseña actual</label>
          <input class="input" id="currentPassword" type="password"
                 autocomplete="current-password" required />
        </div>
        <div class="form-field">
          <label for="newPassword">Nueva contraseña</label>
          <input class="input" id="newPassword" type="password"
                 autocomplete="new-password" minlength="${MIN_PASSWORD_LENGTH}" required />
        </div>
        <div class="form-field">
          <label for="confirmPassword">Confirmar nueva contraseña</label>
          <input class="input" id="confirmPassword" type="password"
                 autocomplete="new-password" minlength="${MIN_PASSWORD_LENGTH}" required />
        </div>
      </form>
      <div class="modal__footer modal__footer--spread">
        ${
          mandatory
            ? `<button class="btn btn--ghost" id="passwordChangeLogout" type="button">Cerrar sesión</button>`
            : `<button class="btn btn--ghost" id="passwordChangeCancel" type="button">Cancelar</button>`
        }
        <button class="btn btn--primary" id="passwordChangeSubmit" type="submit" form="passwordChangeForm">
          Guardar contraseña
        </button>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);
  document.body.classList.add("modal-open");

  const form = qs("#passwordChangeForm", overlay);
  const submit = qs("#passwordChangeSubmit", overlay);
  let deactivate = () => {};

  const close = ({ force = false } = {}) => {
    if (mandatory && !force) return;
    document.body.classList.remove("modal-open");
    overlay.classList.add("modal-overlay--leaving");
    deactivate();
    setTimeout(() => overlay.remove(), 160);
  };

  deactivate = activateModal(overlay, {
    onClose: () => close(),
    closeOnBackdrop: !mandatory,
  });

  qs("#passwordChangeClose", overlay)?.addEventListener("click", () => close());
  qs("#passwordChangeCancel", overlay)?.addEventListener("click", () => close());
  qs("#passwordChangeLogout", overlay)?.addEventListener("click", () => logout());

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const currentPassword = qs("#currentPassword", overlay).value;
    const newPassword = qs("#newPassword", overlay).value;
    const confirmPassword = qs("#confirmPassword", overlay).value;

    if (!currentPassword || !newPassword) {
      notify.warning("Completa ambos campos de contraseña.");
      return;
    }
    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      notify.warning(
        `La nueva contraseña debe tener al menos ${MIN_PASSWORD_LENGTH} caracteres.`
      );
      return;
    }
    if (newPassword !== confirmPassword) {
      notify.warning("La confirmación no coincide con la nueva contraseña.");
      return;
    }

    setButtonLoading(submit, true, "Guardando…");
    try {
      await api.post("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      notify.success("Contraseña actualizada. Vuelve a iniciar sesión.");
      close({ force: true });
      window.setTimeout(() => window.location.reload(), 600);
    } catch (error) {
      notify.error(error.message, { title: "No se pudo cambiar la contraseña" });
    } finally {
      setButtonLoading(submit, false);
    }
  });

  setTimeout(() => qs("#currentPassword", overlay)?.focus(), 30);
}
export function openPasswordChangeModal({ mandatory = false } = {}) {
  if (document.getElementById("passwordChangeOverlay")) return;
  buildPasswordModal(mandatory);
}

export function setupConnectionBadge() {
  const badge = document.getElementById("connectionBadge");
  const label = document.getElementById("connectionText");
  if (!badge) return;

  const apply = (online) => {
    badge.classList.toggle("live-indicator--offline", !online);
    badge.classList.toggle("live-indicator--online", online);
    if (label) label.textContent = online ? "En vivo" : "Sin conexión";
    badge.setAttribute(
      "aria-label",
      online ? "Conexión activa con el servidor" : "Sin conexión con el servidor"
    );
  };

  apply(navigator.onLine);
  window.addEventListener("frostbase:connection", (event) =>
    apply(event.detail.online)
  );
  window.addEventListener("online", () => apply(true));
  window.addEventListener("offline", () => apply(false));
}

export async function initProtectedPage() {
  const admin = await requireAuth();
  renderSidebar(admin);
  initTheme(admin.theme);
  setupConnectionBadge();
  document.documentElement.classList.add("is-ready");
  if (admin.must_change_password) {
    openPasswordChangeModal({ mandatory: true });
  }
  return admin;
}

export function setupPolling(callback, intervalMs) {
  let timer = null;
  let running = false;
  let stopped = false;
  let failures = 0;
  let delay = intervalMs;

  const schedule = (nextDelay) => {
    window.clearTimeout(timer);
    if (!stopped) timer = window.setTimeout(run, nextDelay);
  };

  const run = async () => {
    if (stopped || running) return;
    if (document.hidden) {
      schedule(intervalMs);
      return;
    }
    running = true;
    try {
      await callback();
      failures = 0;
      delay = intervalMs;
    } catch (error) {
      if (!error?.cancelled) {
        failures += 1;
        delay = Math.min(intervalMs * 2 ** failures, 60000);
      } else {
        delay = intervalMs;
      }
    } finally {
      running = false;
      schedule(delay);
    }
  };

  run();

  const onVisibility = () => {
    if (!document.hidden) run();
  };
  document.addEventListener("visibilitychange", onVisibility);

  const stop = () => {
    stopped = true;
    window.clearTimeout(timer);
    document.removeEventListener("visibilitychange", onVisibility);
  };

  window.addEventListener("beforeunload", stop, { once: true });
  return { stop, run };
}
