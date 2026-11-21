import { expect, test } from "@playwright/test";

const PAGES = [
  "dashboard.html",
  "trucks.html",
  "drivers.html",
  "routes.html",
  "alerts.html",
  "settings.html",
];

test("cero violaciones de CSP en las páginas internas", async ({ page }) => {
  await page.addInitScript(() => {
    window.__cspViolations = [];
    document.addEventListener("securitypolicyviolation", (event) => {
      window.__cspViolations.push({
        directive: event.violatedDirective,
        blocked: event.blockedURI,
        sample: event.sample,
      });
    });
  });

  for (const pagePath of PAGES) {
    await page.goto(`/${pagePath}`);
    await page.waitForLoadState("networkidle");
    const violations = await page.evaluate(() => window.__cspViolations || []);
    expect(violations, `${pagePath}: ${JSON.stringify(violations)}`).toEqual([]);
  }
});
