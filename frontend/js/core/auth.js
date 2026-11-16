import { api } from "./api.js";

let cachedAdmin = null;

export async function login(identifier, password) {
  const response = await api.post("/auth/login", { identifier, password });
  cachedAdmin = response.admin;
  return response.admin;
}

export async function getMe() {
  cachedAdmin = await api.get("/auth/me");
  return cachedAdmin;
}

export async function requireAuth() {
  try {
    return await getMe();
  } catch (error) {
    if (error.status === 401) {
      const next = encodeURIComponent(
        window.location.pathname.split("/").pop() + window.location.search
      );
      window.location.replace(`login.html?next=${next}`);
      throw new Error("redirecting");
    }
    throw error;
  }
}

export function getCachedAdmin() {
  return cachedAdmin;
}

export async function logout() {
  try {
    await api.post("/auth/logout");
  } catch (error) {
    /* La sesión local se limpia aunque el servidor no responda */
  }
  cachedAdmin = null;
  window.location.replace("login.html");
}
