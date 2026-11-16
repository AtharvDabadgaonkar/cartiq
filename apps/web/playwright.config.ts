import { defineConfig, devices } from '@playwright/test';

const channelOverride = process.env.PLAYWRIGHT_CHANNEL
  ? { channel: process.env.PLAYWRIGHT_CHANNEL }
  : {};

/** Smoke suite. Phase 3 fills in the storefront journeys. */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  /**
   * By default Playwright's own Chromium build is used, which CI installs.
   * Set PLAYWRIGHT_CHANNEL=chrome to run against a locally installed browser
   * instead — useful when the Playwright CDN download is unavailable.
   */
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], ...channelOverride } },
    { name: 'mobile', use: { ...devices['Pixel 7'], ...channelOverride } },
  ],
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        // CI builds first and runs the production server: the dev server's
        // on-demand compilation makes the first navigation of each spec slow
        // enough to look like a flake.
        command: process.env.CI ? 'pnpm start' : 'pnpm dev',
        url: 'http://localhost:3000',
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
