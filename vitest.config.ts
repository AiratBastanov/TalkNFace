import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['apps/server/test/**/*.test.ts', 'packages/*/test/**/*.test.ts'],
    environment: 'node',
    fileParallelism: false,
    testTimeout: 10_000,
    hookTimeout: 10_000,
  },
});
