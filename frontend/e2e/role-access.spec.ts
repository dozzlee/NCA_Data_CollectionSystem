import AxeBuilder from "@axe-core/playwright";
import { expect, Page, test } from "@playwright/test";

function requiredTestPassword(): string {
  const value = process.env.PLAYWRIGHT_DEMO_PASSWORD;
  if (!value) throw new Error("PLAYWRIGHT_DEMO_PASSWORD must be supplied by the test environment.");
  return value;
}
const password = requiredTestPassword();

async function signIn(page: Page, email: string) {
  await page.goto("/login");
  await page.getByPlaceholder("you@example.com").fill(email);
  await page.getByPlaceholder("••••••••••••").fill(password);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

async function expectNoCriticalAccessibilityIssues(page: Page) {
  const result = await new AxeBuilder({ page }).analyze();
  const critical = result.violations.filter((violation) => violation.impact === "critical");
  expect(critical, JSON.stringify(critical, null, 2)).toEqual([]);
}

test("Data Requester sees the governed requester portal only", async ({ page }) => {
  await signIn(page, "viewer@nca.org.gh");
  await expect(page.getByRole("link", { name: "Data Catalog" })).toBeVisible();
  await expect(page.getByRole("link", { name: "My Requests" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Submissions" })).toHaveCount(0);
  await expectNoCriticalAccessibilityIssues(page);
});

test("Provider Data Entry cannot contact NCA and can use the shared Forms queue", async ({ page }) => {
  await signIn(page, "dataentry@vodafone.com.gh");
  await expect(page.getByRole("link", { name: "Technical Support" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Compliance" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Forms", exact: true })).toBeVisible();
  await page.goto("/provider/forms");
  await expect(page.getByRole("heading", { name: "Forms" })).toBeVisible();
  await expectNoCriticalAccessibilityIssues(page);
});

test("Provider Approver receives the unified review and flag controls", async ({ page }) => {
  await signIn(page, "admin@vodafone.com.gh");
  await expect(page.getByRole("link", { name: "Forms", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Compliance" })).toHaveCount(0);
  await page.goto("/provider/forms?provider_status=AWAITING_APPROVAL");
  await expect(page.getByRole("heading", { name: "Forms" })).toBeVisible();
  await expectNoCriticalAccessibilityIssues(page);
});

test("NCA Officer has operational parity with explicit exclusions", async ({ page }) => {
  await signIn(page, "officer.asante@nca.org.gh");
  await expect(page.getByRole("link", { name: "Forms" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Production Readiness" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Users" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Data Requests" })).toBeVisible();
  await page.goto("/support");
  await expect(page.getByRole("tab", { name: "Feedback" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Support Queue" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Support Queue" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Feedback" }).click();
  await expect(page.getByRole("heading", { name: "Provider feedback" })).toBeVisible();
  await expectNoCriticalAccessibilityIssues(page);
});

test("NCA Admin retains Users and Data Requests", async ({ page }) => {
  await signIn(page, "admin@nca.org.gh");
  await expect(page.getByRole("link", { name: "Users" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Data Requests" })).toBeVisible();
  await expectNoCriticalAccessibilityIssues(page);
});
