import { expect, test } from "@playwright/test";

test.describe("portal del conductor", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("frostbase-theme", "light"));
    await page.goto("/driver.html", { waitUntil: "domcontentloaded" });
  });

  test("el logo se ve sobre fondo oscuro en tema claro", async ({ page }) => {
    const logo = page.locator(".driver-header__logo");
    await expect(logo).toBeVisible();

    const box = await logo.boundingBox();
    expect(Math.abs(box.width - box.height)).toBeLessThanOrEqual(1);

    const background = await logo.evaluate(
      (img) => getComputedStyle(img).backgroundColor
    );
    const [red, green, blue] = background.match(/\d+/g).slice(0, 3).map(Number);
    const luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255;

    expect(luminance).toBeLessThan(0.35);
  });

  test("los cuatro indicadores forman una rejilla 2x2 desde 480 px", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });

    const grid = page.locator(".driver-container-grid");
    const metrics = grid.locator(".driver-metric");
    await expect(metrics).toHaveCount(4);

    const columns = await grid.evaluate(
      (element) => getComputedStyle(element).gridTemplateColumns
    );
    expect(columns.split(" ")).toHaveLength(2);

    const rows = await metrics.evaluateAll((elements) =>
      elements.map((element) => Math.round(element.getBoundingClientRect().top))
    );
    expect(new Set(rows).size).toBe(2);
    expect(rows.filter((top) => top === rows[0])).toHaveLength(2);
  });
});
