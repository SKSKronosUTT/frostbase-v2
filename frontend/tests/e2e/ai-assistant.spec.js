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

const CONVERSATION_A = {
  id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  title: null,
  created_at: "2026-11-24T16:00:00Z",
  last_used_at: "2026-11-24T16:10:00Z",
  last_seq: 2,
};

const CONVERSATION_MESSAGES = {
  [CONVERSATION_A.id]: [
    { seq: 1, role: "user", text: "¿Cuántas alertas hay?", truncated: false },
    {
      seq: 2,
      role: "assistant",
      text: "Hay **3 alertas activas**: temperatura 2 y puerta 1.",
      truncated: false,
    },
  ],
};

async function mockAgent(
  page,
  {
    status = STATUS_ONLINE,
    chat,
    usage = USAGE_OK,
    conversations = [],
    messages = CONVERSATION_MESSAGES,
    truckOptions = [{ id: 1, label: "ABC-123" }],
  } = {}
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
  await page.route("**/api/v1/trucks/options", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(truckOptions),
    })
  );
  await page.route("**/api/v1/ai/quick/*", (route) => {
    const url = new URL(route.request().url());
    const id = url.pathname.split("/").pop();
    const truckId = url.searchParams.get("truck_id");
    if ((id === "truck-status" || id === "truck-thresholds") && !truckId) {
      return route.fulfill({
        status: 422,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Selecciona un camión" }),
      });
    }
    const responses = {
      "truck-status": {
        title: "Estado del camión",
        text: "Camión ABC-123 · fuera de rango\nLectura: 4.0 °C / 80.0 % · hace 2 min\nAlertas activas: temperatura",
      },
      "truck-thresholds": {
        title: "Umbrales del camión",
        text: "Umbrales de ABC-123 (valores efectivos):\n- Temperatura: -1 a 1 °C",
      },
      "trips-history": {
        title: "Historial de viajes",
        text: "Historial reciente (1 viajes completados):\n- ABC-123 · 1 fallidas",
      },
      "alerts-by-type": {
        title: "Alertas por tipo",
        text: "Alertas activas por tipo (2):\n- temperatura: 1",
      },
    };
    const response = responses[id] || {
      id: "fleet-summary",
      title: "Resumen de la flota",
      text: "Hay **3 alertas activas**: temperatura 2 y puerta 1.",
    };
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id, ...response, source: "system" }),
    });
  });
  const historyState = {
    conversations: conversations.map((item) => ({ ...item })),
    messages,
  };

  await page.route(/\/api\/v1\/ai\/conversations(\?.*)?$/, (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(historyState.conversations),
    });
  });

  await page.route(/\/api\/v1\/ai\/conversations\/[^/]+\/messages(\?.*)?$/, (route) => {
    const path = new URL(route.request().url()).pathname;
    const id = path.split("/").at(-2);
    const items = historyState.messages[id];
    if (!items) {
      return route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Conversación no encontrada" }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        conversation_id: id,
        generated_at: "2026-11-24T16:11:00Z",
        total: items.length,
        returned: items.length,
        truncated: false,
        messages: items,
      }),
    });
  });

  await page.route(/\/api\/v1\/ai\/conversations\/[^/]+$/, (route) => {
    const method = route.request().method();
    const path = new URL(route.request().url()).pathname;
    const id = path.split("/").pop();
    const index = historyState.conversations.findIndex((item) => item.id === id);

    if (method === "PATCH") {
      if (index === -1) {
        return route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Conversación no encontrada" }),
        });
      }
      const payload = route.request().postDataJSON();
      historyState.conversations[index] = {
        ...historyState.conversations[index],
        title: payload.title,
      };
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(historyState.conversations[index]),
      });
    }

    if (method === "DELETE") {
      if (index !== -1) historyState.conversations.splice(index, 1);
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ conversation_id: id, closed: true }),
      });
    }

    return route.fallback();
  });

  await page.route("**/api/v1/ai/chat", async (route) => {
    try {
      if (chat?.delayMs) {
        await new Promise((resolve) => setTimeout(resolve, chat.delayMs));
      }
      if (chat?.error) {
        return await route.fulfill({
          status: chat.error.status,
          contentType: "application/json",
          body: JSON.stringify({ detail: chat.error.detail }),
          headers: chat.error.headers,
        });
      }
      return await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          conversation_id: "11111111-1111-1111-1111-111111111111",
          reply: chat?.reply || "Hay **3 alertas activas**: temperatura 2 y puerta 1.",
          source: "agent",
          latency_ms: 1200,
        }),
      });
    } catch {
      // La petición se canceló localmente; no hay nada que responder.
      return undefined;
    }
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

