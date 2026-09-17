import { describe, expect, it } from 'vitest';
import { buildApp } from '../src/app.ts';
import { openDatabase } from '../src/database.ts';
import { parseEnv } from '../src/env.ts';
import { temporaryDatabase } from './helpers.ts';

describe('Fastify lifecycle', () => {
  it('serves minimal liveness and genuine readiness; close releases the database', async () => {
    const temp = temporaryDatabase();
    const database = openDatabase(temp.filename);
    const app = await buildApp(parseEnv({ NODE_ENV: 'test', DATABASE_PATH: temp.filename }), { database });
    try {
      const health = await app.inject('/health');
      expect(health.statusCode).toBe(200);
      expect(health.json()).toEqual({ status: 'ok' });
      const ready = await app.inject('/ready');
      expect(ready.statusCode).toBe(200);
      expect(ready.json()).toEqual({ status: 'ready' });
    } finally { await app.close(); temp.cleanup(); }
    expect(database.open).toBe(false);
  });

  it('reports a database failure as 503 while process liveness stays healthy', async () => {
    const temp = temporaryDatabase();
    const database = openDatabase(temp.filename);
    const app = await buildApp(parseEnv({ NODE_ENV: 'test', DATABASE_PATH: temp.filename }), { database });
    database.close();
    try {
      const ready = await app.inject('/ready');
      expect(ready.statusCode).toBe(503);
      expect(ready.json()).toEqual({ status: 'not_ready' });
      expect((await app.inject('/health')).statusCode).toBe(200);
    } finally { await app.close(); temp.cleanup(); }
  });
});
