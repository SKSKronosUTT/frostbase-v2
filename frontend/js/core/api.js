const API_BASE = "/api/v1";
const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
export const REQUEST_TIMEOUT_MS = 15000;

const inFlight = new Set();
let redirectingToLogin = false;

export class ApiError extends Error {
  constructor(message, status, payload = null, { cancelled = false } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
    this.cancelled = cancelled;
  }
}

function emitConnection(online) {
  window.dispatchEvent(new CustomEvent("frostbase:connection", { detail: { online } }));
}

function readCookie(name) {
  const prefix = `${name}=`;
  const item = document.cookie.split("; ").find((row) => row.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

function extractDetail(payload, fallback) {
  if (!payload) return fallback;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) {
    return payload.detail
      .map((item) => {
        const location = Array.isArray(item.loc) ? item.loc.slice(-1)[0] : "";
        return location ? `${location}: ${item.msg}` : item.msg;
      })
      .join(" · ");
  }
  if (Array.isArray(payload.errors)) return payload.errors.join(" · ");
  return fallback;
}

export function isCancelledError(error) {
  return Boolean(error?.cancelled);
}

export function redirectToLogin() {
  if (redirectingToLogin) return;
  if (window.location.pathname.endsWith("login.html")) return;
  redirectingToLogin = true;
  const next = encodeURIComponent(
    window.location.pathname.split("/").pop() + window.location.search
  );
  window.location.replace(`login.html?next=${next}`);
}

export function cancelPendingRequests() {
  inFlight.forEach((controller) => controller.abort());
  inFlight.clear();
}

if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) cancelPendingRequests();
  });
}

async function request(
  path,
  { method = "GET", body, headers = {}, timeout = REQUEST_TIMEOUT_MS } = {},
  retried = false
) {
  const requestHeaders = { Accept: "application/json", ...headers };
  if (body !== undefined) {
    requestHeaders["Content-Type"] = "application/json";
  }
  if (MUTATING_METHODS.has(method)) {
    const csrfToken = readCookie("frostbase_csrf");
    if (csrfToken) requestHeaders["X-CSRF-Token"] = csrfToken;
  }

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeout);
  inFlight.add(controller);

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      credentials: "same-origin",
      headers: requestHeaders,
      signal: controller.signal,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    emitConnection(true);
  } catch (error) {
    if (error?.name === "AbortError") {
      const hidden = typeof document !== "undefined" && document.hidden;
      throw new ApiError(
        hidden
          ? "Solicitud cancelada"
          : "La solicitud tardó más de 15 segundos. Intenta de nuevo.",
        0,
        null,
        { cancelled: hidden }
      );
    }
    emitConnection(false);
    throw new ApiError(
      "No se pudo conectar con el servidor. Verifica tu conexión.",
      0,
      null
    );
  } finally {
    window.clearTimeout(timer);
    inFlight.delete(controller);
  }

  const contentType = response.headers.get("content-type") || "";
  let payload = null;
  if (response.status !== 204) {
    if (contentType.includes("application/json")) {
      payload = await response.json().catch(() => null);
    } else {
      payload = await response.text().catch(() => null);
    }
  }

  if (
    response.status === 401 &&
    !retried &&
    path !== "/auth/login" &&
    path !== "/auth/refresh"
  ) {
    try {
      await request("/auth/refresh", { method: "POST" }, true);
      return request(path, { method, body, headers, timeout }, true);
    } catch (refreshError) {
      redirectToLogin();
    }
  } else if (response.status === 401 && path !== "/auth/login") {
    redirectToLogin();
  }

  if (!response.ok) {
    const message = extractDetail(
      payload,
      `Error ${response.status} al procesar la solicitud`
    );
    throw new ApiError(message, response.status, payload);
  }

  return payload;
}

export const api = {
  get: (path, options) => request(path, options),
  post: (path, body, options) => request(path, { ...options, method: "POST", body }),
  put: (path, body, options) => request(path, { ...options, method: "PUT", body }),
  delete: (path, options) => request(path, { ...options, method: "DELETE" }),
};
