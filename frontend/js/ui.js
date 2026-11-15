const paths = {
  monitoring: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  orders: '<path d="M6 3h9l3 3v15H6z"/><path d="M9 10h6M9 14h6M9 18h4"/>',
  routes: '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8.5 6H15a3 3 0 0 1 0 6H9a3 3 0 0 0 0 6h6.5"/>',
  stores: '<path d="M4 9l1.5-5h13L20 9"/><path d="M5 9v11h14V9"/><path d="M9 20v-6h6v6"/><path d="M4 9h16"/>',
  trucks: '<path d="M3 7h10v9H3z"/><path d="M13 10h4l3 3v3h-7z"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
  drivers: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  map: '<path d="M9 4L3 6v15l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v15M15 6v15"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1.34-1.66 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6h.09A1.7 1.7 0 0 0 10 3.05V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9v.09a1.7 1.7 0 0 0 1.55 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1z"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  trash: '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v5M14 11v5"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
  alert: '<path d="M12 3L2 21h20z"/><path d="M12 9v5M12 18h.01"/>',
  temp: '<path d="M14 14.76V5a2 2 0 0 0-4 0v9.76a4 4 0 1 0 4 0z"/>',
  humidity: '<path d="M12 3c3.5 4.5 6 7.6 6 11a6 6 0 0 1-12 0c0-3.4 2.5-6.5 6-11z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  check: '<path d="M20 6L9 17l-5-5"/>',
  close: '<path d="M18 6L6 18M6 6l12 12"/>',
  chevron: '<path d="M9 18l6-6-6-6"/>',
  sync: '<path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 21v-5h5M21 3v5h-5"/>',
  play: '<path d="M8 5l11 7-11 7z"/>',
  location: '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0z"/><circle cx="12" cy="10" r="2.5"/>',
  box: '<path d="M21 8l-9-5-9 5v8l9 5 9-5z"/><path d="M3 8l9 5 9-5M12 13v8"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
  snow: '<path d="M12 2v20M4 7l16 10M20 7L4 17M9 4l3 3 3-3M9 20l3-3 3 3"/>',
  wallet: '<path d="M20 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0 0 4h15v4"/><path d="M3 7v12a2 2 0 0 0 2 2h15V11H5a2 2 0 0 1-2-2"/><path d="M17 15h.01"/>',
  trend: '<path d="M3 17l6-6 4 4 8-8"/><path d="M17 7h4v4"/>',
  layers: '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/><path d="M3 18l9 5 9-5"/>',
};

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

export function icon(name, size = 18) {
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true">${paths[name] || paths.box}</svg>`;
}

export function truckIcon(size = 19) {
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true">${paths.trucks}</svg>`;
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export function num(value, digits = 0) {
  return new Intl.NumberFormat("es-MX", { maximumFractionDigits: digits }).format(Number(value || 0));
}

export function currency(value, digits = 0) {
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: digits,
  }).format(Number(value || 0));
}

export function pct(value) {
  return `${Number(value || 0).toFixed(1)}%`;
}

