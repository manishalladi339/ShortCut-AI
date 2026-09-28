import { expect, test } from "@playwright/test";

test("public auth entry is reachable and has no Emergent Google dependency", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("ShortCut", { exact: false }).first()).toBeVisible();

  await page.getByText("I already have an account").click();
  await expect(page.getByText("Welcome back")).toBeVisible();
  await expect(page.getByText("Continue with Google")).toHaveCount(0);
  await expect(page.getByPlaceholder("you@example.com")).toBeVisible();
});

test("signup requires terms acceptance and validates password locally", async ({ page }) => {
  await page.goto("/");
  await page.getByText("Create account").first().click();

  await expect(page.getByText("Create your studio")).toBeVisible();
  await page.getByPlaceholder("Your name").fill("Beta Tester");
  await page.getByPlaceholder("you@example.com").fill("tester@example.com");
  await page.getByPlaceholder("At least 8 characters").fill("short");
  await page.getByText("Create account").last().click();
  await expect(page.getByText("Password must be at least 8 characters")).toBeVisible();

  await page.getByPlaceholder("At least 8 characters").fill("Demo12345!");
  await page.getByText("Create account").last().click();
  await expect(page.getByText("Please accept the Terms and Privacy Policy")).toBeVisible();

  await page.getByTestId("signup-terms-switch").click();
  await page.getByText("Terms of Service").click();
  await expect(page.getByText("Terms of Service").first()).toBeVisible();
});
