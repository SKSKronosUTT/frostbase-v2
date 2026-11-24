import { expect, test } from "@playwright/test";

const STATUS_ONLINE = {
  enabled: true,
  online: true,
  latency_ms: 42.0,
  boot_id: "boot-e2e-1234",
  wifi_connected: true,
  last_ok_at: "2026-11-23T08:00:00Z",
  last_agent_read_at: "2026-11-23T08:05:00Z",
};

const USAGE_OK = {
  limit: 100,
  used: 3,
  remaining: 97,
  day: "2026-11-24",
  reset_at: "2026-11-25T00:00:00-08:00",
};

const METRICS_OK = {
  days: 1,
  generated_at: "2026-11-24T08:00:00Z",
  requests: 12,
  errors: 1,
  by_action: { chat: 8, quick: 3, read: 1 },
  errors_by_http_status: { 503: 1 },
  latency_avg_ms: 5200.0,
  latency_p50_ms: 4800,
  latency_p95_ms: 9000,
};

async function mockAgent(
  page,
  { status = STATUS_ONLINE, chat, usage = USAGE_OK } = {}
) {
  await page.route("**/api/v1/ai/status", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(status),
    })
  );
  await page.route("**/api/v1/ai/usage", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(usage),
    })
  );
  await page.route("**/api/v1/ai/metrics**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(METRICS_OK),
    })
  );
  await page.route("**/api/v1/ai/quick/*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "fleet-summary",
        title: "Resumen de la flota",
        text: "Hay **3 alertas activas**: temperatura 2 y puerta 1.",
        source: "system",
      }),
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
  await expect(page.getByText("Datos del sistema")).toBeVisible();
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
  await expect(page.getByText(/Reintenta en \d+ s/)).toBeVisible();
  await expect(page.locator("#aiSend")).toBeDisabled();
});

test("asistente: cuota, métricas y salud del pull", async ({ page }) => {
  await mockAgent(page, {});
  await page.goto("/ai.html");

  await expect(page.locator("#aiUsageCount")).toHaveText("3/100");
  await expect(page.locator("#aiUsageHint")).toHaveText("97 disponibles");
  await expect(page.locator("#aiUsageErrors")).toHaveText("1");
  await expect(page.locator("#aiUsageLatency")).toHaveText("4800 ms / 9000 ms");
  await expect(page.locator("#aiUsagePull")).toContainText("Hace");
  await expect(page.locator("#aiUsageBoot")).toHaveText("boot boot-e2e");
});

test("asistente: cuota agotada deshabilita el envío", async ({ page }) => {
  await mockAgent(page, {
    usage: { ...USAGE_OK, used: 100, remaining: 0 },
  });
  await page.goto("/ai.html");

  await expect(page.locator("#aiUsageCount")).toHaveText("100/100");
  await expect(page.locator("#aiUsageHint")).toHaveText("Sin consultas disponibles");
  await expect(page.getByText(/Se agotó la cuota diaria/)).toBeVisible();
  await expect(page.locator("#aiSend")).toBeDisabled();
});
