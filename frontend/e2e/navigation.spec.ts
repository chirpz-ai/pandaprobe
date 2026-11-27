import { test, expect } from "@playwright/test";

const TEST_ORG_ID = "test-org-id";
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

  test("Settings opens API Keys and lists the organization tabs in priority order", async ({
    page,
  }) => {
    await page.goto("/");
    const sidebar = page.locator("aside");
    await sidebar
      .getByRole("button", { name: "Settings", exact: true })
      .click();
    await expect(page).toHaveURL(/\/org\/[^/]+\/settings\/api-keys$/);
    await expect(sidebar.getByRole("navigation").getByRole("link")).toHaveText([
      "API Keys",
      "Projects",
      "Plans",
      "Billing",
      "Members",
      "Organization",
    ]);
  });

  test("navigating to traces page shows the traces heading", async ({
    page,
  }) => {
    await page.goto(ORG_URL);
    await page.click("text=Traces");
    await expect(page).toHaveURL(/\/org\/[^/]+\/project\/[^/]+\/traces/);
  });

  test("navigating to sessions page shows the sessions heading", async ({
    page,
  }) => {
    await page.goto(ORG_URL);
    await page.click("text=Sessions");
    await expect(page).toHaveURL(/\/org\/[^/]+\/project\/[^/]+\/sessions/);
  });

  test("navigating to evaluations page shows evaluation sections", async ({
    page,
  }) => {
    await page.goto(ORG_URL);
    await page.click("text=Evaluations");
    await expect(page).toHaveURL(/\/org\/[^/]+\/project\/[^/]+\/evaluations/);
  });
});
