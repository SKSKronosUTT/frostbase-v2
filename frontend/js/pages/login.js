import { getMe, login } from "../core/auth.js";
import { notify } from "../core/notifications.js";
import { applyTheme, initTheme, toggleTheme } from "../core/theme.js";
import { qs, setButtonLoading } from "../core/helpers.js";

const form = qs("#loginForm");
const identifier = qs("#identifier");
const password = qs("#password");
const submitButton = qs("#loginButton");
const passwordToggle = qs("#passwordToggle");

initTheme();

qs("#themeToggle").addEventListener("click", () => toggleTheme(null));

getMe()
  .then(() => window.location.replace("dashboard.html"))
  .catch(() => {});

passwordToggle.addEventListener("click", () => {
  const isPassword = password.type === "password";
  password.type = isPassword ? "text" : "password";
  passwordToggle.innerHTML = `<i class="fa-solid ${isPassword ? "fa-eye-slash" : "fa-eye"}"></i>`;
  passwordToggle.setAttribute(
    "aria-label",
    isPassword ? "Ocultar contraseña" : "Mostrar contraseña"
  );
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const user = identifier.value.trim();
  const secret = password.value;

  if (!user || !secret) {
    notify.warning("Ingresa tu usuario o correo y tu contraseña.");
    (user ? password : identifier).focus();
    return;
  }

  setButtonLoading(submitButton, true, "Verificando…");
  try {
    await login(user, secret);
    notify.success("Sesión iniciada correctamente.");
    setTimeout(() => window.location.replace("dashboard.html"), 250);
  } catch (error) {
    notify.error(error.message || "No se pudo iniciar sesión.");
    password.focus();
    password.select();
  } finally {
    setButtonLoading(submitButton, false);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    applyTheme(document.documentElement.dataset.theme);
  }
});
