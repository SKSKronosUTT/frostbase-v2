import { request as playwrightRequest } from "@playwright/test";

const AUTH_FILE = "tests/e2e/.auth/state.json";

export default async function globalSetup() {
  const baseURL = process.env.E2E_BASE_URL || "http://127.0.0.1:8050";
  const password = process.env.E2E_ADMIN_PASSWORD || process.env.ADMIN_PASSWORD;
  if (!password) throw new Error("Defina E2E_ADMIN_PASSWORD o ADMIN_PASSWORD");

  const context = await playwrightRequest.newContext({ baseURL });
  const response = await context.post("/api/v1/auth/login", {
    data: {
      identifier: process.env.E2E_ADMIN_USER || "admin",
      password,
    },
  });
  if (!response.ok()) {
    throw new Error(`Login E2E falló: ${response.status()} ${await response.text()}`);
  }
  await context.storageState({ path: AUTH_FILE });
  await context.dispose();
}
