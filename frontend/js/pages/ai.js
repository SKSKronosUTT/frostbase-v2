import { api } from "../core/api.js";
import { initProtectedPage, setupPolling } from "../core/app.js";
import { qs } from "../core/helpers.js";

const MAX_CHARS = 500;

const state = {
  conversationId: null,
  busy: false,
  online: false,
  enabled: false,
  quota: null,
  retryUntil: 0,
  retryTimer: null,
};

const chat = qs("#aiChat");
const empty = qs("#aiEmpty");
const typing = qs("#aiTyping");
const form = qs("#aiForm");
const input = qs("#aiMessage");
const sendButton = qs("#aiSend");
const counter = qs("#aiCount");
const statusChip = qs("#aiStatus");
const statusText = qs("#aiStatusText");
const newConversation = qs("#newConversation");
const notice = qs("#aiNotice");
const usageCount = qs("#aiUsageCount");
const usageHint = qs("#aiUsageHint");
const usageBar = qs("#aiUsageBar");
const usageBarWrap = qs("#aiUsageBarWrap");
const usageBlock = usageBarWrap.closest(".ai-usage__block");
const usageErrors = qs("#aiUsageErrors");
const usageRequests = qs("#aiUsageRequests");
const usageLatency = qs("#aiUsageLatency");
const usagePull = qs("#aiUsagePull");
const usageBoot = qs("#aiUsageBoot");

// ===== Render seguro (sin innerHTML con datos) =====

function appendInline(parent, text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  for (const part of parts) {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      const strong = document.createElement("strong");
      strong.textContent = part.slice(2, -2);
      parent.appendChild(strong);
    } else if (part) {
      parent.appendChild(document.createTextNode(part));
    }
  }
}

function appendText(container, text) {
  const lines = String(text || "").split(/\r?\n/);
  for (const line of lines) {
    const row = document.createElement("div");
    row.className = "ai-message__line";
    if (line.startsWith("- ")) {
      row.classList.add("ai-message__line--bullet");
      appendInline(row, line.slice(2));
    } else {
      appendInline(row, line);
    }
    container.appendChild(row);
  }
}

function appendMessage(role, text, { error = false, label = null } = {}) {
  empty.hidden = true;
  const wrapper = document.createElement("article");
  wrapper.className = `ai-message ai-message--${role}${error ? " ai-message--error" : ""}`;

  const bubble = document.createElement("div");
  bubble.className = "ai-message__bubble";
  appendText(bubble, text);

  const meta = document.createElement("span");
  meta.className = "ai-message__meta";
  meta.textContent =
    label || (role === "user" ? "Tú" : error ? "Sistema" : "Asistente FrostBase");

  wrapper.appendChild(bubble);
  wrapper.appendChild(meta);
  chat.insertBefore(wrapper, typing);
  chat.scrollTop = chat.scrollHeight;
}

function quotaExhausted() {
  return Boolean(state.quota && state.quota.remaining <= 0);
}

function retryBlocked() {
  return state.retryUntil > Date.now();
}

function updateSendState() {
  sendButton.disabled = state.busy || quotaExhausted() || retryBlocked();
  sendButton.classList.toggle("is-loading", state.busy);
}

function setBusy(busy) {
  state.busy = busy;
  typing.hidden = !busy;
  updateSendState();
  if (busy) chat.scrollTop = chat.scrollHeight;
}

function updateCounter() {
  counter.textContent = `${input.value.length}/${MAX_CHARS}`;
}

function setStatus({ enabled, online }) {
  state.enabled = enabled;
  state.online = online;
  statusChip.classList.remove("ai-status--checking");
  if (!enabled) {
    statusChip.classList.add("ai-status--offline");
    statusText.textContent = "Asistente deshabilitado";
    return;
  }
  if (online) {
    statusChip.classList.add("ai-status--online");
    statusChip.classList.remove("ai-status--offline");
    statusText.textContent = "Agente en línea";
  } else {
    statusChip.classList.add("ai-status--offline");
    statusChip.classList.remove("ai-status--online");
    statusText.textContent = "Agente no disponible";
  }
}

