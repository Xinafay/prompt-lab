import { cpSync, existsSync, readdirSync, rmSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const repoRoot = fileURLToPath(new URL("../..", import.meta.url));
const demoFixtureNames = ["demo-json", "demo-string"] as const;
const demoCaseSuiteNames = ["demo-json-briefs", "demo-string-replies"] as const;

function removeManagedExperimentFixtures() {
  const experimentsRoot = resolve(repoRoot, "experiments");
  if (!existsSync(experimentsRoot)) return;
  for (const entry of readdirSync(experimentsRoot, { withFileTypes: true })) {
    if (entry.isDirectory() && entry.name.startsWith("managed-")) {
      rmSync(resolve(experimentsRoot, entry.name), { recursive: true, force: true });
    }
  }
}

function resetDemoFixtures() {
  removeManagedExperimentFixtures();
  for (const fixtureName of demoFixtureNames) {
    const source = resolve(repoRoot, "examples", "experiments", fixtureName);
    const destination = resolve(repoRoot, "experiments", fixtureName);
    rmSync(destination, { recursive: true, force: true });
    cpSync(source, destination, { recursive: true });
  }
  for (const suiteName of demoCaseSuiteNames) {
    const source = resolve(repoRoot, "examples", "case_suites", suiteName);
    const destination = resolve(repoRoot, "case_suites", suiteName);
    rmSync(destination, { recursive: true, force: true });
    cpSync(source, destination, { recursive: true });
  }
}

test.beforeAll(() => {
  resetDemoFixtures();
});

test.afterAll(() => {
  removeManagedExperimentFixtures();
});

async function selectVersion(page: import("@playwright/test").Page, version: string) {
  const versionSelect = page.getByLabel("Version");
  await expect(versionSelect).toBeVisible();
  if ((await versionSelect.inputValue()) !== version) {
    await versionSelect.selectOption(version);
  }
  await expect(versionSelect).toHaveValue(version);
}

test("demo cases tab shows suite-backed cases and opens case suites", async ({
  page
}) => {
  await page.goto("/demo-string/cases");

  const stringCases = page.getByRole("region", { name: "Cases" });
  await expect(stringCases).toContainText("2 of 2 from Demo string replies");
  await expect(stringCases).toContainText("billing-reply");
  await expect(stringCases).toContainText("support-reply");

  await page.goto("/demo-json/cases");
  const jsonCases = page.getByRole("region", { name: "Cases" });
  await expect(jsonCases).toContainText("2 of 2 from Demo JSON briefs");
  await expect(jsonCases).toContainText("product-brief");
  await expect(jsonCases).toContainText("service-brief");

  await page.getByRole("button", { name: "Case Suites" }).click();
  await expect(page).toHaveURL(/\/case-suites\/demo-json-briefs\/cases$/);
  await expect(
    page.getByRole("navigation", { name: "Case Suites" })
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: "Cases" })).toHaveAttribute(
    "aria-selected",
    "true"
  );
  await expect(page.getByRole("tab", { name: "Settings" })).toBeVisible();

  const suiteWorkspace = page.getByRole("region", {
    name: "Case Suite workspace"
  });
  await expect(suiteWorkspace).toBeVisible();
  await expect(
    suiteWorkspace.getByRole("heading", { name: "Suite cases" })
  ).not.toBeVisible();
  await expect(suiteWorkspace.getByRole("region", { name: "Cases" })).toBeVisible();
  await expect(
    suiteWorkspace.getByRole("button", { name: "Edit payload" })
  ).toBeVisible();
  await expect(
    suiteWorkspace.getByRole("button", { name: "Delete case" })
  ).toBeVisible();
  await expect(
    suiteWorkspace.getByRole("button", { name: "Delete suite" })
  ).not.toBeVisible();

  await suiteWorkspace.getByRole("button", { name: "Edit payload" }).click();
  await expect(
    page.getByRole("dialog", { name: "Edit case payload" })
  ).toBeVisible();
  await expect(page.getByRole("region", { name: "Payload JSON" })).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();

  await suiteWorkspace.getByRole("button", { name: "Add case" }).click();
  await expect(page.getByRole("dialog", { name: "Add case" })).toBeVisible();
  await expect(page.getByText("Choose JSON file")).toBeVisible();
  await expect(page.getByText("No file selected")).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();

  await page.getByRole("tab", { name: "Settings" }).click();
  await expect(page).toHaveURL(/\/case-suites\/demo-json-briefs\/settings$/);
  await expect(
    suiteWorkspace.getByRole("heading", { name: "Settings" })
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Save" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Delete suite" })
  ).toBeVisible();
  await expect(page.getByRole("region", { name: "Cases" })).not.toBeVisible();

  await page.reload();
  await expect(
    page
  ).toHaveURL(/\/case-suites\/demo-json-briefs\/settings$/);
  await expect(
    suiteWorkspace.getByRole("heading", { name: "Settings" })
  ).toBeVisible();

  await page.getByRole("button", { name: "Experiments" }).click();
  await expect(page).toHaveURL(/\/experiments\/demo-json\/prompt$/);
  await expect(page.getByRole("navigation", { name: "Experiments" })).toBeVisible();
});

