import { expect, test } from "@playwright/test";

test.describe("logo del login", () => {
  test("el logo conserva la proporción cuadrada", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto("/login.html", { waitUntil: "domcontentloaded" });

    const logo = page.locator(".login-brand__logo img");
    await expect(logo).toBeVisible();

    const box = await logo.boundingBox();
    const natural = await logo.evaluate((img) => ({
      width: img.naturalWidth,
      height: img.naturalHeight,
    }));

    expect(box.width).toBeGreaterThan(0);
    expect(box.height).toBeGreaterThan(0);
    expect(Math.abs(box.width - box.height)).toBeLessThanOrEqual(1);
    expect(natural.width).toBe(natural.height);
  });
});
