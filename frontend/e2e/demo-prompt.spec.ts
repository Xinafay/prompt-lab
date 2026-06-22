import { expect, test } from "@playwright/test";

test("demo string prompt and validators tabs show source sections", async ({ page }) => {
  await page.goto("/demo-string/prompt");

  const prompt = page.getByRole("region", { name: "Prompt source" });
  await expect(prompt.getByRole("heading", { name: "Demo String" })).toBeVisible();
  await expect(prompt.getByRole("heading", { name: "Prompt" })).toBeVisible();
  await expect(prompt.getByText("Reply to the customer ticket")).toBeVisible();
  await expect(prompt.getByText("Reply quality")).not.toBeVisible();

  await page.getByRole("tab", { name: "Validators" }).click();

  const validators = page.getByRole("region", { name: "Validators" });
  await expect(validators.getByRole("heading", { name: "Validators" })).toBeVisible();
  await expect(validators.getByRole("heading", { name: "Reply quality" })).toBeVisible();
  await expect(validators.getByText("LLM questionnaire")).toBeVisible();
  await expect(validators.getByRole("heading", { name: "Reply stats" })).toBeVisible();
  await expect(validators.getByText("Automatic")).toBeVisible();
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

test("demo json prompt shows prompt and model source", async ({ page }) => {
  await page.goto("/demo-json/prompt");

  const prompt = page.getByRole("region", { name: "Prompt source" });
  await expect(prompt).toBeVisible();
  await expect(prompt.getByRole("heading", { name: "Demo JSON" })).toBeVisible();
  await expect(prompt.getByRole("heading", { name: "Prompt" })).toBeVisible();
  await expect(
    prompt.getByText("Create a concise launch-readiness report")
  ).toBeVisible();

  await expect(prompt.getByRole("heading", { name: "Model" })).toBeVisible();
  await expect(prompt.getByText("model.py").first()).toBeVisible();
  await expect(prompt.getByText("class DemoReport")).toBeVisible();
});

test("demo json proposal shows new prompt and model plus diff", async ({
  page
}) => {
  await page.goto("/demo-json/proposal");
  await page.getByLabel("Version").selectOption("v002");

  const proposal = page.getByRole("region", { name: "Proposal" });
  await expect(proposal.getByRole("heading", { name: "Rationale" })).toBeVisible();
  await expect(proposal.getByText("Proposed prompt")).toBeVisible();
  await expect(proposal.getByText("Proposed model")).toBeVisible();
  await expect(proposal.getByText("set launch_ready to false")).toBeVisible();
  await expect(proposal.getByText("max_length=3").first()).toBeVisible();

  await proposal.getByRole("tab", { name: "Diff" }).click();

  const promptDiff = proposal.getByRole("region", { name: "Prompt diff" });
  await expect(promptDiff.getByText("Prompt diff")).toBeVisible();
  await expect(proposal.getByRole("region", { name: "Model diff" })).toBeVisible();
  await expect(
    promptDiff.locator(".cm-line", {
      hasText: /set launch_ready\s+based on the.*risks/
    })
  ).toBeVisible();
  await expect(
    promptDiff.locator(".cm-line", {
      hasText: /set launch_ready.*to false/
    })
  ).toBeVisible();
});
