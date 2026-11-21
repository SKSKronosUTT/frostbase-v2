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

test("alta de conductor con contraseña temporal y baja lógica", async ({
  page,
  browser,
}) => {
  const api = page.context().request;
  const csrf = await csrfToken(page.context());
  const suffix = Date.now().toString().slice(-6);

  await page.goto("/drivers.html");
  await page.getByRole("button", { name: "Nuevo conductor" }).click();
  await page.locator("#driverFirstName").fill("Elena");
  await page.locator("#driverLastName").fill("Ramírez");
  await page.locator("#driverEmail").fill(`elena.${suffix}@frostbase.local`);
  await page.locator("#driverPhone").fill("6641112223");
  await page.locator("#driverBirthdate").fill("1991-04-05");
  await page.locator("#driverSubmit").click();

  const secret = page.locator("#secretModal");
  await expect(secret).toBeVisible();
  const temporaryPassword = await page.locator("#secretValue").textContent();
  expect(temporaryPassword?.length ?? 0).toBeGreaterThanOrEqual(12);
  await page.getByRole("button", { name: "Entendido" }).click();
  await expect(page.getByText(`elena.${suffix}@frostbase.local`)).toBeVisible();

  // El conductor entra con la contraseña temporal y se le exige cambiarla.
  // Se usa un contexto aparte para no sustituir la sesión de administrador.
  const driverContext = await browser.newContext();
  const driverApi = driverContext.request;
  const login = await driverApi.post("/api/v1/auth/login", {
    data: {
      identifier: `elena.${suffix}@frostbase.local`,
      password: temporaryPassword,
    },
  });
  expect(login.ok()).toBeTruthy();
  expect((await login.json()).role).toBe("driver");

  // Baja lógica desde el panel y reactivación desde el filtro de inactivos.
  const listed = await api.get(
    `/api/v1/drivers?search=elena.${suffix}&active=true`
  );
  expect(listed.ok(), await listed.text()).toBeTruthy();
  const [driver] = (await listed.json()).items;
  expect(driver).toBeTruthy();

  await page
    .locator(`[data-driver-action="deactivate"][data-id="${driver.id}"]`)
    .click();
  await page.getByRole("button", { name: "Desactivar" }).click();
  await expect(
    page.getByText(`elena.${suffix}@frostbase.local`)
  ).toHaveCount(0);

  const inactiveLogin = await driverApi.post("/api/v1/auth/login", {
    data: {
      identifier: `elena.${suffix}@frostbase.local`,
      password: temporaryPassword,
    },
  });
  expect(inactiveLogin.status()).toBe(401);

  await page.locator("#driverActiveFilter").selectOption("false");
  await page
    .locator(`[data-driver-action="restore"][data-id="${driver.id}"]`)
    .click();
  await expect(
    page.locator(`[data-driver-action="restore"][data-id="${driver.id}"]`)
  ).toHaveCount(0);

  // De vuelta en el filtro de activos, el conductor aparece con su acción de baja.
  await page.locator("#driverActiveFilter").selectOption("true");
  await expect(
    page.locator(`[data-driver-action="deactivate"][data-id="${driver.id}"]`)
  ).toBeVisible();

  const restored = await api.get("/api/v1/drivers?active=false");
  const inactive = (await restored.json()).items;
  const stillInactive = inactive.find(
    (item) => item.email === `elena.${suffix}@frostbase.local`
  );
  expect(stillInactive).toBeUndefined();

  await driverContext.close();
});