function showNotice(text) {
  notice.textContent = text || "";
  notice.hidden = !text;
}

function formatMs(value) {
  return Number.isFinite(value) ? `${Math.round(value)} ms` : "—";
}

function formatRelative(iso) {
  if (!iso) return "Sin lecturas";
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "—";
  const minutes = Math.floor(Math.max(0, Date.now() - at.getTime()) / 60000);
  if (minutes < 1) return "Hace segundos";
  if (minutes < 60) return `Hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `Hace ${hours} h`;
  return `Hace ${Math.floor(hours / 24)} d`;
}

function renderUsage(usage) {
  state.quota = usage;
  usageCount.textContent = `${usage.used}/${usage.limit}`;
  const ratio = usage.limit > 0 ? usage.used / usage.limit : 0;
  const percent = Math.min(100, Math.round(ratio * 100));
  usageBar.style.width = `${percent}%`;
  usageBarWrap.setAttribute("aria-valuenow", String(percent));
  usageBlock.classList.toggle("ai-usage__block--danger", usage.remaining <= 0);
  usageBlock.classList.toggle(
    "ai-usage__block--warn",
    usage.remaining > 0 && ratio >= 0.9
  );
  if (usage.remaining <= 0) {
    usageHint.textContent = "Sin consultas disponibles";
  } else if (ratio >= 0.9) {
    usageHint.textContent = `Te quedan ${usage.remaining}`;
  } else {
    usageHint.textContent = `${usage.remaining} disponibles`;
  }

  if (retryBlocked() || state.busy) {
    updateSendState();
    return;
  }
  if (usage.remaining <= 0) {
    showNotice(
      "Se agotó la cuota diaria del asistente. Se reinicia a medianoche (hora de Tijuana)."
    );
  } else if (ratio >= 0.9) {
    showNotice(`Te quedan ${usage.remaining} consultas hoy.`);
  } else {
    showNotice("");
  }
  updateSendState();
}

function renderMetrics(metrics) {
  usageErrors.textContent = String(metrics.errors ?? 0);
  usageRequests.textContent = `${metrics.requests ?? 0} eventos · ${
    metrics.by_action?.chat ?? 0
  } consultas`;
  const p50 = metrics.latency_p50_ms ?? null;
  const p95 = metrics.latency_p95_ms ?? null;
  usageLatency.textContent =
    p50 === null && p95 === null ? "—" : `${formatMs(p50)} / ${formatMs(p95)}`;
}

function renderPull(status) {
  usagePull.textContent = formatRelative(status.last_agent_read_at);
  if (!status.enabled) {
    usageBoot.textContent = "Asistente deshabilitado";
  } else if (status.boot_id) {
    usageBoot.textContent = `boot ${String(status.boot_id).slice(0, 8)}`;
  } else {
    usageBoot.textContent = "Sin conexión";
  }
}

function startRetryCountdown(seconds, reason) {
  const until = Date.now() + Math.max(1, Math.ceil(seconds)) * 1000;
  state.retryUntil = until;
  if (state.retryTimer) window.clearInterval(state.retryTimer);
  const tick = () => {
    const left = Math.ceil((until - Date.now()) / 1000);
    if (left <= 0) {
      state.retryUntil = 0;
      window.clearInterval(state.retryTimer);
      state.retryTimer = null;
      showNotice("");
      updateSendState();
      refreshUsage();
      return;
    }
    showNotice(`${reason} Reintenta en ${left} s.`);
    updateSendState();
  };
  tick();
  state.retryTimer = window.setInterval(tick, 1000);
}

function errorMessage(error) {
  if (error?.status === 429 && error?.message?.includes("límite diario")) {
    return "Se alcanzó el límite diario de consultas. Intenta de nuevo mañana.";
  }
  if (error?.status === 429) {
    return "El agente está atendiendo otra consulta. Espera unos segundos e intenta de nuevo.";
  }
  if (error?.status === 503) {
    return "El agente no está disponible en este momento. Revisa la conexión con el ESP32.";
  }
  if (error?.status === 504) {
    return "El agente tardó demasiado en responder. Intenta de nuevo.";
  }
  if (error?.status === 404) {
    return "El asistente está deshabilitado en este servidor.";
  }
  return error?.message || "No se pudo obtener respuesta del asistente.";
}

async function sendMessage(text) {
  const message = text.trim();
  if (!message || state.busy || quotaExhausted() || retryBlocked()) return;
  if (message.length > MAX_CHARS) {
    appendMessage("system", `El mensaje supera ${MAX_CHARS} caracteres.`, {
      error: true,
    });
    return;
  }

  appendMessage("user", message);
  input.value = "";
  updateCounter();
  setBusy(true);

  try {
    const payload = { message };
    if (state.conversationId) payload.conversation_id = state.conversationId;
    // El agente puede tardar hasta AI_AGENT_TIMEOUT_SECONDS (90 s).
    const response = await api.post("/ai/chat", payload, { timeout: 95000 });
    state.conversationId = response.conversation_id;
    appendMessage("assistant", response.reply || "(sin contenido)");
    refreshUsage();
  } catch (error) {
    appendMessage("system", errorMessage(error), { error: true });
    if (error?.status === 429 && error?.message?.includes("límite diario")) {
      if (state.quota) {
        state.quota = {
          ...state.quota,
          used: state.quota.limit,
          remaining: 0,
        };
        renderUsage(state.quota);
      }
      startRetryCountdown(error.retryAfter || 3600, "Cuota diaria agotada.");
    } else if (error?.status === 429) {
      startRetryCountdown(error.retryAfter || 3, "El agente está ocupado.");
    } else if (error?.status === 503) {
      setStatus({ enabled: true, online: false });
      startRetryCountdown(error.retryAfter || 30, "El agente no está disponible.");
    }
  } finally {
    setBusy(false);
    input.focus();
  }
}

async function refreshStatus() {
  try {
    const status = await api.get("/ai/status");
    setStatus(status);
    renderPull(status);
  } catch {
    setStatus({ enabled: true, online: false });
  }
}

async function refreshUsage() {
  const [usage, metrics] = await Promise.allSettled([
    api.get("/ai/usage"),
    api.get("/ai/metrics?days=1"),
  ]);
  if (usage.status === "fulfilled") {
    renderUsage(usage.value);
  }
  if (metrics.status === "fulfilled") {
    renderMetrics(metrics.value);
  }
}

async function resetConversation() {
  const previous = state.conversationId;
  state.conversationId = null;
  chat.querySelectorAll(".ai-message").forEach((node) => node.remove());
  empty.hidden = false;
  input.value = "";
  updateCounter();
  if (previous) {
    try {
      await api.delete(`/ai/conversations/${previous}`);
    } catch {
      // El cierre es best-effort: la conversación local ya se reinició.
    }
  }
  input.focus();
}

async function runQuick(quickId) {
  if (state.busy) return;
  setBusy(true);
  try {
    const quick = await api.post(`/ai/quick/${quickId}`);
    appendMessage("user", quick.title || "Consulta rápida");
    appendMessage("assistant", quick.text || "(sin datos)", {
      label: "Datos del sistema",
    });
  } catch (error) {
    appendMessage("system", errorMessage(error), { error: true });
  } finally {
    setBusy(false);
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(input.value);
});

input.addEventListener("input", updateCounter);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage(input.value);
  }
});

document.querySelectorAll("[data-quick]").forEach((button) => {
  button.addEventListener("click", () => runQuick(button.dataset.quick || ""));
});

newConversation.addEventListener("click", resetConversation);

async function init() {
  await initProtectedPage();
  updateCounter();
  input.focus();
  await Promise.all([refreshStatus(), refreshUsage()]);
  setupPolling(() => {
    refreshStatus();
    refreshUsage();
  }, 30000);
}

init();
