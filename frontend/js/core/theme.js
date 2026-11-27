import { api } from "./api.js";

const STORAGE_KEY = "frostbase-theme";
const VALID_THEMES = ["light", "dark"];
const DARK_QUERY = "(prefers-color-scheme: dark)";

function normalize(theme) {
  return VALID_THEMES.includes(theme) ? theme : null;
}

function systemTheme() {
  return window.matchMedia?.(DARK_QUERY)?.matches ? "dark" : "light";
}

export function resolveTheme(adminTheme) {
  const stored = normalize(localStorage.getItem(STORAGE_KEY));
  if (stored) return stored;
  return normalize(adminTheme) || systemTheme();
}

export function applyTheme(theme, { persist = true } = {}) {
  const normalized = normalize(theme) || systemTheme();
  document.documentElement.dataset.theme = normalized;
  if (persist) localStorage.setItem(STORAGE_KEY, normalized);
  updateToggle(normalized);
}

function updateToggle(theme) {
  const button = document.getElementById("themeToggle");
  if (!button) return;
  const icon = button.querySelector("i");
  const label = button.querySelector("span");
  const isDark = theme === "dark";
  if (icon) icon.className = isDark ? "fa-solid fa-sun" : "fa-solid fa-moon";
  if (label) label.textContent = isDark ? "Tema claro" : "Tema oscuro";
  button.setAttribute(
    "aria-label",
    isDark ? "Cambiar a tema claro" : "Cambiar a tema oscuro"
  );
}

export function initTheme(adminTheme) {
  const stored = normalize(localStorage.getItem(STORAGE_KEY));
  const admin = normalize(adminTheme);
  applyTheme(stored || admin || systemTheme(), { persist: false });

  // Sin preferencia explícita, sigue los cambios del sistema operativo.
  if (!stored && !admin && window.matchMedia) {
    const media = window.matchMedia(DARK_QUERY);
    const onChange = (event) => {
      if (normalize(localStorage.getItem(STORAGE_KEY))) return;
      applyTheme(event.matches ? "dark" : "light", { persist: false });
    };
    if (media.addEventListener) media.addEventListener("change", onChange);
    else media.addListener?.(onChange);
  }
}

export function toggleTheme(admin) {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  applyTheme(next);
  if (admin) {
    api.put("/auth/preferences", { theme: next }).catch(() => {
      /* La preferencia local se mantiene aunque falle la persistencia */
    });
  }
  window.dispatchEvent(new CustomEvent("frostbase:theme", { detail: next }));
}
