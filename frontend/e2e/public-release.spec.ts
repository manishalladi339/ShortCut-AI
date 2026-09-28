import { expect, test } from "@playwright/test";

test("email user can sign up and create a project", async ({ page }) => {
  const email = `e2e-${Date.now()}@shortcut.ai`;

  await page.goto("/");
  await expect(page.getByTestId("welcome-title")).toBeVisible();

  await page.getByTestId("welcome-signup-button").click();
  await page.getByTestId("auth-name-input").fill("Release Test");
  await page.getByTestId("auth-email-input").fill(email);
  await page.getByTestId("auth-password-input").fill("ReleaseTest123!");
  await page.getByTestId("auth-signup-submit-button").click();
  await expect(page.getByTestId("signup-error")).toContainText("accept the Terms");
  await page.getByTestId("signup-terms-switch").click();
  await page.getByTestId("auth-signup-submit-button").click();

  await expect(page.getByTestId("dashboard-username")).toHaveText("Release Test");

  await page.getByTestId("dashboard-quickaction-new").click();
  await expect(page.getByTestId("new-project-title")).toBeVisible();
  await page.getByTestId("new-project-title-input").fill("Public Release Smoke");
  await page.getByTestId("new-project-submit-button").click();

  await expect(page.getByTestId("project-upload-asset-button")).toBeVisible();
  await expect(page.getByTestId("project-detail-header-title")).toHaveText("Public Release Smoke");
});


test("legal pages are reachable before signup", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("welcome-signup-button").click();
  await page.getByText("Terms of Service").click();
  await expect(page.getByTestId("legal-page-title")).toHaveText("Terms of Service");
  await page.goBack();
  await page.getByText("Privacy Policy").click();
  await expect(page.getByTestId("legal-page-title")).toHaveText("Privacy Policy");
});
