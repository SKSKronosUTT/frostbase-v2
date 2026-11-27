import { expect, test } from "@playwright/test";

const EMPTY_STATE = { cookies: [], origins: [] };

test("sin preferencia sigue el tema oscuro del sistema", async ({ browser }) => {
  const context = await browser.newContext({
    colorScheme: "dark",
    storageState: EMPTY_STATE,
  });
  const page = await context.newPage();
  await page.goto("/login.html");
  await expect(page).toHaveURL(/login\.html/);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await context.close();
});

test("la preferencia guardada manda sobre el sistema", async ({ browser }) => {
  const context = await browser.newContext({
    colorScheme: "dark",
    storageState: EMPTY_STATE,
  });
  await context.addInitScript(() => {
    localStorage.setItem("frostbase-theme", "light");
  });
  const page = await context.newPage();
  await page.goto("/login.html");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await context.close();
});

test("el toggle guarda una preferencia explícita", async ({ browser }) => {
  const context = await browser.newContext({
    colorScheme: "light",
    storageState: EMPTY_STATE,
  });
  const page = await context.newPage();
  await page.goto("/login.html");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await page.click("#themeToggle");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(await page.evaluate(() => localStorage.getItem("frostbase-theme"))).toBe(
    "dark"
  );

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await context.close();
});

test("si no hay preferencia, sigue los cambios del sistema en vivo", async ({
  browser,
}) => {
  const context = await browser.newContext({
    colorScheme: "light",
    storageState: EMPTY_STATE,
  });
  const page = await context.newPage();
  await page.goto("/login.html");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await page.emulateMedia({ colorScheme: "dark" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(await page.evaluate(() => localStorage.getItem("frostbase-theme"))).toBeNull();
  await context.close();
});
