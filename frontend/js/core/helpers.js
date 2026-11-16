export function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function qs(selector, root = document) {
  return root.querySelector(selector);
}

export function qsa(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

const dateTimeFormatter = new Intl.DateTimeFormat("es-MX", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const dateFormatter = new Intl.DateTimeFormat("es-MX", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const timeFormatter = new Intl.DateTimeFormat("es-MX", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

function toDate(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateTime(value) {
  const date = toDate(value);
  return date ? dateTimeFormatter.format(date) : "—";
}

export function formatDate(value) {
  const date = toDate(value);
  return date ? dateFormatter.format(date) : "—";
}

export function formatTime(value) {
  const date = toDate(value);
  return date ? timeFormatter.format(date) : "—";
}

export function timeAgo(value) {
  const date = toDate(value);
  if (!date) return "—";
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 5) return "hace unos segundos";
  if (seconds < 60) return `hace ${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `hace ${days} d`;
  return formatDate(date);
}

export function formatTemp(value, withUnit = true) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return `${Number(value).toFixed(1)}${withUnit ? " °C" : ""}`;
}

export function formatHum(value, withUnit = true) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return `${Number(value).toFixed(1)}${withUnit ? " %" : ""}`;
}

export function formatNumber(value, decimals = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("es-MX", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatPercent(value) {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toFixed(1)}%`;
}

export function formatRange(min, max, unit = "") {
  if (min === null || min === undefined || max === null || max === undefined) return "—";
  return `${Number(min).toFixed(1)} a ${Number(max).toFixed(1)}${unit}`;
}

export const TRUCK_STATUS = {
  en_ruta: { label: "En ruta", className: "badge--route" },
  disponible: { label: "Disponible", className: "badge--success" },
  mantenimiento: { label: "Mantenimiento", className: "badge--warning" },
};

export const ALERT_TYPES = {
  temperatura: { label: "Temperatura", icon: "fa-temperature-half" },
  humedad: { label: "Humedad", icon: "fa-droplet" },
  desconexion: { label: "Desconexión", icon: "fa-plug-circle-xmark" },
};

export const ALERT_STATUS = {
  activa: { label: "Activa", className: "badge--danger" },
  resuelta: { label: "Resuelta", className: "badge--success" },
};

export const READING_STATUS = {
  normal: { label: "Normal", className: "reading--normal" },
  alerta: { label: "Fuera de rango", className: "reading--alert" },
  sin_lectura: { label: "Sin lectura", className: "reading--empty" },
};

export function truckStatusMeta(status) {
  return TRUCK_STATUS[status] || { label: status, className: "badge--muted" };
}

export function alertTypeMeta(type) {
  return ALERT_TYPES[type] || { label: type, icon: "fa-triangle-exclamation" };
}

export function alertStatusMeta(status) {
  return ALERT_STATUS[status] || { label: status, className: "badge--muted" };
}

export function readingStatusMeta(status) {
  return READING_STATUS[status] || READING_STATUS.sin_lectura;
}

export function debounce(fn, delay = 300) {
  let timeout;
  return (...args) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => fn(...args), delay);
  };
}

export function setButtonLoading(button, loading, loadingText = "Procesando…") {
  if (!button) return;
  if (loading) {
    if (!button.dataset.originalHtml) {
      button.dataset.originalHtml = button.innerHTML;
    }
    button.disabled = true;
    button.classList.add("is-loading");
    button.innerHTML = `<span class="spinner spinner--sm"></span> ${escapeHtml(loadingText)}`;
  } else {
    button.disabled = false;
    button.classList.remove("is-loading");
    if (button.dataset.originalHtml) {
      button.innerHTML = button.dataset.originalHtml;
      delete button.dataset.originalHtml;
    }
  }
}

export function toIsoOrNull(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export function truncate(value, length = 80) {
  if (!value) return "";
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}
