import { requireAuth } from "./auth.js";
import { renderSidebar } from "../components/sidebar.js";
import { initTheme } from "./theme.js";

export async function initProtectedPage() {
  const admin = await requireAuth();
  renderSidebar(admin);
  initTheme(admin.theme);
  document.documentElement.classList.add("is-ready");
  return admin;
}

export function setupPolling(callback, intervalMs) {
  let timer = null;
  let running = false;
  let stopped = false;

  const run = async () => {
    if (running || stopped || document.hidden) return;
    running = true;
    try {
      await callback();
    } finally {
      running = false;
    }
  };

  run();
  timer = window.setInterval(run, intervalMs);

  const onVisibility = () => {
    if (!document.hidden) run();
  };
  document.addEventListener("visibilitychange", onVisibility);

  const stop = () => {
    stopped = true;
    window.clearInterval(timer);
    document.removeEventListener("visibilitychange", onVisibility);
  };

  window.addEventListener("beforeunload", stop, { once: true });
  return { stop, run };
}
