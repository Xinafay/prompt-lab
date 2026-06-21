import { expect, test } from "@playwright/test";

test("demo string overview shows prompt and validators", async ({ page }) => {
  await page.goto("/demo-string/overview");

  const overview = page.getByRole("region", { name: "Experiment overview" });
  await expect(overview.getByRole("heading", { name: "Demo String" })).toBeVisible();
  await expect(overview.getByRole("heading", { name: "Prompt" })).toBeVisible();
  await expect(overview.getByText("Reply to the customer ticket")).toBeVisible();

  await expect(overview.getByRole("heading", { name: "Validators" })).toBeVisible();
  await expect(overview.getByRole("heading", { name: "Reply quality" })).toBeVisible();
  await expect(overview.getByText("LLM questionnaire")).toBeVisible();
  await expect(overview.getByRole("heading", { name: "Reply stats" })).toBeVisible();
  await expect(overview.getByText("Automatic")).toBeVisible();
});

test("demo string compare shows validator matrix and evidence modal", async ({
  page
}) => {
  await page.goto("/demo-string/compare");

  await page.getByRole("button", { name: /^(Recompare|Compare) versions$/ }).click();

  const comparison = page.getByRole("region", { name: "Comparison" });
  await expect(
    comparison.getByRole("heading", { name: "Compare matrix" })
  ).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: /v001/ })).toBeVisible();
  await expect(comparison.getByRole("columnheader", { name: /v002/ })).toBeVisible();
  await expect(comparison.getByRole("rowheader", { name: /Reply quality/ })).toBeVisible();
  await expect(comparison.getByRole("rowheader", { name: /Answers question/ })).toBeVisible();

  await comparison
    .getByRole("button", { name: /The reply is too vague/ })
    .click();
  await expect(page.getByRole("dialog")).toContainText("Evidence");
  await expect(page.getByRole("dialog")).toContainText("billing-reply");
});
