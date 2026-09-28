import { resolve } from 'node:path';
import { z } from 'zod';
import { PROJECT_ROOT } from './paths.ts';
import { validPasswordHash } from './access/password.ts';

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  HOST: z.string().trim().regex(/^[A-Za-z0-9.:-]+$/).default('127.0.0.1'),
  PORT: z.string().regex(/^\d+$/).transform(Number).pipe(z.number().int().min(1).max(65535)).default(3000),
  ACCESS_PROFILE: z.enum(['local', 'public']).default('local'),
  APP_ORIGIN: z.string().optional(),
  ADMIN_PASSWORD_HASH: z.string().refine(validPasswordHash).optional(),
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
  const data = result.data;
  const loopback = (host: string) => ['127.0.0.1', 'localhost', '::1', '[::1]'].includes(host);
  const host = data.HOST.includes(':') ? `[${data.HOST}]` : data.HOST;
  let origin: URL;
  try {
    if (data.ACCESS_PROFILE === 'public' && !data.APP_ORIGIN) throw new Error();
    origin = new URL(data.APP_ORIGIN ?? `http://${host}:${data.PORT}`);
    if (origin.username || origin.password || origin.search || origin.hash || origin.pathname !== '/') throw new Error();
    if (data.ACCESS_PROFILE === 'local') {
      if (!loopback(data.HOST) || !loopback(origin.hostname) || origin.protocol !== 'http:') throw new Error();
    } else if (origin.protocol !== 'https:' || loopback(origin.hostname)) throw new Error();
  } catch {
    throw new ConfigurationError('Invalid configuration: ACCESS_PROFILE, APP_ORIGIN, HOST');
  }
  return { ...data, APP_ORIGIN: origin.origin, DATABASE_PATH: resolve(PROJECT_ROOT, data.DATABASE_PATH) };
}

export type ServerConfig = ReturnType<typeof parseEnv>;
