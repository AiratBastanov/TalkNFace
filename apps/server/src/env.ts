import { resolve } from 'node:path';
import { z } from 'zod';
import { PROJECT_ROOT } from './paths.ts';

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  HOST: z.string().trim().regex(/^[A-Za-z0-9.:-]+$/).default('127.0.0.1'),
  PORT: z.string().regex(/^\d+$/).transform(Number).pipe(z.number().int().min(1).max(65535)).default(3000),
  DATABASE_PATH: z.string().trim().min(1).refine(
    (path) => path !== ':memory:' && !path.startsWith('file:') && !/[\0\r\n]/.test(path) && !/[\\/]$/.test(path),
    'Expected a SQLite file path',
  ).default('./data/arena.sqlite'),
});

export class ConfigurationError extends Error {}

export function parseEnv(input: Record<string, string | undefined>) {
  const result = envSchema.safeParse(input);
  if (!result.success) {
    const fields = [...new Set(result.error.issues.map((issue) => issue.path[0]))];
    // Field names only: never echo rejected values or the full environment.
    throw new ConfigurationError(`Invalid configuration: ${fields.join(', ')}`);
  }
  return { ...result.data, DATABASE_PATH: resolve(PROJECT_ROOT, result.data.DATABASE_PATH) };
}

export type ServerConfig = ReturnType<typeof parseEnv>;
