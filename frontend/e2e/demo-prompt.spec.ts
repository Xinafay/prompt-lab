import { expect, test } from "@playwright/test";

test.describe.configure({ mode: "serial" });

async function selectVersion(page: import("@playwright/test").Page, version: string) {
  const versionSelect = page.getByLabel("Version");
  await expect(versionSelect).toBeVisible();
  if ((await versionSelect.inputValue()) !== version) {
    await versionSelect.selectOption(version);
  }
  await expect(versionSelect).toHaveValue(version);
}

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
  await expect(
    validators.getByRole("button", { name: /Reply quality\s+reply-quality/i })
  ).toBeVisible();
  await expect(
    validators.getByRole("button", { name: /Reply stats\s+reply-stats/i })
  ).toBeVisible();
  await expect(validators.getByRole("region", { name: "Validator editor" })).toBeVisible();
  await expect(validators.getByLabel("Type")).toHaveValue("llm_questionnaire");
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

test("demo json validators can be saved as next version", async ({ page }) => {
  await page.goto("/demo-json/validators");
  await selectVersion(page, "v001");

  const validators = page.getByRole("region", { name: "Validators" });
  await validators
    .getByRole("button", { name: /Report quality\s+report-quality/i })
    .click();

  const editedTitle = `Report quality e2e ${Date.now()}`;
  const editor = validators.getByRole("region", { name: "Validator editor" });
  await editor.getByLabel("Title").first().fill(editedTitle);

  await validators.getByRole("button", { name: "Save as next version" }).click();

  await expect(
    validators.getByText(/^Created v\d+ and switched to it\.$/)
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: "Validators" })).toHaveAttribute(
    "aria-selected",
    "true"
  );
  await expect(validators.getByText(editedTitle)).toBeVisible();
  await expect(editor.getByLabel("Title").first()).toHaveValue(editedTitle);
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

test("demo json validators can overwrite current version", async ({ page }) => {
  await page.goto("/demo-json/validators");
  await selectVersion(page, "v002");

  const validators = page.getByRole("region", { name: "Validators" });
  await validators
    .getByRole("button", { name: /Report quality\s+report-quality/i })
    .click();

  const editedDescription = `Checks whether the structured report is useful and grounded. e2e ${Date.now()}`;
  const editor = validators.getByRole("region", { name: "Validator editor" });
  await editor.getByLabel("Description").first().fill(editedDescription);

  await validators.getByRole("button", { name: "Overwrite current version" }).click();
  const dialog = page.getByRole("dialog", {
    name: "Overwrite current validators?"
  });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Overwrite current version" }).click();

  await expect(
    validators.getByText(
      "Overwrote validators for v002 and cleared generated validation artifacts."
    )
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: "Validators" })).toHaveAttribute(
    "aria-selected",
    "true"
  );

  await page.getByRole("tab", { name: "Runs" }).click();
  const runs = page.getByRole("region", { name: "Run results" });
  await expect(runs.getByRole("heading", { name: "Active run" })).toBeVisible();
  await expect(runs.getByRole("cell", { name: /product brief/i }).first()).toBeVisible();
  await expect(runs.getByText("Output JSON")).toBeVisible();

  await page.getByRole("tab", { name: "Validation" }).click();
  const validation = page.getByRole("region", { name: "Validation" });
  await expect(
    validation.getByText("No validation loaded. Validate the active run to review evidence.")
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Validate active run" })).toBeVisible();
});
