import { expect, test } from "@playwright/test";

const ADMIN = process.env.E2E_ADMIN_USER || "admin";
const PASSWORD = process.env.E2E_ADMIN_PASSWORD || process.env.ADMIN_PASSWORD;

async function csrfToken(context) {
  const cookies = await context.cookies();
  return cookies.find((item) => item.name === "frostbase_csrf")?.value || "";
}

test("login y redirección al panel", async ({ page }) => {
  await page.context().clearCookies();
  await page.goto("/login.html");
  await page.locator("#identifier").fill(ADMIN);
  await page.locator("#password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entrar al panel" }).click();
  await expect(page).toHaveURL(/dashboard\.html/, { timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "Panel de Control" })).toBeVisible();
});

test("alta de camión y dispositivo IoT", async ({ page }) => {
  const api = page.context().request;
  const plate = `E2E-${Date.now().toString().slice(-6)}`;
  await page.goto("/trucks.html");
  await page.getByRole("button", { name: "Nuevo camión" }).click();
  await page.locator("#truckBrand").fill("E2E");
  await page.locator("#truckModel").fill("Playwright");
  await page.locator("#truckYear").fill("2024");
  await page.locator("#truckPlate").fill(plate);
  await page.locator("#truckSubmit").click();
  await page.locator("#truckSearch").fill(plate);
  await expect(page.getByText(plate).first()).toBeVisible();

  await page.getByRole("tab", { name: /Dispositivos IoT/ }).click();
  await page.getByRole("button", { name: "Nuevo dispositivo" }).click();
  await page.locator("#deviceIdentifier").fill(`E2E-${Date.now()}`);
  await page.locator("#deviceSubmit").click();
  await expect(page.locator("#secretModal")).toBeVisible();
  await expect(page.locator("#secretValue")).not.toBeEmpty();

  const trucks = await api.get(`/api/v1/trucks/options?search=${plate}`);
  const [truck] = await trucks.json();
  await api.delete(`/api/v1/trucks/${truck.id}`, {
    headers: { "X-CSRF-Token": await csrfToken(page.context()) },
  });
});

test("ruta con geometría servida por la API", async ({ page }) => {
  const api = page.context().request;
  const csrf = await csrfToken(page.context());
  const response = await api.post("/api/v1/routes", {
    headers: { "X-CSRF-Token": csrf },
    data: {
      description: "Ruta E2E",
      status: "activa",
      points: [
        { name: "E2E A", latitude: 32.51, longitude: -117.03 },
        { name: "E2E B", latitude: 32.52, longitude: -117.04 },
      ],
    },
  });
  expect(response.ok()).toBeTruthy();
  const route = await response.json();

  await page.route("**/api/v1/routes/*/calculate", (routeHandler) =>
    routeHandler.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(route),
    })
  );
  await page.goto(`/routes.html?id=${route.id}`);
  await expect(page.locator("#routeEditorTitle")).toContainText("E2E A");
  await page.getByRole("button", { name: /Recalcular ruta/ }).click();
  await expect(page.getByText("Geometría de la ruta recalculada")).toBeVisible();
  await api.delete(`/api/v1/routes/${route.id}`, {
    headers: { "X-CSRF-Token": csrf },
  });
});

test("ingesta IoT fuera de rango genera alerta", async ({ page }) => {
  const api = page.context().request;
  const csrf = await csrfToken(page.context());
  const truck = await api.post("/api/v1/trucks", {
    headers: { "X-CSRF-Token": csrf },
    data: {
      brand: "E2E",
      model: "Alerta",
      year: 2024,
      plate: `ALT-${Date.now().toString().slice(-6)}`,
      status: "disponible",
    },
  });
  const truckBody = await truck.json();
  const deviceId = `E2E-ALERT-${Date.now()}`;
  const device = await api.post("/api/v1/devices", {
    headers: { "X-CSRF-Token": csrf },
    data: { device_id: deviceId, truck_id: truckBody.id },
  });
  const { device_key: deviceKey } = await device.json();

  const ingest = await api.post("/api/v1/iot/readings", {
    headers: { "X-Device-Id": deviceId, "X-Device-Key": deviceKey },
    data: {
      device_id: deviceId,
      temperature: 25,
      humidity: 80,
      timestamp: new Date().toISOString(),
    },
  });
  expect(ingest.ok()).toBeTruthy();

  await page.goto("/alerts.html?status=activa");
  await expect(page.getByText("Temperatura").first()).toBeVisible();
  await api.delete(`/api/v1/trucks/${truckBody.id}`, {
    headers: { "X-CSRF-Token": csrf },
  });
});

test("configuración de umbrales y tema", async ({ page }) => {
  await page.goto("/settings.html");
  await expect(page.locator("#settingsUpdated")).toContainText("Última actualización");
  await page.locator("#temperatureIdeal").fill("3");
  await page.locator("#weatherCity").fill("Tijuana");
  await page.getByRole("button", { name: /Guardar configuración/ }).click();
  await expect(
    page.getByText("La configuración se guardó correctamente.")
  ).toBeVisible();
});

test("borrado lógico y reutilización de placa", async ({ page }) => {
  const api = page.context().request;
  const csrf = await csrfToken(page.context());
  const plate = `REU-${Date.now().toString().slice(-6)}`;
  const created = await api.post("/api/v1/trucks", {
    headers: { "X-CSRF-Token": csrf },
    data: {
      brand: "E2E",
      model: "Reuso",
      year: 2024,
      plate,
      status: "disponible",
    },
  });
  expect(created.status()).toBe(201);
  await page.goto("/trucks.html");
  await page.locator("#truckSearch").fill(plate);
  await page.locator(`[data-action="delete"][data-plate="${plate}"]`).click();
  await page.getByRole("button", { name: "Eliminar camión" }).click();
  await expect(page.getByText(plate)).toHaveCount(0);

  const reused = await api.post("/api/v1/trucks", {
    headers: { "X-CSRF-Token": csrf },
    data: {
      brand: "E2E",
      model: "Reuso",
      year: 2024,
      plate,
      status: "disponible",
    },
  });
  expect(reused.status()).toBe(201);
  const newTruck = await reused.json();
  await api.delete(`/api/v1/trucks/${newTruck.id}`, {
    headers: { "X-CSRF-Token": csrf },
  });
});
