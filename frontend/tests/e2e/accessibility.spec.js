import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const THEMES = ["light", "dark"];
const IMPACTS = ["moderate", "serious", "critical"];

let truckId = null;
let routeId = null;

test.beforeAll(async ({ request }) => {
  const trucks = await request.get("/api/v1/trucks?limit=1");
  if (trucks.ok()) {
    const data = await trucks.json();
    truckId = data.items?.[0]?.id ?? data[0]?.id ?? null;
  }
  const routes = await request.get("/api/v1/routes?limit=1");
  if (routes.ok()) {
    const data = await routes.json();
    routeId = data.items?.[0]?.id ?? data[0]?.id ?? null;
  }
});

const PAGES = [
  { path: "dashboard.html", label: "dashboard" },
  { path: "trucks.html", label: "flota" },
  { path: "trucks.html", label: "flota (dispositivos)", devices: true },
  { path: "drivers.html", label: "conductores" },
  { path: "routes.html", label: "rutas", openRoute: true },
  {
    path: () => `route-detail.html?id=${routeId}`,
    label: "detalle de ruta",
    requires: "routeId",
  },
  {
    path: () => `truck-detail.html?id=${truckId}`,
    label: "detalle de camión",
    requires: "truckId",
  },
  { path: "alerts.html", label: "alertas" },
  { path: "settings.html", label: "configuración" },
  { path: "ai.html", label: "asistente IA" },
  { path: "driver.html", label: "portal del conductor" },
];

function formatViolations(violations) {
  return violations
    .map(
      (violation) =>
        `${violation.id} (${violation.impact}): ${violation.help}\n${violation.nodes
          .slice(0, 4)
          .map((node) => `  ${node.target.join(" ")}`)
          .join("\n")}`
    )
    .join("\n");
}

async function settle(page) {
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
}

async function audit(page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  return results.violations.filter((violation) => IMPACTS.includes(violation.impact));
}

async function expectNoViolations(page) {
  const violations = await audit(page);
  expect(violations, formatViolations(violations)).toEqual([]);
}

async function prepare(page, theme) {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addInitScript((value) => {
    localStorage.setItem("frostbase-theme", value);
  }, theme);
}

for (const theme of THEMES) {
  for (const config of PAGES) {
    test(`sin violaciones moderate+ en ${config.label} (${theme})`, async ({
      page,
    }) => {
      test.skip(
        Boolean(config.requires) && !{ truckId, routeId }[config.requires],
        `Sin datos para ${config.label}`
      );

      await prepare(page, theme);
      const url = typeof config.path === "function" ? config.path() : config.path;
      await page.goto(`/${url}`, { waitUntil: "domcontentloaded" });
      await settle(page);

      if (config.devices) {
        await page.getByRole("tab", { name: /Dispositivos IoT/ }).click();
        await settle(page);
      }
      if (config.openRoute) {
        const item = page.locator("#routesList [data-route-id]").first();
        if (await item.count()) {
          await item.click();
          await settle(page);
        }
      }

      await expectNoViolations(page);
    });
  }

  test(`sin violaciones moderate+ en login (${theme})`, async ({ page }) => {
    await page.context().clearCookies();
    await prepare(page, theme);
    await page.goto("/login.html", { waitUntil: "domcontentloaded" });
    await settle(page);
    await expectNoViolations(page);
  });

  test(`sin violaciones moderate+ en index (${theme})`, async ({ page }) => {
    await prepare(page, theme);
    // index.js redirige en cuanto resuelve la sesión; se bloquea solo ese
    // módulo para poder auditar el splash sin que salga de la página.
    await page.route("**/assets/build/index.*.js", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/javascript",
        body: "",
      })
    );
    await page.goto("/index.html", { waitUntil: "domcontentloaded" });
    await expect(page.locator("main.splash")).toBeVisible();
    await expectNoViolations(page);
  });
}

test.describe("foco y teclado", () => {
  test("el skip link lleva el foco al contenido principal", async ({ page }) => {
    await page.goto("/dashboard.html");
    await page.keyboard.press("Tab");
    await expect(page.locator(".skip-link")).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("#main")).toBeFocused();
  });

  test("el drawer móvil atrapa el foco y lo devuelve al cerrar", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/dashboard.html");
    const toggle = page.locator("#sidebarMobileToggle");
    const sidebar = page.locator("#sidebar");
    const main = page.locator("#main");

    await expect(toggle).toBeVisible();
    await expect(sidebar).toHaveAttribute("inert", "");
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await expect(page.locator(".sidebar .nav-link.is-active")).toBeFocused();
    await expect(main).toHaveAttribute("inert", "");

    await page.keyboard.press("Escape");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(toggle).toBeFocused();
    await expect(main).not.toHaveAttribute("inert", "");
  });

  test("las pestañas de flota se navegan con flechas, Home y End", async ({ page }) => {
    await page.goto("/trucks.html");
    const trucksTab = page.getByRole("tab", { name: /Camiones/ });
    const devicesTab = page.getByRole("tab", { name: /Dispositivos IoT/ });
    const devicesPanel = page.locator("#devicesPanel");

    await trucksTab.focus();
    await page.keyboard.press("ArrowRight");
    await expect(devicesTab).toBeFocused();
    await expect(devicesTab).toHaveAttribute("aria-selected", "true");
    await expect(devicesPanel).toBeVisible();

    await page.keyboard.press("ArrowLeft");
    await expect(trucksTab).toBeFocused();
    await expect(trucksTab).toHaveAttribute("aria-selected", "true");

    await page.keyboard.press("End");
    await expect(devicesTab).toBeFocused();
    await page.keyboard.press("Home");
    await expect(trucksTab).toBeFocused();
  });

  test("los errores de acceso se anuncian y reciben el foco", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto("/login.html");
    await page.getByRole("button", { name: "Entrar al panel" }).click();

    const identifier = page.locator("#identifier");
    const error = page.locator("#identifier-error");
    await expect(identifier).toBeFocused();
    await expect(identifier).toHaveAttribute("aria-invalid", "true");
    await expect(identifier).toHaveAttribute("aria-describedby", /identifier-error/);
    await expect(error).toHaveAttribute("role", "alert");
    await expect(error).toContainText("Ingresa tu usuario");

    await identifier.fill("admin");
    await expect(identifier).not.toHaveAttribute("aria-invalid", "true");
    await expect(error).toHaveCount(0);
  });
});
