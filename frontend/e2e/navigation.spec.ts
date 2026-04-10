import { test, expect } from "@playwright/test";

const TEST_ORG_ID = "test-org-id";
const TEST_PROJECT_ID = "test-project-id";
const ORG_URL = `/org/${TEST_ORG_ID}`;

test.describe("Navigation", () => {
  test("sidebar renders all main navigation links", async ({ page }) => {
    await page.goto(ORG_URL);
    await expect(page.locator("text=Home")).toBeVisible();
    await expect(page.locator("text=Traces")).toBeVisible();
    await expect(page.locator("text=Sessions")).toBeVisible();
    await expect(page.locator("text=Evaluations")).toBeVisible();
    await expect(page.locator("text=Analytics")).toBeVisible();
  });

  test("sidebar renders settings navigation links", async ({ page }) => {
    await page.goto(ORG_URL);
    await expect(page.locator("text=Organization")).toBeVisible();
    await expect(page.locator("text=Members")).toBeVisible();
    await expect(page.locator("text=Projects")).toBeVisible();
    await expect(page.locator("text=API Keys")).toBeVisible();
    await expect(page.locator("text=Billing")).toBeVisible();
  });

  test("navigating to traces page shows the traces heading", async ({ page }) => {
    await page.goto(ORG_URL);
    await page.click("text=Traces");
    await expect(page).toHaveURL(/\/org\/[^/]+\/project\/[^/]+\/traces/);
  });

  test("navigating to sessions page shows the sessions heading", async ({ page }) => {
    await page.goto(ORG_URL);
    await page.click("text=Sessions");
    await expect(page).toHaveURL(/\/org\/[^/]+\/project\/[^/]+\/sessions/);
  });

  test("navigating to evaluations page shows evaluation sections", async ({ page }) => {
    await page.goto(ORG_URL);
    await page.click("text=Evaluations");
    await expect(page).toHaveURL(/\/org\/[^/]+\/project\/[^/]+\/evaluations/);
  });
});
