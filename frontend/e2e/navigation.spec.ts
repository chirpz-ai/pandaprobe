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

  test("switching organizations keeps the Projects tab and shows the selected organization's projects", async ({
    page,
  }) => {
    const createdAt = "2026-01-01T00:00:00Z";
    const organizations = [
      {
        id: TEST_ORG_ID,
        name: "First team",
        role: "OWNER",
        created_at: createdAt,
      },
      {
        id: "other-org-id",
        name: "Second team",
        role: "MEMBER",
        created_at: createdAt,
      },
    ];
    await page.route("**/organizations", (route) =>
      route.fulfill({ json: organizations }),
    );
    for (const org of organizations) {
      await page.route(`**/organizations/${org.id}/projects`, (route) =>
        route.fulfill({
          json: [
            {
              id: `${org.id}-project`,
              org_id: org.id,
              name: `${org.name} project`,
              description: "",
              created_at: createdAt,
            },
          ],
        }),
      );
    }

    await page.goto(`${ORG_URL}/settings/projects`);
    const main = page.getByRole("main");
    await expect(
      main.getByText("First team project", { exact: true }),
    ).toBeVisible();
    await page
      .locator("aside")
      .getByRole("button", { name: "First team", exact: true })
      .click();
    await page
      .getByRole("menuitem", { name: "Second team", exact: true })
      .click();
    await expect(page).toHaveURL("/org/other-org-id/settings/projects");
    await expect(
      main.getByText("Second team project", { exact: true }),
    ).toBeVisible();
    await expect(
      main.getByText("First team project", { exact: true }),
    ).toHaveCount(0);
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
