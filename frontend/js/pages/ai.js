import { api } from "../core/api.js";
import { initProtectedPage, setupPolling } from "../core/app.js";
import { qs } from "../core/helpers.js";

const MAX_CHARS = 500;

const state = {
  conversationId: null,
  busy: false,
  online: false,
  enabled: false,
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

function setBusy(busy) {
  state.busy = busy;
  typing.hidden = !busy;
  sendButton.disabled = busy;
  sendButton.classList.toggle("is-loading", busy);
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
  if (!message || state.busy) return;
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
    const response = await api.post("/ai/chat", payload);
    state.conversationId = response.conversation_id;
    appendMessage("assistant", response.reply || "(sin contenido)");
  } catch (error) {
    appendMessage("system", errorMessage(error), { error: true });
    if (error?.status === 503) setStatus({ enabled: true, online: false });
  } finally {
    setBusy(false);
    input.focus();
  }
}

async function refreshStatus() {
  try {
    const status = await api.get("/ai/status");
    setStatus(status);
  } catch {
    setStatus({ enabled: true, online: false });
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
  await refreshStatus();
  setupPolling(refreshStatus, 30000);
}

init();
