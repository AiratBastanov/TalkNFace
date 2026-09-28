import './check-runtime.mjs';
import { fork } from 'node:child_process';
import { once } from 'node:events';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import { parseEnv } from '../apps/server/src/env.ts';

const root = fileURLToPath(new URL('../', import.meta.url));
const envFile = new URL('../.env', import.meta.url);
if (existsSync(envFile)) process.loadEnvFile(envFile);
// Browser uses Vite's loopback origin; the backend never accepts a wildcard Origin.
process.env.APP_ORIGIN ??= 'http://127.0.0.1:5173';
const config = parseEnv({ ...process.env, NODE_ENV: 'development' });
const backend = fork(new URL('../apps/server/src/main.ts', import.meta.url), [], {
  cwd: root, execArgv: [], env: { ...process.env, NODE_ENV: 'development' },
  stdio: ['ignore', 'inherit', 'inherit', 'ipc'], windowsHide: true,
});
const exited = once(backend, 'exit');
let vite;
let stopping = false;
async function shutdown() {
  if (stopping) return;
  stopping = true;
  await vite?.close();
  if (backend.exitCode === null && backend.connected) backend.send('shutdown');
  const watchdog = setTimeout(() => backend.kill(), 10_000).unref();
  await exited;
  clearTimeout(watchdog);
}
process.once('SIGINT', () => { void shutdown(); });
process.once('SIGTERM', () => { void shutdown(); });
process.on('message', (message) => { if (message === 'shutdown') void shutdown(); });
backend.once('exit', (code) => {
  if (!stopping) { process.exitCode = code || 1; void shutdown(); }
  if (process.connected) process.disconnect();
});

try {
  const host = config.HOST === '0.0.0.0' ? '127.0.0.1' : config.HOST === '::' ? '::1' : config.HOST;
  const target = `http://${host.includes(':') ? `[${host}]` : host}:${config.PORT}`;
  vite = await createServer({
    configFile: fileURLToPath(new URL('../apps/web/vite.config.ts', import.meta.url)),
    server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy: { '/health': target, '/ready': target, '/api': target } },
  });
  await vite.listen();
  vite.printUrls();
} catch {
  console.error('Development startup failed; check HOST/PORT and port 5173.');
  process.exitCode = 1;
  await shutdown();
}
