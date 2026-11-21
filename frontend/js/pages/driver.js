import { api } from "../core/api.js";
import { logout } from "../core/auth.js";
import { openPasswordChangeModal } from "../core/app.js";
import { notify } from "../core/notifications.js";
import { initTheme, toggleTheme } from "../core/theme.js";
import { escapeHtml, qs } from "../core/helpers.js";

initTheme();

qs("#themeToggle").addEventListener("click", () => toggleTheme(null));
qs("#logoutButton").addEventListener("click", logout);
qs("#changePasswordButton").addEventListener("click", () =>
  openPasswordChangeModal({ mandatory: false })
);

async function init() {
  try {
    const me = await api.get("/driver/me");
    qs("#driverName").textContent = `${me.first_name} ${me.last_name}`;
    qs("#driverEmail").textContent = me.email;
    qs("#driverPhone").textContent = me.phone;
    qs("#driverTruck").textContent = me.truck
      ? `${me.truck.plate}`
      : "Sin camión asignado";

    if (me.must_change_password) {
      openPasswordChangeModal({ mandatory: true });
    }
  } catch (error) {
    if (error.status === 401) {
      window.location.replace("login.html");
      return;
    }
    notify.error(error.message || "No se pudo cargar el perfil del conductor.");
    qs("#driverEmail").innerHTML = escapeHtml("Sin sesión válida");
  }
}

init();
