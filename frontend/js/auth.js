import { api, getToken, setSession } from "./api.js";
import { applyTheme, icon } from "./ui.js";

applyTheme(localStorage.getItem("frostbase.theme") || "dark");

const form = document.getElementById("login-form");
const email = document.getElementById("login-email");
const password = document.getElementById("login-password");
const submit = document.getElementById("login-submit");
const errorBox = document.getElementById("login-error");
const demoButton = document.getElementById("demo-fill");

document.querySelectorAll(".brand-mark img, .mobile-brand img").forEach((img) => {
  img.dataset.loaded = "true";
});

if (getToken()) {
  window.location.replace("app.html");
}

demoButton.addEventListener("click", () => {
  email.value = "mgonzalez@logisticarf.com";
  password.value = "admin123";
  errorBox.textContent = "";
  email.focus();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.textContent = "";
  if (!email.value.trim() || !password.value) {
    errorBox.textContent = "Ingresa tu correo y contraseña para continuar.";
    return;
  }
  submit.disabled = true;
  submit.innerHTML = `<span class="spinner"></span>Iniciando sesión`;
  try {
    const user = await api("/auth/login", {
      method: "POST",
      body: { email: email.value.trim(), password: password.value },
    });
    const { token, ...profile } = user;
    setSession(token, profile, true);
    window.location.replace("app.html");
  } catch (error) {
    errorBox.textContent = error.message || "No se pudo iniciar sesión.";
    submit.disabled = false;
    submit.innerHTML = "Iniciar sesión";
    password.select();
  }
});

[email, password].forEach((input) => input.addEventListener("input", () => (errorBox.textContent = "")));

const themeButton = document.createElement("button");
themeButton.className = "icon-btn";
themeButton.style.position = "fixed";
themeButton.style.top = "22px";
themeButton.style.right = "22px";
themeButton.style.zIndex = "5";
themeButton.setAttribute("aria-label", "Cambiar tema");
themeButton.innerHTML = icon(document.documentElement.dataset.theme === "dark" ? "sun" : "moon");
themeButton.addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  applyTheme(next);
  themeButton.innerHTML = icon(next === "dark" ? "sun" : "moon");
});
document.body.appendChild(themeButton);

window.addEventListener("pageshow", () => {
  if (getToken()) window.location.replace("app.html");
});
