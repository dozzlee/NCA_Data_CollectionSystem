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
  await page.locator('input[type="password"]').fill(password);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

test("Data Entry has a shared, responsive operational workspace", async ({ page }) => {
  await signIn(page, "dataentry@vodafone.com.gh");
  await page.goto("/provider/forms");
  await expect(page.getByRole("heading", { name: "Forms" })).toBeVisible();
  await expect(page.getByText("Active forms being completed, checked or corrected inside your organisation.")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("link", { name: /Updates/ })).toBeVisible();
  const critical = (await new AxeBuilder({ page }).analyze()).violations.filter((item) => item.impact === "critical");
  expect(critical).toEqual([]);
});

test("Approver uses the shared Forms workspace without one-click submission", async ({ page }) => {
  await signIn(page, "admin@vodafone.com.gh");
  await page.goto("/provider/forms?provider_status=AWAITING_APPROVAL");
  await expect(page.getByRole("heading", { name: "Forms" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Submit to NCA/ })).toHaveCount(0);
  await expect(page.getByPlaceholder("Search form or reporting period")).toBeVisible();
});
