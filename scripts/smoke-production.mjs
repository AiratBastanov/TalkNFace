import './check-runtime.mjs';
import assert from 'node:assert/strict';
import { fork } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { once } from 'node:events';
import { existsSync, mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openDatabase } from '../apps/server/dist/database.js';

const root = fileURLToPath(new URL('../', import.meta.url));
const tempRoot = resolve(root, '.tmp');
mkdirSync(tempRoot, { recursive: true });
const directory = mkdtempSync(join(tempRoot, 'g0-production-'));
const databasePath = join(directory, 'runtime.sqlite');
const children = new Set();
const deadline = setTimeout(() => {
  console.error('Production smoke exceeded its 60-second budget');
  for (const child of children) child.kill();
  process.exitCode = 1;
}, 55_000);

async function unusedPort() {
  const probe = createServer();
  probe.listen(0, '127.0.0.1');
  await once(probe, 'listening');
  const { port } = probe.address();
  await new Promise((resolve, reject) => probe.close(error => error ? reject(error) : resolve()));
  return port;
}

const port = await unusedPort();
const origin = `http://127.0.0.1:${port}`;
// Construct a minimal environment: no inherited AI credentials or NODE_OPTIONS.
const childEnv = { PATH: process.env.PATH, SystemRoot: process.env.SystemRoot, WINDIR: process.env.WINDIR,
  NODE_ENV: 'production', HOST: '127.0.0.1', PORT: String(port), DATABASE_PATH: databasePath };

async function start() {
  // This is exactly the production entry used by npm start, in a separate real process.
  const child = fork(new URL('./start.mjs', import.meta.url), [], {
    cwd: root, env: childEnv, execArgv: [], windowsHide: true, stdio: ['ignore', 'pipe', 'pipe', 'ipc'],
  });
  children.add(child);
  let output = '';
  child.stdout.on('data', chunk => { output += chunk; });
  child.stderr.on('data', chunk => { output += chunk; });
  const exit = once(child, 'exit');
  child.once('exit', () => children.delete(child));
  const message = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Production startup timed out')), 10_000);
    child.once('message', message => { clearTimeout(timer); resolve(message); });
    child.once('error', error => { clearTimeout(timer); reject(error); });
    child.once('exit', code => { clearTimeout(timer); reject(new Error(`Production exited early: ${code}; ${output}`)); });
  });
  assert.equal(message.type, 'started');
  assert.equal(message.node, process.version);
  return { child, exit, output: () => output };
}

async function request(path) {
  return fetch(origin + path, { signal: AbortSignal.timeout(5000) });
}

async function endpoints() {
  const page = await request('/');
  assert.equal(page.status, 200);
  assert.match(page.headers.get('content-type'), /text\/html/);
  const html = await page.text();
  assert.match(html, /Арена переговоров/);
  const asset = html.match(/src="(\/assets\/[^\"]+\.js)"/)?.[1];
  assert.ok(asset, 'Real Vite production asset is linked');
  const javascript = await request(asset);
  assert.equal(javascript.status, 200);
  assert.match(javascript.headers.get('content-type'), /javascript/);
  await javascript.arrayBuffer();
  for (const [path, status] of [['/health', 'ok'], ['/ready', 'ready']]) {
    const response = await request(path);
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { status });
  }
  const missing = await request('/api/unknown');
  assert.equal(missing.status, 404);
  assert.deepEqual(await missing.json(), { status: 'not_found' });
}

async function stop(instance) {
  instance.child.send('shutdown');
  const timer = setTimeout(() => instance.child.kill(), 12_000);
  const [code, signal] = await instance.exit;
  clearTimeout(timer);
  assert.equal(code, 0, instance.output());
  assert.equal(signal, null);
  assert.match(instance.output(), /database.closed/);
  assert.equal(existsSync(databasePath + '-wal'), false, 'Final SQLite connection closed and WAL checkpointed');
  assert.equal(existsSync(databasePath + '-shm'), false);
}

try {
  const first = await start();
  await endpoints();
  const sentinel = randomUUID();
  let db = openDatabase(databasePath);
  try { db.prepare('INSERT INTO foundation_metadata (key, value) VALUES (?, ?)').run('g0-runtime-smoke', sentinel); }
  finally { db.close(); }
  await stop(first);
  const second = await start();
  assert.notEqual(first.child.pid, second.child.pid);
  await endpoints();
  db = openDatabase(databasePath);
  try {
    assert.deepEqual(db.prepare('SELECT value FROM foundation_metadata WHERE key = ?').get('g0-runtime-smoke'), { value: sentinel });
    assert.deepEqual(db.prepare('SELECT version FROM schema_migrations ORDER BY version').all(), [{ version: 1 }, { version: 2 }]);
  } finally { db.close(); }
  await stop(second);
  console.log(JSON.stringify({ result: 'PASS', runtime: process.version, platform: process.platform, arch: process.arch,
    starts: 2, cleanShutdowns: 2, sameOriginSpaAndAssets: true, health: true, ready: true,
    persistedSentinel: true, nonDestructiveMigration: true, aiCredentials: 'NONE', orphanProcesses: children.size }));
} finally {
  clearTimeout(deadline);
  for (const child of children) {
    if (child.connected) child.send('shutdown');
    const timer = setTimeout(() => child.kill(), 10_000);
    await once(child, 'exit');
    clearTimeout(timer);
  }
  if (!resolve(directory).startsWith(tempRoot + sep)) throw new Error('Unsafe smoke cleanup path');
  rmSync(directory, { recursive: true, force: true });
}
