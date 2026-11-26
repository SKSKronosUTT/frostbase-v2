import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const PAGES = [
  "dashboard.html",
  "trucks.html",
  "drivers.html",
  "routes.html",
  "alerts.html",
  "settings.html",
  "ai.html",
];

const THEMES = ["light", "dark"];

function blockingViolations(results) {
  return results.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact)
  );
}

for (const theme of THEMES) {
  for (const pagePath of PAGES) {
    test(`sin violaciones graves en ${pagePath} (${theme})`, async ({ page }) => {
      await page.addInitScript((value) => {
        localStorage.setItem("frostbase-theme", value);
      }, theme);
      await page.goto(`/${pagePath}`);
      await page.waitForLoadState("networkidle");
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa"])
        .analyze();
      const blocking = blockingViolations(results);
      expect(
        blocking,
        blocking
          .map(
            (violation) =>
              `${violation.id}: ${violation.help}\n${violation.nodes
                .slice(0, 3)
                .map((node) => `  ${node.target.join(" ")}`)
                .join("\n")}`
          )
          .join("\n")
      ).toEqual([]);
    });
  }

  test(`sin violaciones graves en el login (${theme})`, async ({ page }) => {
    await page.context().clearCookies();
    await page.addInitScript((value) => {
      localStorage.setItem("frostbase-theme", value);
    }, theme);
    await page.goto("/login.html");
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    const blocking = blockingViolations(results);
    expect(blocking, JSON.stringify(blocking.map((item) => item.id))).toEqual([]);
  });
}
