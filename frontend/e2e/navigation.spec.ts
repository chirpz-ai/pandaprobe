import { test, expect } from "@playwright/test";

test.describe("Navigation", () => {
  test("sidebar renders all main navigation links", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.locator("text=Dashboard")).toBeVisible();
    await expect(page.locator("text=Traces")).toBeVisible();
    await expect(page.locator("text=Sessions")).toBeVisible();
    await expect(page.locator("text=Evaluations")).toBeVisible();
    await expect(page.locator("text=Analytics")).toBeVisible();
  });

  test("sidebar renders settings navigation links", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.locator("text=Organization")).toBeVisible();
    await expect(page.locator("text=Members")).toBeVisible();
    await expect(page.locator("text=Projects")).toBeVisible();
    await expect(page.locator("text=API Keys")).toBeVisible();
    await expect(page.locator("text=Billing")).toBeVisible();
  });

  test("navigating to traces page shows the traces heading", async ({ page }) => {
    await page.goto("/dashboard");
    await page.click("text=Traces");
    await expect(page).toHaveURL(/\/dashboard\/traces/);
  });

  test("navigating to sessions page shows the sessions heading", async ({ page }) => {
    await page.goto("/dashboard");
    await page.click("text=Sessions");
    await expect(page).toHaveURL(/\/dashboard\/sessions/);
  });

  test("navigating to evaluations page shows evaluation sections", async ({ page }) => {
    await page.goto("/dashboard");
    await page.click("text=Evaluations");
    await expect(page).toHaveURL(/\/dashboard\/evaluations/);
  });
});
