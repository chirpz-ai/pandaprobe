import { test, expect } from "@playwright/test";

test.describe("Auth flow (auth disabled)", () => {
  test("root redirects to an org page", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/org\//);
  });

  test("org page loads without login when auth is disabled", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("text=Home")).toBeVisible();
  });
});