test("historial: abre una conversación y la restaura al recargar", async ({ page }) => {
  await mockAgent(page, { conversations: [CONVERSATION_A] });
  await page.goto("/ai.html");

  const openButton = page.getByRole("button", {
    name: /Abrir Conversación del/,
  });
  await expect(openButton).toBeVisible();
  await openButton.click();

  await expect(page.getByText("¿Cuántas alertas hay?")).toBeVisible();
  await expect(page.getByText("3 alertas activas")).toBeVisible();
  await expect(page.locator("#aiEmpty")).toBeHidden();

  await page.reload();
  await expect(page.getByText("¿Cuántas alertas hay?")).toBeVisible();
  await expect(page.locator("#aiEmpty")).toBeHidden();
});

test("historial: renombra una conversación", async ({ page }) => {
  await mockAgent(page, { conversations: [CONVERSATION_A] });
  await page.goto("/ai.html");

  await page.getByRole("button", { name: "Renombrar conversación" }).click();
  const input = page.getByRole("textbox", {
    name: "Nuevo título de la conversación",
  });
  await input.fill("Ruta norte");
  await page.getByRole("button", { name: "Guardar título" }).click();

  await expect(page.getByRole("button", { name: "Abrir Ruta norte" })).toBeVisible();
});

test("historial: elimina una conversación", async ({ page }) => {
  await mockAgent(page, { conversations: [CONVERSATION_A] });
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/ai.html");

  await expect(
    page.getByRole("button", { name: /Abrir Conversación del/ })
  ).toBeVisible();
  await page.getByRole("button", { name: "Eliminar conversación" }).click();

  await expect(page.getByText("Sin conversaciones activas.")).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Abrir Conversación del/ })
  ).toHaveCount(0);
});

test("respuestas rápidas: estado de camión usa el selector", async ({ page }) => {
  await mockAgent(page, {});
  await page.goto("/ai.html");

  await expect(page.locator("#aiTruckSelect")).toHaveValue("1");
  await page.getByRole("button", { name: "Estado del camión" }).click();

  await expect(page.getByText("Camión ABC-123 · fuera de rango")).toBeVisible();
  await expect(page.getByText("Lectura: 4.0 °C / 80.0 %")).toBeVisible();
});

test("respuestas rápidas: exige camión seleccionado", async ({ page }) => {
  await mockAgent(page, {});
  await page.goto("/ai.html");

  await page.locator("#aiTruckSelect").selectOption("");
  await page.getByRole("button", { name: "Umbrales del camión" }).click();

  await expect(
    page.getByText("Selecciona un camión para esta consulta.")
  ).toBeVisible();
});

test("respuestas rápidas: historial de viajes y alertas por tipo", async ({ page }) => {
  await mockAgent(page, {});
  await page.goto("/ai.html");

  await page.getByRole("button", { name: "Historial de viajes" }).click();
  await expect(
    page.getByText("Historial reciente (1 viajes completados)")
  ).toBeVisible();

  await page.reload();
  await page.getByRole("button", { name: "Alertas por tipo" }).click();
  await expect(page.getByText("Alertas activas por tipo (2)")).toBeVisible();
});

test("espera: muestra tiempo transcurrido sin streaming", async ({ page }) => {
  await mockAgent(page, { chat: { delayMs: 2200, reply: "Respuesta tardía" } });
  await page.goto("/ai.html");

  await page.locator("#aiMessage").fill("¿Alertas?");
  await page.locator("#aiSend").click();

  await expect(page.locator("#aiTyping")).toBeVisible();
  await expect(page.locator("#aiTypingText")).toHaveText(/Enviando consulta… [1-9] s/, {
    timeout: 4000,
  });
  await expect(page.getByText("Respuesta tardía")).toBeVisible();
  await expect(page.locator("#aiTyping")).toBeHidden();
});

test("espera: cancelar pide confirmación y avisa del consumo", async ({ page }) => {
  await mockAgent(page, { chat: { delayMs: 3000, reply: "No debería verse" } });
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/ai.html");

  await page.locator("#aiMessage").fill("¿Alertas?");
  await page.locator("#aiSend").click();
  await expect(page.locator("#aiCancel")).toBeVisible();
  await page.locator("#aiCancel").click();

  await expect(
    page.getByText("Espera cancelada localmente. La consulta puede completarse")
  ).toBeVisible();
  await expect(page.locator("#aiTyping")).toBeHidden();
  await expect(page.locator("#aiSend")).toBeEnabled();
});

test("seguridad: una respuesta HTML se muestra como texto", async ({ page }) => {
  const payload = '<img src=x onerror="window.__xss=1">';
  await mockAgent(page, { chat: { reply: payload } });
  await page.goto("/ai.html");

  await page.locator("#aiMessage").fill("Prueba XSS");
  await page.locator("#aiSend").click();

  await expect(page.getByText(payload)).toBeVisible();
  expect(await page.evaluate(() => window.__xss)).toBeUndefined();
});
