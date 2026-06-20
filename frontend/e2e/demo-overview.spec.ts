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
