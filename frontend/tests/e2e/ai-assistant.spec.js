import { expect, test } from "@playwright/test";

const STATUS_ONLINE = {
  enabled: true,
  online: true,
  latency_ms: 42.0,
  boot_id: "boot-e2e",
  wifi_connected: true,
  last_ok_at: "2026-11-23T08:00:00Z",
};

async function mockAgent(page, { status = STATUS_ONLINE, chat } = {}) {
  await page.route("**/api/v1/ai/status", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(status),
    })
  );
  await page.route("**/api/v1/ai/chat", (route) => {
    if (chat?.error) {
      return route.fulfill({
        status: chat.error.status,
        contentType: "application/json",
        body: JSON.stringify({ detail: chat.error.detail }),
        headers: chat.error.headers,
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        conversation_id: "11111111-1111-1111-1111-111111111111",
        reply: chat?.reply || "Hay **3 alertas activas**: temperatura 2 y puerta 1.",
        source: "agent",
        latency_ms: 1200,
      }),
    });
  });
}

test("asistente: estado en línea y respuesta a una sugerencia", async ({ page }) => {
  await mockAgent(page, {});
  await page.goto("/ai.html");

  await expect(page.getByRole("heading", { name: "Asistente IA" })).toBeVisible();
  await expect(page.getByText("Agente en línea")).toBeVisible();

  await page.getByRole("button", { name: "Resumen de la flota" }).click();
  await expect(page.getByText("Dame un resumen del estado de la flota.")).toBeVisible();
  await expect(page.getByText("3 alertas activas")).toBeVisible();
});

test("asistente: agente no disponible", async ({ page }) => {
  await mockAgent(page, {
    status: { ...STATUS_ONLINE, online: false },
  });
  await page.goto("/ai.html");
  await expect(page.getByText("Agente no disponible")).toBeVisible();
});

test("asistente: error de ocupado se explica al usuario", async ({ page }) => {
  await mockAgent(page, {
    chat: {
      error: {
        status: 429,
        detail: "El asistente está atendiendo otra consulta; intente en unos segundos",
        headers: { "Retry-After": "3" },
      },
    },
  });
  await page.goto("/ai.html");
  await page.locator("#aiMessage").fill("¿Cuántas alertas hay?");
  await page.locator("#aiSend").click();
  await expect(page.getByText("El agente está atendiendo otra consulta")).toBeVisible();
});
