import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { hashPassword } from '../apps/server/src/access/password.ts';
import { checkPasswordLength, readAdminPassword } from './password-input.mjs';
if (process.versions.node.split('.')[0] !== '24') throw new Error('Node 24 is required.');
process.chdir(fileURLToPath(new URL('../', import.meta.url)));
if (existsSync('.env')) process.loadEnvFile('.env');
try {
  if (!process.env.ADMIN_PASSWORD_HASH) {
    const password = await readAdminPassword(); checkPasswordLength(password);
    process.env.ADMIN_PASSWORD_HASH = await hashPassword(password);
  }
  // Owner shortcut always uses loopback. npm start exposes the other explicit profiles.
  const port = process.env.PORT ?? '3000';
  if (!/^\d+$/.test(port) || Number(port) < 1 || Number(port) > 65535) throw new Error('Invalid port');
  Object.assign(process.env, { ACCESS_PROFILE: 'local', HOST: '127.0.0.1', PORT: port, APP_ORIGIN: `http://127.0.0.1:${port}` });
  process.env.DATABASE_PATH ??= '.tmp/owner-app-demo.sqlite';
  console.log(`Open http://127.0.0.1:${port}/admin`);
  await import('./start.mjs');
} catch {
  console.error('Local demo could not start. Use Node 24, npm run build, a 12-256 character password and an available port 3000.');
  process.exitCode = 1;
}
