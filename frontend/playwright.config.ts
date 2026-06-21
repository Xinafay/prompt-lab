import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const reuseExistingServer = !process.env.CI;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    screenshot: "only-on-failure",
    trace: "on-first-retry"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ],
  webServer: [
    {
      command:
        "cd .. && PYTHONPATH=backend .venv/bin/python -m uvicorn prompt_lab.app:app --host 127.0.0.1 --port 8000",
      reuseExistingServer,
      timeout: 120_000,
      url: "http://127.0.0.1:8000/api/experiments"
    },
    {
      command: "pnpm dev -- --port 5173 --strictPort",
      reuseExistingServer,
      timeout: 120_000,
      url: baseURL
    }
  ]
});