export function dateTime(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("es-MX", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function dateOnly(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("es-MX", { month: "short", day: "numeric", year: "numeric" }).format(
    new Date(value),
  );
}

export function timeOnly(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("es-MX", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export function relative(value) {
  if (!value) return "—";
  const diff = Date.now() - new Date(value).getTime();
  const minutes = Math.round(diff / 60000);
  if (minutes < 1) return "ahora";
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  return `hace ${Math.round(hours / 24)} d`;
}

export const DAYS = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];

const ORDER_STATES = {
  PO: ["Pendiente", "blue"],
  LO: ["Atrasado", "yellow"],
  DO: ["Entregado", "green"],
  CO: ["Cancelado", "red"],
};
const TRUCK_STATES = {
  AV: ["Disponible", "green"],
  IR: ["En ruta", "blue"],
  IM: ["Mantenimiento", "yellow"],
  OS: ["Fuera de servicio", "red"],
};
const TRIP_STATES = { IP: ["En curso", "blue"], CP: ["Completado", "green"], CN: ["Cancelado", "red"] };
const ALERT_STATES = {
  HT: ["Temperatura alta", "red"],
  LT: ["Temperatura baja", "blue"],
  HH: ["Humedad alta", "yellow"],
  LH: ["Humedad baja", "blue"],
  OD: ["Puerta abierta", "red"],
};

export function stateBadge(kind, code, fallback) {
  const maps = { order: ORDER_STATES, truck: TRUCK_STATES, trip: TRIP_STATES, alert: ALERT_STATES };
  const entry = maps[kind]?.[code] || [fallback || code || "Desconocido", "gray"];
  return `<span class="badge ${entry[1]}">${escapeHtml(entry[0])}</span>`;
}

export function emptyState(title, message, iconName = "box", action = "") {
  return `<div class="empty">${icon(iconName, 28)}<strong>${escapeHtml(title)}</strong><span>${escapeHtml(message)}</span>${action}</div>`;
}

export function loadingState(message = "Cargando panel de trabajo") {
  return `<div class="card loading"><span class="spinner"></span>${escapeHtml(message)}</div>`;
}

export function toast(type = "blue", title = "", message = "") {
  const stack = $("#toast-stack");
  if (!stack) return;
  const node = document.createElement("div");
  node.className = `toast ${type}`;
  node.innerHTML = `<div><strong>${escapeHtml(title)}</strong>${message ? `<p>${escapeHtml(message)}</p>` : ""}</div><button aria-label="Cerrar">${icon("close", 14)}</button>`;
  const close = () => node.remove();
  node.querySelector("button").addEventListener("click", close);
  stack.appendChild(node);
  setTimeout(close, 5200);
}

export const success = (title, message) => toast("green", title, message);
export const info = (title, message) => toast("blue", title, message);
export const warning = (title, message) => toast("yellow", title, message);
export const error = (title, message) => toast("red", title, message);

export function openModal({ title, subtitle = "", body, footer = "", wide = false, onMount, onClose }) {
  const root = $("#modal-root");
  root.innerHTML = `
    <div class="modal-backdrop">
      <section class="modal ${wide ? "wide" : ""}" role="dialog" aria-modal="true" aria-label="${escapeHtml(title)}">
        <div class="modal-head">
          <div><h2>${escapeHtml(title)}</h2>${subtitle ? `<p>${escapeHtml(subtitle)}</p>` : ""}</div>
          <button class="icon-btn" data-close aria-label="Cerrar">${icon("close")}</button>
        </div>
        <div class="modal-body">${body}</div>
        ${footer ? `<div class="modal-foot">${footer}</div>` : ""}
      </section>
    </div>`;
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    root.innerHTML = "";
    document.removeEventListener("keydown", onKey);
    if (onClose) onClose();
  };
  const onKey = (event) => {
    if (event.key === "Escape") close();
  };
  root.querySelector("[data-close]").addEventListener("click", close);
  root.querySelector(".modal-backdrop").addEventListener("click", (event) => {
    if (event.target.classList.contains("modal-backdrop")) close();
  });
  document.addEventListener("keydown", onKey);
  if (onMount) onMount(root.querySelector(".modal"), close);
  return close;
}

export function confirmDialog({ title, message, confirmLabel = "Confirmar", danger = false }) {
  return new Promise((resolve) => {
    openModal({
      title,
      body: `<p class="muted" style="font-size:.88rem">${escapeHtml(message)}</p>`,
      footer: `<button class="btn" data-cancel>Cancelar</button><button class="btn ${danger ? "btn-danger" : "btn-primary"}" data-confirm>${escapeHtml(confirmLabel)}</button>`,
      onClose: () => resolve(false),
      onMount(modal, dismiss) {
        modal.querySelector("[data-cancel]").addEventListener("click", dismiss);
        modal.querySelector("[data-confirm]").addEventListener("click", () => {
          resolve(true);
          dismiss();
        });
      },
    });
  });
}

export function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("frostbase.theme", theme);
  const button = $("#theme-toggle");
  if (button) button.innerHTML = icon(theme === "dark" ? "sun" : "moon");
}

export function initTheme() {
  const stored = localStorage.getItem("frostbase.theme");
  applyTheme(stored || "dark");
}

export function toggleTheme() {
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
}

function smoothPath(points, tension = 0.19) {
  if (!points.length) return "";
  if (points.length === 1) return `M${points[0][0].toFixed(1)},${points[0][1].toFixed(1)}`;
  const commands = [`M${points[0][0].toFixed(1)},${points[0][1].toFixed(1)}`];
  for (let index = 0; index < points.length - 1; index += 1) {
    const p0 = points[index - 1] || points[index];
    const p1 = points[index];
    const p2 = points[index + 1];
    const p3 = points[index + 2] || p2;
    const cp1x = p1[0] + (p2[0] - p0[0]) * tension;
    const cp1y = p1[1] + (p2[1] - p0[1]) * tension;
    const cp2x = p2[0] - (p3[0] - p1[0]) * tension;
    const cp2y = p2[1] - (p3[1] - p1[1]) * tension;
    commands.push(
      `C${cp1x.toFixed(1)},${cp1y.toFixed(1)} ${cp2x.toFixed(1)},${cp2y.toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`,
    );
  }
  return commands.join(" ");
}

export function lineChart(trend = []) {
  if (!trend.length) {
    return emptyState("Sin datos de tendencia", "Las lecturas de temperatura y humedad aparecerán aquí.", "monitoring");
  }
  const width = 720;
  const height = 260;
  const pad = { top: 22, right: 18, bottom: 30, left: 40 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const temps = trend.map((point) => Number(point.temperature));
  const hums = trend.map((point) => Number(point.humidity));
  const tempMin = Math.min(...temps);
  const tempMax = Math.max(...temps);
  const humMin = Math.min(...hums);
  const humMax = Math.max(...hums);
  const x = (index) => pad.left + (trend.length === 1 ? innerW / 2 : (index / (trend.length - 1)) * innerW);
  const yTemp = (value) => pad.top + innerH - ((value - tempMin) / Math.max(tempMax - tempMin, 0.6)) * innerH;
  const yHum = (value) => pad.top + innerH - ((value - humMin) / Math.max(humMax - humMin, 1)) * innerH;
  const tempPoints = trend.map((point, index) => [x(index), yTemp(Number(point.temperature))]);
  const humPoints = trend.map((point, index) => [x(index), yHum(Number(point.humidity))]);
  const tempPath = smoothPath(tempPoints);
  const humPath = smoothPath(humPoints);
  const baseY = (pad.top + innerH).toFixed(1);
  const area = `${tempPath} L${x(trend.length - 1).toFixed(1)},${baseY} L${x(0).toFixed(1)},${baseY} Z`;
  const uid = `trend${Math.random().toString(36).slice(2, 7)}`;
  const grid = [0, 0.25, 0.5, 0.75, 1]
    .map((ratio) => `<line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${pad.top + innerH * ratio}" y2="${pad.top + innerH * ratio}"/>`)
    .join("");
  const labelIndexes = [...new Set([0, Math.floor((trend.length - 1) / 2), trend.length - 1])];
  const labels = labelIndexes
    .map((index) => `<text class="axis-text" x="${x(index)}" y="${height - 8}" text-anchor="${index === 0 ? "start" : index === trend.length - 1 ? "end" : "middle"}">${timeOnly(trend[index].time)}</text>`)
    .join("");
  const yLabels = [tempMax, (tempMax + tempMin) / 2, tempMin]
    .map((value, index) => `<text class="axis-text" x="4" y="${pad.top + (innerH * index) / 2 + 3}">${value.toFixed(1)}°</text>`)
    .join("");
  const tempDots = tempPoints
    .map((point) => `<circle class="dot-temp" cx="${point[0].toFixed(1)}" cy="${point[1].toFixed(1)}" r="2.6"/>`)
    .join("");
  return `
    <div class="chart">
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Tendencia de temperatura y humedad">
        <defs>
          <linearGradient id="${uid}-stroke" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="#22d3ee"/>
            <stop offset="50%" stop-color="#818cf8"/>
            <stop offset="100%" stop-color="#f472b6"/>
          </linearGradient>
          <linearGradient id="${uid}-hum" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="#f472b6"/>
            <stop offset="100%" stop-color="#a78bfa"/>
          </linearGradient>
          <linearGradient id="${uid}-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.42"/>
            <stop offset="55%" stop-color="#818cf8" stop-opacity="0.16"/>
            <stop offset="100%" stop-color="#818cf8" stop-opacity="0"/>
          </linearGradient>
        </defs>
        ${grid}${yLabels}${labels}
        <path d="${area}" fill="url(#${uid}-area)"/>
        <path d="${humPath}" fill="none" stroke="url(#${uid}-hum)" stroke-width="2.4" stroke-linecap="round" opacity="0.9"/>
        <path d="${tempPath}" fill="none" stroke="url(#${uid}-stroke)" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" filter="drop-shadow(0 8px 14px rgba(56,189,248,.45))"/>
        ${tempDots}
      </svg>
    </div>`;
}

export function progressMeter(label, value, total, tone = "") {
  const ratio = total ? Math.min(100, Math.round((value / total) * 100)) : 0;
  return `<div class="meter"><div class="meter-head"><span>${escapeHtml(label)}</span><strong>${num(value)}</strong></div><div class="progress ${tone}"><span style="width:${ratio}%"></span></div></div>`;
}

export function debounce(fn, wait = 250) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

export function formValues(form) {
  return Object.fromEntries(new FormData(form).entries());
}

export function todayInput() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}
