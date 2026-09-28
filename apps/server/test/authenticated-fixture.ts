import type { ServerConfig } from '../src/env.ts';
import { parseEnv } from '../src/env.ts';
import { buildApp as rawApp } from '../src/app.ts';
import type { InjectOptions } from 'fastify';
import { AccessClient, testPasswordHash } from './access-client.ts';

// Existing G2/G5/G6 functional suites now use TWO explicit cookie jars. No bypass in buildApp.
// Restart callers must hand back the same jars, just like the browser retaining its cookie.
export async function buildApp(config: Pick<ServerConfig, 'NODE_ENV' | 'HOST' | 'PORT' | 'DATABASE_PATH'>,
  options: Parameters<typeof rawApp>[1], jars?: { player: AccessClient; admin: AccessClient }) {
  const app = await rawApp(parseEnv({ ...config, PORT: String(config.PORT), ADMIN_PASSWORD_HASH: testPasswordHash }), options);
  if (!jars) {
    jars = { player: new AccessClient(app), admin: new AccessClient(app) };
    for (const client of [jars.player, jars.admin]) {
      if ((await client.bootstrap()).statusCode !== 200) throw new Error('Fixture bootstrap failed');
    }
    if ((await jars.admin.login()).statusCode !== 200) throw new Error('Fixture admin authentication failed');
  } else { jars.player.app = app; jars.admin.app = app; }
  const savedJars = jars;
  return {
    raw: app, jars,
    inject(input: string | InjectOptions) {
      const url = typeof input === 'string' ? input : input.url ?? '';
      return ((typeof url === 'string' ? url : url.pathname).startsWith('/api/admin/') ? savedJars.admin : savedJars.player).send(input);
    },
    close: () => app.close(),
  };
}
