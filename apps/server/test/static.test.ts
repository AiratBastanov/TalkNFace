import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { buildApp } from '../src/app.ts';
import { openDatabase } from '../src/database.ts';
import { parseEnv } from '../src/env.ts';
import { WEB_ROOT } from '../src/paths.ts';
import { temporaryDatabase } from './helpers.ts';

describe('production static integration (run npm run build first)', () => {
  it('serves the real built entry and assets alongside JSON health', async () => {
    expect(existsSync(join(WEB_ROOT, 'index.html'))).toBe(true);
    const temp = temporaryDatabase();
    const app = await buildApp(parseEnv({ NODE_ENV: 'production', DATABASE_PATH: temp.filename }));
    try {
      const page = await app.inject('/');
      expect(page.statusCode).toBe(200);
      expect(page.headers['content-type']).toContain('text/html');
      expect(page.body).toContain('Арена переговоров');
      const asset = page.body.match(/src="(\/assets\/[^\"]+\.js)"/)?.[1];
      expect(asset).toBeDefined();
      if (!asset) throw new Error('Built JavaScript asset missing');
      const javascript = await app.inject(asset);
      expect(javascript.statusCode).toBe(200);
      expect(javascript.headers['content-type']).toMatch(/javascript/);
      const health = await app.inject({ url: '/health', headers: { accept: 'text/html' } });
      expect(health.statusCode).toBe(200);
      expect(health.headers['content-type']).toContain('application/json');
      expect(health.json()).toEqual({ status: 'ok' });
      const navigation = await app.inject({ url: '/foundation/check', headers: { accept: 'text/html' } });
      expect(navigation.statusCode).toBe(200);
      expect(navigation.body).toBe(page.body);
      for (const url of ['/api', '/api/unknown', '/%61pi/unknown', '/ready/missing', '/assets/missing.js']) {
        const response = await app.inject({ url, headers: { accept: 'text/html' } });
        expect(response.statusCode, url).toBe(404);
        expect(response.headers['content-type'], url).toContain('application/json');
      }
      expect((await app.inject({ method: 'POST', url: '/unknown', headers: { accept: 'text/html' } })).statusCode).toBe(404);
    } finally { await app.close(); temp.cleanup(); }
  });

  it('fails closed and releases SQLite when the production build is missing', async () => {
    const temp = temporaryDatabase();
    const database = openDatabase(temp.filename);
    try {
      await expect(buildApp(parseEnv({ NODE_ENV: 'production', DATABASE_PATH: temp.filename }), {
        database, webRoot: join(temp.directory, 'missing-build'),
      })).rejects.toThrow('Production assets are missing');
      expect(database.open).toBe(false);
    } finally { if (database.open) database.close(); temp.cleanup(); }
  });
});
