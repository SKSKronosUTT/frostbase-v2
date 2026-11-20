const API_BASE = "/api/v1";
const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export class ApiError extends Error {
  constructor(message, status, payload = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
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

async function request(
  path,
  { method = "GET", body, headers = {} } = {},
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

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      credentials: "same-origin",
      headers: requestHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (error) {
    throw new ApiError(
      "No se pudo conectar con el servidor. Verifica tu conexión.",
      0,
      null
    );
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
      return request(path, { method, body, headers }, true);
    } catch (refreshError) {
      /* La sesión no se pudo renovar; se propaga el 401 original. */
    }
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
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", body }),
  put: (path, body) => request(path, { method: "PUT", body }),
  delete: (path) => request(path, { method: "DELETE" }),
};
