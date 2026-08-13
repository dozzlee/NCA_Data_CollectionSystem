import AxeBuilder from "@axe-core/playwright";
import { expect, Page, test } from "@playwright/test";

const password = process.env.PLAYWRIGHT_DEMO_PASSWORD ?? "testpass123";

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

test("Provider Data Entry cannot contact NCA or open the Approver queue", async ({ page }) => {
  await signIn(page, "dataentry@vodafone.com.gh");
  await expect(page.getByRole("link", { name: "Technical Support" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Corrections" })).toBeVisible();
  await page.goto("/provider/pending-approval");
  await expect(page.getByRole("heading", { name: "Provider Approver access required" })).toBeVisible();
  await expectNoCriticalAccessibilityIssues(page);
});

test("Provider Approver receives review and compliance controls", async ({ page }) => {
  await signIn(page, "admin@vodafone.com.gh");
  await expect(page.getByRole("link", { name: "Pending Approval" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Compliance" })).toBeVisible();
  await page.goto("/provider/pending-approval");
  await expect(page.getByRole("heading", { name: "Approval work queue" })).toBeVisible();
  await expectNoCriticalAccessibilityIssues(page);
});

test("NCA Officer has operational parity with explicit exclusions", async ({ page }) => {
  await signIn(page, "officer.asante@nca.org.gh");
  await expect(page.getByRole("link", { name: "Form Builder" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Production Readiness" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Users" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Data Requests" })).toHaveCount(0);
  await expectNoCriticalAccessibilityIssues(page);
});

test("NCA Admin retains Users and Data Requests", async ({ page }) => {
  await signIn(page, "admin@nca.org.gh");
  await expect(page.getByRole("link", { name: "Users" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Data Requests" })).toBeVisible();
  await expectNoCriticalAccessibilityIssues(page);
});
