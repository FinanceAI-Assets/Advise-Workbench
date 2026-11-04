import { test, expect } from "@playwright/test";

// The workbench is the only UI generation. These checks keep its routes rendering and
// stop the retired project-studio routes from coming back.

const workbenchRoutes = [
  "/engagements",
  "/engagements/new",
  "/conversation",
  "/deliverables",
  "/library",
  "/skills",
  "/reviews",
  "/help",
  "/settings",
  "/admin/console",
  "/admin/console/skills",
  "/admin/console/skills/new",
];

const retiredRoutes = [
  "/projects",
  "/projects/new",
  "/projects/p_test",
  "/projects/p_test/runs/r_test",
  "/v2/projects/p_test",
  "/customize",
  "/memory",
  "/tasks",
  "/permissions",
  "/admin/dpdp",
  "/admin/skills",
  "/admin/skills/new",
  "/admin/lp-library",
];

test.describe("Workbench routes", () => {
  for (const route of workbenchRoutes) {
    test(`${route} renders`, async ({ page }) => {
      const pageErrors: Error[] = [];
      page.on("pageerror", (err) => pageErrors.push(err));

      const response = await page.goto(route);
      expect(response?.status()).toBeLessThan(400);
      await expect(page.locator("body")).toBeVisible();
      await expect(page.getByText("Application error")).toHaveCount(0);
      expect(pageErrors).toEqual([]);
    });
  }
});

test.describe("Retired routes", () => {
  for (const route of retiredRoutes) {
    test(`${route} is gone`, async ({ page }) => {
      const response = await page.goto(route);
      expect(response?.status()).toBe(404);
    });
  }
});
