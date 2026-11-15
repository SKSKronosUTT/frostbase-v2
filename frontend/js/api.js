const TOKEN_KEY = "frostbase.token";
const USER_KEY = "frostbase.user";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
}

export function getUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || sessionStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
}

export function setSession(token, user, remember = true) {
  clearSession();
  const storage = remember ? localStorage : sessionStorage;
  storage.setItem(TOKEN_KEY, token);
  storage.setItem(USER_KEY, JSON.stringify(user));
}

export function updateStoredUser(user) {
  const storage = localStorage.getItem(TOKEN_KEY) ? localStorage : sessionStorage;
  storage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  for (const storage of [localStorage, sessionStorage]) {
    storage.removeItem(TOKEN_KEY);
    storage.removeItem(USER_KEY);
  }
}

export function requireSession() {
  const token = getToken();
  if (!token) {
    window.location.replace("index.html");
    return false;
  }
  return true;
}

export async function api(path, options = {}, timeout = 25000) {
  const token = getToken();
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  let response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });
  } catch (error) {
    clearTimeout(timer);
    throw new ApiError(
      error.name === "AbortError" ? "El servidor tardó demasiado en responder" : "No se puede conectar con la API de Frostbase",
      0,
    );
  }
  clearTimeout(timer);

  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { detail: text };
    }
  }

  if (response.status === 401 && token && !path.startsWith("/auth/login")) {
    clearSession();
    if (!window.location.pathname.endsWith("index.html")) {
      window.location.replace("index.html");
    }
    throw new ApiError("Tu sesión expiró. Inicia sesión de nuevo.", 401);
  }

  if (!response.ok) {
    let detail = payload?.detail ?? payload?.error ?? "La solicitud falló";
    if (Array.isArray(detail)) {
      detail = detail.map((item) => item.msg || item.message || "Valor inválido").join(", ");
    }
    throw new ApiError(String(detail), response.status);
  }

  if (payload && Object.prototype.hasOwnProperty.call(payload, "status")) {
    if (payload.status !== 0) throw new ApiError(payload.error || "La solicitud falló", payload.status);
    return payload.data;
  }
  return payload;
}

export const get = (path) => api(path);
export const post = (path, body) => api(path, { method: "POST", body });
export const put = (path, body) => api(path, { method: "PUT", body });
export const del = (path) => api(path, { method: "DELETE" });
