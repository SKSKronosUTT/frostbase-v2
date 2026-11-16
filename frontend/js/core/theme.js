import { api } from "./api.js";

const STORAGE_KEY = "frostbase-theme";
const VALID_THEMES = ["light", "dark"];

function normalize(theme) {
  return VALID_THEMES.includes(theme) ? theme : null;
}

export function resolveTheme(adminTheme) {
  const stored = normalize(localStorage.getItem(STORAGE_KEY));
  if (stored) return stored;
  return normalize(adminTheme) || "light";
}

export function applyTheme(theme) {
  const normalized = normalize(theme) || "light";
  document.documentElement.dataset.theme = normalized;
  localStorage.setItem(STORAGE_KEY, normalized);
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
  button.setAttribute("aria-label", isDark ? "Cambiar a tema claro" : "Cambiar a tema oscuro");
}

export function initTheme(adminTheme) {
  applyTheme(resolveTheme(adminTheme));
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
