import { getMe, login } from "../core/auth.js";
import { notify } from "../core/notifications.js";
import { applyTheme, initTheme, toggleTheme } from "../core/theme.js";
import { qs, setButtonLoading } from "../core/helpers.js";

const form = qs("#loginForm");
const identifier = qs("#identifier");
const password = qs("#password");
const submitButton = qs("#loginButton");
const passwordToggle = qs("#passwordToggle");

function safeNext() {
  const next = new URLSearchParams(window.location.search).get("next");
  if (!next) return "dashboard.html";
  try {
    const target = new URL(next, window.location.href);
    if (target.origin !== window.location.origin) return "dashboard.html";
    return target.pathname.split("/").pop() + target.search;
  } catch (error) {
    return "dashboard.html";
  }
}

const brandLogo = qs(".login-brand__logo img");
brandLogo?.addEventListener("error", () => {
  brandLogo.style.display = "none";
  brandLogo.parentElement?.classList.add("login-brand__logo--placeholder");
});

initTheme();

qs("#themeToggle").addEventListener("click", () => toggleTheme(null));

getMe()
  .then(() => window.location.replace(safeNext()))
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
    setTimeout(() => window.location.replace(safeNext()), 250);
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
