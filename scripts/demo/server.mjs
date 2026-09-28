// Production entry used only by the Windows launcher. No .env/global deployment overrides.
import fs from 'node:fs';
import { createServer } from 'node:net';
import { root, pipe, data, stateFile, databaseFile, safe, safeDatabase, config, writeJson, friendly } from './common.mjs';
import { buildApp } from '../../apps/server/dist/app.js';
import { parseEnv } from '../../apps/server/dist/env.js';

const [portText, instance] = process.argv.slice(2), port = Number(portText);
let app, stopping = false, status = 'starting';
const info = () => ({ root, instance, port, pid: process.pid, status, nodeEnv: process.env.NODE_ENV });
const manager = createServer(socket => {
  socket.setTimeout(2000, () => socket.destroy());
  let input = '';
  socket.on('error', () => {});
  socket.on('data', chunk => {
    input += chunk;
    if (input.length > 16) return socket.destroy();
    if (input.includes('\n')) {
      const command = input.trim();
      if (!['status', 'stop'].includes(command)) return socket.destroy();
      socket.end(JSON.stringify(info()));
      if (command === 'stop') void shutdown();
    }
  });
});
async function shutdown() {
  if (stopping) return; stopping = true; status = 'stopping';
  const watchdog = setTimeout(() => process.exit(1), 10_000).unref();
  try {
    if (app) await app.close();
    await new Promise(resolve => manager.close(resolve));
    if (fs.existsSync(stateFile) && JSON.parse(fs.readFileSync(safe(stateFile), 'utf8')).instance === instance) fs.unlinkSync(safe(stateFile));
  } catch { console.error('Demo shutdown failed. SQLite remains on disk; inspect -Status before restarting.'); process.exitCode = 1; }
  finally { clearTimeout(watchdog); }
}
process.once('SIGINT', shutdown); process.once('SIGTERM', shutdown);
try {
  if (process.version !== 'v24.21.0' || !/^[0-9a-f-]{36}$/.test(instance ?? '') || !Number.isInteger(port) || port < 1024 || port > 65535) throw Error('Invalid managed demo invocation. Use windows-demo.ps1 -Start.');
  safe(data); safeDatabase(databaseFile); const credentials = config();
  await new Promise((resolve, reject) => { manager.once('error', reject); manager.listen(pipe, resolve); });
  const cfg = parseEnv({ NODE_ENV: 'production', HOST: '127.0.0.1', PORT: String(port), ACCESS_PROFILE: 'local',
    APP_ORIGIN: `http://127.0.0.1:${port}`, DATABASE_PATH: databaseFile, ADMIN_PASSWORD_HASH: credentials.adminPasswordHash });
  app = await buildApp(cfg, { logger: true });
  await app.listen({ host: '127.0.0.1', port });
  status = 'ready'; writeJson(stateFile, { ...info(), startedAt: new Date().toISOString() });
} catch (error) {
  console.error('Demo startup: ' + friendly(error)); process.exitCode = 1; await shutdown();
}
