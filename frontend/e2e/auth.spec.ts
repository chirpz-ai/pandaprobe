import { test, expect } from "@playwright/test";

test.describe("Auth flow (auth disabled)", () => {
  test("root redirects to dashboard", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("dashboard loads without login when auth is disabled", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.locator("text=Dashboard")).toBeVisible();
  });
});
