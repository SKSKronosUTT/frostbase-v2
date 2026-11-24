import { api } from "../core/api.js";
import { initProtectedPage, setupPolling } from "../core/app.js";
import { qs } from "../core/helpers.js";

const MAX_CHARS = 500;
const MAX_TITLE = 60;
const STORAGE_KEY = "frostbase.ai.conversation";

const state = {
  conversationId: null,
  conversations: [],
  renamingId: null,
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
const typingText = qs("#aiTypingText");
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
const conversationList = qs("#aiConversationList");
const conversationEmpty = qs("#aiConversationEmpty");
const refreshConversationsButton = qs("#refreshConversations");

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

// ===== Historial de conversaciones (B3) =====

function persistConversation(id) {
  try {
    if (id) window.localStorage.setItem(STORAGE_KEY, id);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Sin almacenamiento (modo privado): la conversación dura lo que la página.
  }
}

function rememberConversation(id) {
  state.conversationId = id;
  persistConversation(id);
}

function conversationLabel(conversation) {
  if (conversation.title) return conversation.title;
  const date = new Date(conversation.last_used_at);
  if (Number.isNaN(date.getTime())) return "Conversación sin título";
  return `Conversación del ${date.toLocaleString("es-MX", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

function iconButton(iconClass, label, extraClass = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `ai-history__action${extraClass ? ` ${extraClass}` : ""}`;
  button.setAttribute("aria-label", label);
  button.title = label;
  const icon = document.createElement("i");
  icon.className = iconClass;
  icon.setAttribute("aria-hidden", "true");
  button.appendChild(icon);
  return button;
}

function buildRenameForm(conversation) {
  const form = document.createElement("form");
  form.className = "ai-history__rename";
  const input = document.createElement("input");
  input.type = "text";
  input.value = conversation.title || "";
  input.maxLength = MAX_TITLE;
  input.required = true;
  input.setAttribute("aria-label", "Nuevo título de la conversación");
  input.addEventListener("input", () => input.setCustomValidity(""));

  const save = iconButton("fa-solid fa-check", "Guardar título");
  save.type = "submit";
  const cancel = iconButton("fa-solid fa-xmark", "Cancelar");
  cancel.addEventListener("click", () => {
    state.renamingId = null;
    renderConversations();
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!input.value.trim()) {
      input.setCustomValidity("El título no puede estar vacío");
      input.reportValidity();
      return;
    }
    renameConversation(conversation, input.value);
  });

  form.append(input, save, cancel);
  window.setTimeout(() => {
    input.focus();
    input.select();
  }, 0);
  return form;
}

function renderConversations() {
  conversationList.replaceChildren();
  conversationEmpty.hidden = state.conversations.length > 0;

  for (const conversation of state.conversations) {
    const item = document.createElement("div");
    item.className = "ai-history__item";
    item.setAttribute("role", "listitem");
    if (conversation.id === state.conversationId) {
      item.classList.add("is-active");
    }

    if (state.renamingId === conversation.id) {
      item.appendChild(buildRenameForm(conversation));
    } else {
      const label = conversationLabel(conversation);
      const open = document.createElement("button");
      open.type = "button";
      open.className = "ai-history__open";
      open.setAttribute("aria-label", `Abrir ${label}`);

      const title = document.createElement("span");
      title.className = "ai-history__title";
      title.textContent = label;
      const count = conversation.last_seq || 0;
      const meta = document.createElement("span");
      meta.className = "ai-history__meta";
      meta.textContent = `${formatRelative(conversation.last_used_at)} · ${count} ${
        count === 1 ? "mensaje" : "mensajes"
      }`;
      open.append(title, meta);
      open.addEventListener("click", () => loadConversation(conversation.id));

      const actions = document.createElement("div");
      actions.className = "ai-history__actions";
      const rename = iconButton("fa-solid fa-pen", "Renombrar conversación");
      rename.addEventListener("click", () => {
        state.renamingId = conversation.id;
        renderConversations();
      });
      const remove = iconButton(
        "fa-solid fa-trash",
        "Eliminar conversación",
        "ai-history__action--danger"
      );
      remove.addEventListener("click", () => deleteConversation(conversation));
      actions.append(rename, remove);
      item.append(open, actions);
    }

    conversationList.appendChild(item);
  }
}

async function refreshConversations() {
  try {
    const items = await api.get("/ai/conversations?limit=20");
    state.conversations = Array.isArray(items) ? items : [];
    renderConversations();
  } catch {
    // La lista es auxiliar: el chat sigue funcionando sin ella.
  }
}

function clearChatView() {
  rememberConversation(null);
  chat.querySelectorAll(".ai-message").forEach((node) => node.remove());
  empty.hidden = false;
  input.value = "";
  updateCounter();
  renderConversations();
}

async function loadConversation(id) {
  if (!id || state.busy) return;
  setBusy(true, "Cargando conversación…");
  try {
    const history = await api.get(`/ai/conversations/${id}/messages?limit=50`);
    rememberConversation(id);
    state.renamingId = null;
    chat.querySelectorAll(".ai-message").forEach((node) => node.remove());
    const messages = Array.isArray(history.messages) ? history.messages : [];
    for (const message of messages) {
      const role = message.role === "user" ? "user" : "assistant";
      appendMessage(role, message.text || "(sin contenido)", {
        label: message.role === "system" ? "Agente" : undefined,
      });
    }
    empty.hidden = messages.length > 0;
    renderConversations();
    chat.scrollTop = chat.scrollHeight;
  } catch (error) {
    if (error?.status === 404 || error?.status === 422) {
      clearChatView();
      appendMessage("system", "La conversación ya no está disponible en el agente.", {
        error: true,
      });
      refreshConversations();
    } else {
      appendMessage("system", errorMessage(error), { error: true });
    }
  } finally {
    setBusy(false);
  }
}

async function renameConversation(conversation, value) {
  const title = String(value || "").trim();
  if (!title) return;
  try {
    const updated = await api.patch(`/ai/conversations/${conversation.id}`, {
      title,
    });
    state.conversations = state.conversations.map((item) =>
      item.id === conversation.id ? updated : item
    );
    state.renamingId = null;
    renderConversations();
  } catch (error) {
    appendMessage("system", errorMessage(error), { error: true });
  }
}

async function deleteConversation(conversation) {
  const label = conversationLabel(conversation);
  if (!window.confirm(`¿Eliminar «${label}» y su historial?`)) return;
  try {
    await api.delete(`/ai/conversations/${conversation.id}`);
    state.conversations = state.conversations.filter(
      (item) => item.id !== conversation.id
    );
    if (state.conversationId === conversation.id) {
      clearChatView();
    } else {
      renderConversations();
    }
  } catch (error) {
    appendMessage("system", errorMessage(error), { error: true });
  }
}

function storedConversationId() {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

async function restoreConversation() {
  const id = storedConversationId();
  if (!id) return;
  await loadConversation(id);
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

function setBusy(busy, message = "El agente está escribiendo…") {
  state.busy = busy;
  typing.hidden = !busy;
  typingText.textContent = message;
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
    rememberConversation(response.conversation_id);
    appendMessage("assistant", response.reply || "(sin contenido)");
    refreshUsage();
    refreshConversations();
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
  clearChatView();
  if (previous) {
    try {
      await api.delete(`/ai/conversations/${previous}`);
      state.conversations = state.conversations.filter((item) => item.id !== previous);
    } catch {
      // El cierre es best-effort: la conversación local ya se reinició.
    }
    renderConversations();
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
refreshConversationsButton.addEventListener("click", refreshConversations);

async function init() {
  await initProtectedPage();
  updateCounter();
  input.focus();
  await Promise.all([refreshStatus(), refreshUsage(), refreshConversations()]);
  await restoreConversation();
  setupPolling(() => {
    refreshStatus();
    refreshUsage();
  }, 30000);
}

init();
