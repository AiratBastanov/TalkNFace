import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e', workers: 1, fullyParallel: false, retries: 0, maxFailures: 1,
  timeout: 90_000, globalTimeout: 180_000, expect: { timeout: 5_000 },
  outputDir: '.tools/g2-browser-artifacts',
  reporter: [['list'], ['json', { outputFile: '.tools/g2-browser-tests.json' }]],
  use: { channel: 'chrome', headless: true, viewport: { width: 1280, height: 900 },
    // Traces contain Cookie/CSRF request headers. Never persist authentication traces.
    actionTimeout: 5_000, navigationTimeout: 10_000, screenshot: 'only-on-failure', trace: 'off' },
});