test("global settings uses a full-width settings workspace", async ({ page }) => {
  await page.goto("/global-settings");

  await expect(page.getByRole("heading", { name: "Global settings" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Experiments" })).not.toBeVisible();
  await expect(page.getByRole("navigation", { name: "Case Suites" })).not.toBeVisible();
  await expect(page.getByRole("button", { name: "New" })).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Save" })).toBeVisible();
});

test("demo string prompt and validators tabs show source sections", async ({ page }) => {
  await page.goto("/demo-string/prompt");

  const prompt = page.getByRole("region", { name: "Prompt source" });
  await expect(
    prompt.getByRole("heading", { name: "Prompt source" })
  ).toBeVisible();
  await expect(
    prompt.getByRole("heading", { name: "Demo String" })
  ).not.toBeVisible();
  await expect(prompt.getByText("Reply to the customer ticket")).toBeVisible();
  await expect(prompt.getByText("Reply quality")).not.toBeVisible();

  await page.getByRole("tab", { name: "Validators" }).click();

  const validators = page.getByRole("region", { name: "Validators" });
  await expect(page.getByRole("heading", { name: "Validators" })).toBeVisible();
  await expect(
    validators.getByRole("article", { name: /Reply quality validator/i })
  ).toBeVisible();
  await expect(
    validators.getByRole("article", { name: /Reply stats validator/i })
  ).toBeVisible();
  await expect(
    validators.getByRole("button", { name: /Edit Reply quality validator/i })
  ).toBeVisible();
  await expect(validators.getByRole("region", { name: "Validator editor" })).not.toBeVisible();
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
  await expect(
    prompt.getByRole("heading", { name: "Prompt source" })
  ).toBeVisible();
  await expect(
    prompt.getByRole("heading", { name: "Demo JSON" })
  ).not.toBeVisible();
  await expect(
    prompt.getByText("Create a concise launch-readiness report")
  ).toBeVisible();

  await expect(
    prompt.getByRole("heading", { name: "Model source" })
  ).toBeVisible();
  await expect(prompt.getByText("model.py").first()).toBeVisible();
  await expect(prompt.getByText("class DemoReport")).toBeVisible();
});

test("demo json validators show large read-only cards with all checks", async ({
  page
}) => {
  await page.goto("/demo-json/validators");
  await selectVersion(page, "v002");

  const validators = page.getByRole("region", { name: "Validators" });
  const reportShape = validators.getByRole("article", {
    name: /Report shape validator/i
  });

  await expect(reportShape).toBeVisible();
  await expect(reportShape.getByText("Automatic", { exact: true })).toBeVisible();
  await expect(reportShape.getByText("Enabled", { exact: true })).toBeVisible();
  await expect(reportShape.getByText("Output only", { exact: true })).toBeVisible();
  await expect(reportShape.getByText("3 checks", { exact: true })).toBeVisible();
  await expect(reportShape.getByText("Summary present")).toBeVisible();
  await expect(
    reportShape.getByText("Requires $.summary in output_json to exist.")
  ).toBeVisible();
  await expect(reportShape.getByText("Three tags")).toBeVisible();
  await expect(
    reportShape.getByText("Requires $.tags in output_json to contain exactly 3 items.")
  ).toBeVisible();
  await expect(reportShape.getByText("Risk count")).toBeVisible();
  await expect(
    reportShape.getByText("Requires $.risks in output_json to contain between 1 and 3 items.")
  ).toBeVisible();
});

test("demo json validator edit modal confirms discarding unsaved edits", async ({
  page
}) => {
  await page.goto("/demo-json/validators");
  await selectVersion(page, "v002");

  const validators = page.getByRole("region", { name: "Validators" });
  await validators
    .getByRole("button", { name: /Edit Report quality validator/i })
    .click();

  const dialog = page.getByRole("dialog", {
    name: /Edit validator:/i
  });
  const editor = dialog.getByRole("region", { name: "Validator editor" });
  await editor.getByLabel("Title").first().fill("Discard me");
  await dialog.getByRole("button", { name: "Cancel" }).first().click();

  await expect(dialog.getByRole("alert")).toContainText(
    "Discard unsaved validator edits?"
  );
  await dialog.getByRole("button", { name: "Keep editing" }).click();
  await expect(editor.getByLabel("Title").first()).toHaveValue("Discard me");

  await dialog.getByRole("button", { name: "Cancel" }).first().click();
  await dialog.getByRole("button", { name: "Discard edits" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(validators.getByText("Discard me")).not.toBeVisible();
});

test("demo json validators can be saved as next version", async ({ page }) => {
  await page.goto("/demo-json/validators");
  await selectVersion(page, "v001");

  const validators = page.getByRole("region", { name: "Validators" });
  await validators
    .getByRole("button", { name: /Edit Report quality validator/i })
    .click();

  const editedTitle = `Report quality e2e ${Date.now()}`;
  const dialog = page.getByRole("dialog", {
    name: /Edit validator:/i
  });
  const editor = dialog.getByRole("region", { name: "Validator editor" });
  await editor.getByLabel("Title").first().fill(editedTitle);
  await dialog.getByRole("button", { name: "Save changes" }).click();

  await page.getByRole("button", { name: "Save as next version" }).click();

  await expect(
    validators.getByText(/^Created v\d+ and switched to it\.$/)
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: "Validators" })).toHaveAttribute(
    "aria-selected",
    "true"
  );
  await expect(validators.getByText(editedTitle)).toBeVisible();
  await expect(page.getByRole("dialog")).not.toBeVisible();
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
    .getByRole("button", { name: /Edit Report quality validator/i })
    .click();

  const editedDescription = `Checks whether the structured report is useful and grounded. e2e ${Date.now()}`;
  const editDialog = page.getByRole("dialog", {
    name: /Edit validator:/i
  });
  const editor = editDialog.getByRole("region", { name: "Validator editor" });
  await editor.getByLabel("Description").first().fill(editedDescription);
  await editDialog.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();

  await page.getByRole("button", { name: "Overwrite current version" }).click();
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

test("experiment clone and delete actions live in settings", async ({ page }) => {
  await page.goto("/experiments/demo-json/prompt");

  const experimentRail = page.getByRole("navigation", { name: "Experiments" });
  await expect(
    experimentRail.getByRole("button", { name: "Clone" })
  ).not.toBeVisible();
  await expect(
    experimentRail.getByRole("button", { name: "Delete" })
  ).not.toBeVisible();

  await page.getByRole("tab", { name: "Settings" }).click();
  await expect(page).toHaveURL(/\/experiments\/demo-json\/settings$/);
  await expect(page.getByRole("button", { name: "Clone experiment" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Delete experiment" })).toBeVisible();

  await page.getByRole("button", { name: "Clone experiment" }).click();
  await expect(
    page.getByRole("dialog", { name: "Clone experiment" })
  ).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();

  await page.getByRole("button", { name: "Delete experiment" }).click();
  await expect(
    page.getByRole("dialog", { name: "Delete experiment" })
  ).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
});

test("experiment management creates clones and deletes experiments", async ({
  page
}) => {
  await page.goto("/demo-json/settings");

  const unique = Date.now();
  await page.getByRole("button", { name: "New" }).click();
  const newDialog = page.getByRole("dialog", { name: "New experiment" });
  await expect(newDialog).toBeVisible();
  await newDialog.getByLabel("Title").fill(`Managed Text ${unique}`);
  await newDialog.getByRole("button", { name: "Create experiment" }).click();

  await expect(page).toHaveURL(
    new RegExp(`/experiments/managed-text-${unique}/prompt$`)
  );
  await expect(
    page.getByRole("navigation", { name: "Experiments" })
  ).toContainText(`Managed Text ${unique}`);

  await page.getByRole("button", { name: "New" }).click();
  const pydanticDialog = page.getByRole("dialog", { name: "New experiment" });
  await pydanticDialog.getByLabel("Title").fill(`Managed JSON ${unique}`);
  await pydanticDialog.getByLabel("Output type").selectOption("pydantic");
  await pydanticDialog.getByLabel("Model entrypoint").fill("model.Output");
  await pydanticDialog.getByRole("button", { name: "Create experiment" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/experiments/managed-json-${unique}/prompt$`)
  );
  await expect(page.getByRole("region", { name: "Prompt source" })).toContainText(
    "Model source unavailable."
  );

  await page.goto("/demo-json/settings");
  await page.getByRole("button", { name: "Clone experiment" }).click();
  const cloneDialog = page.getByRole("dialog", { name: "Clone experiment" });
  await cloneDialog.getByLabel("Title").fill(`Managed Clone ${unique}`);
  await cloneDialog.getByRole("button", { name: "Clone experiment" }).click();

  await expect(page).toHaveURL(
    new RegExp(`/experiments/managed-clone-${unique}/settings$`)
  );
  await page.getByRole("tab", { name: "Cases" }).click();
  await expect(page.getByRole("region", { name: "Cases" })).toContainText(
    "product-brief"
  );
  await page.getByRole("tab", { name: "Validators" }).click();
  await expect(page.getByRole("region", { name: "Validators" })).toContainText(
    "Report"
  );

  await page.getByRole("tab", { name: "Settings" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/experiments/managed-clone-${unique}/settings$`)
  );
  await page.getByRole("button", { name: "Delete experiment" }).click();
  const deleteDialog = page.getByRole("dialog", { name: "Delete experiment" });
  await expect(deleteDialog).toContainText(
    "runs, validations, reviews, proposals, and comparisons"
  );
  await deleteDialog.getByRole("button", { name: "Delete experiment" }).click();

  await expect(
    page.getByRole("navigation", { name: "Experiments" })
  ).not.toContainText(`Managed Clone ${unique}`);
});
