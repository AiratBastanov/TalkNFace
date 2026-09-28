// Bounded destructive/failure fixtures are confined to this gate's ignored application data.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { randomBytes, randomUUID, createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { createServer } from 'node:net';
import { once } from 'node:events';
import { setTimeout as delay } from 'node:timers/promises';

const root = process.cwd(), node = process.execPath, started = Date.now();
const results = []; let current = '';
const from = process.argv[process.argv.indexOf('--from') + 1];
let reached = !process.argv.includes('--from');
const suite = path.join(root, '.tmp', 'clean-demo-failures-' + randomUUID());
fs.mkdirSync(suite, { recursive: true });
const state = path.join(root, '.local/arena-demo'), config = path.join(root, '.local/arena-config/admin.json');
const Database = createRequire(path.join(root, 'apps/server/package.json'))('better-sqlite3');
const sha = p => createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const safeCommandPrefix = ['-NoProfile', '-ExecutionPolicy', 'Bypass'];
async function invoke(base, args, { localRuntime = true, offline = false, input = '', timeout = 35_000 } = {}) {
  const command = ['-File', '.\\scripts\\windows-demo.ps1', ...args, ...(localRuntime ? ['-NodePath', node] : [])];
  const psQuote = s => "'" + s.replaceAll("'", "''") + "'";
  const actual = offline ? ['-Command', '[Net.WebRequest]::DefaultWebProxy = New-Object Net.WebProxy(\'http://127.0.0.1:1\'); & ' +
    [path.join(base, 'scripts/windows-demo.ps1'), ...args, ...(localRuntime ? ['-NodePath', node] : [])].map(s => /^-[A-Za-z]+$/.test(s) ? s : psQuote(s)).join(' ')] : command;
  return new Promise((resolve, reject) => {
    const child = spawn('powershell.exe', [...safeCommandPrefix, ...actual], { cwd: base, windowsHide: true,
      env: { ...process.env, ...(offline ? { HTTPS_PROXY: 'http://127.0.0.1:1', HTTP_PROXY: 'http://127.0.0.1:1', NO_PROXY: '' } : {}) }, stdio: ['pipe', 'pipe', 'pipe'] });
    let output = ''; const timer = setTimeout(() => { child.kill(); reject(Error('Failure case command exceeded fixed budget')); }, timeout);
    child.stdout.on('data', b => { output += b; }); child.stderr.on('data', b => { output += b; });
    child.once('error', reject); child.once('exit', code => {
      clearTimeout(timer); child.stdout.destroy(); child.stderr.destroy(); resolve({ code, output });
    }); child.stdin.end(input);
  });
}
function mini(name) {
  const dir = path.join(suite, name);
  const files = ['scripts/windows-demo.ps1', 'scripts/check-runtime.mjs', 'scripts/demo/common.mjs', 'scripts/demo/cli.mjs', 'scripts/demo/server.mjs',
    'apps/server/src/access/password.ts', 'package.json', 'package-lock.json', 'apps/server/package.json', 'apps/web/package.json',
    'packages/contracts/package.json', 'packages/domain/package.json', 'packages/scenarios/package.json', 'apps/web/index.html', 'apps/web/vite.config.ts'];
  for (const relative of files) { const to = path.join(dir, relative); fs.mkdirSync(path.dirname(to), { recursive: true }); fs.copyFileSync(path.join(root, relative), to); }
  // Only source files, never runtime/dependencies/cache/DB/config.
  for (const ws of ['apps/server', 'apps/web', 'packages/contracts', 'packages/domain', 'packages/scenarios']) {
    fs.cpSync(path.join(root, ws, 'src'), path.join(dir, ws, 'src'), { recursive: true });
  }
  return dir;
}
async function test(name, fn) {
  if (!reached && !name.startsWith(from)) return;
  reached = true;
  current = name; const time = Date.now();
  try { await fn(); results.push({ name, status: 'passed', seconds: (Date.now() - time) / 1000 }); console.log('PASS ' + name); }
  catch (e) { results.push({ name, status: 'failed', seconds: (Date.now() - time) / 1000 }); throw e; }
  finally { fs.writeFileSync(path.join(root, '.tools/clean-failure-tests.json'), JSON.stringify({ cases: results, seconds: (Date.now() - started) / 1000 }, null, 2)); }
}
async function rejected(base, args, pattern, opts) { const r = await invoke(base, args, opts); assert.equal(r.code, 1, 'Expected failure'); assert.match(r.output, pattern); assert(!r.output.includes('scrypt$'), 'No config hash in diagnostics'); }
async function temporarily(file, bytes, fn) {
  const previous = fs.existsSync(file) ? fs.readFileSync(file) : null;
  if (bytes === null) fs.unlinkSync(file); else fs.writeFileSync(file, bytes);
  try { await fn(); } finally { if (previous) fs.writeFileSync(file, previous); else if (fs.existsSync(file)) fs.unlinkSync(file); }
}
const watchdog = setTimeout(() => { console.error('Failure group exceeded 180s'); process.exit(1); }, 180_000).unref();
try {
  assert.equal((await invoke(root, ['-Stop'])).code, 0);
  const originalConfig = sha(config), dbFile = path.join(state, 'arena.sqlite');
  const sentinel = randomUUID(); let db = new Database(dbFile); db.prepare('INSERT INTO foundation_metadata(key,value) VALUES (?,?)').run(sentinel, 'preserve'); db.close();
  await test('pristine Status is read-only and does not bootstrap', async () => {
    const dir = mini('status'); assert.equal((await invoke(dir, ['-Status'], { localRuntime: false })).code, 0);
    assert(!fs.existsSync(path.join(dir, '.local')) && !fs.existsSync(path.join(dir, '.tools')));
  });
  await test('explicit unsupported Node is rejected before installation', async () => {
    const found = spawnSync('where.exe', ['node.exe'], { encoding: 'utf8', windowsHide: true }).stdout.trim().split(/\r?\n/);
    const wrong = found.find(p => spawnSync(p, ['--version'], { encoding: 'utf8', windowsHide: true }).stdout.trim() !== 'v24.21.0');
    assert(wrong, 'This environment must provide an unsupported Node for this negative test');
    await rejected(mini('node-major'), ['-Prepare', '-NodePath', wrong], /Unsupported -NodePath/, { localRuntime: false });
  });
  await test('no network on first Node acquisition gives actionable error', async () => {
    await rejected(mini('node-offline'), ['-Prepare', '-PasswordFromStdin'], /Node download failed.*nodejs.org/s, { localRuntime: false, offline: true, input: randomBytes(24).toString('hex') });
  });
  await test('manifest/lock disagreement fails without mutation', async () => {
    const dir = mini('lock-disagreement'), file = path.join(dir, 'package.json'), p = JSON.parse(fs.readFileSync(file)); p.devDependencies.vite = '1.0.0'; fs.writeFileSync(file, JSON.stringify(p));
    const before = sha(path.join(dir, 'package-lock.json'));
    await rejected(dir, ['-Prepare', '-PasswordFromStdin'], /package.json and package-lock.json disagree/, { input: randomBytes(24).toString('hex') });
    assert.equal(sha(path.join(dir, 'package-lock.json')), before); assert(!fs.existsSync(path.join(dir, 'node_modules')));
  });
  await test('empty-cache npm ci network failure is bounded and preserves source/config', async () => {
    const dir = mini('npm-offline'), lock = sha(path.join(dir, 'package-lock.json'));
    await rejected(dir, ['-Prepare', '-PasswordFromStdin'], /npm ci failed.*saved demo data are preserved/s, { offline: true, input: randomBytes(24).toString('hex'), timeout: 35_000 });
    assert.equal(sha(path.join(dir, 'package-lock.json')), lock); assert(fs.existsSync(path.join(dir, '.local/arena-config/admin.json')));
  });
  await test('incomplete local runtime is refused', async () => {
    const dir = mini('incomplete-runtime'); fs.mkdirSync(path.join(dir, '.tools/arena-runtime/node-v24.21.0-win-x64'), { recursive: true });
    await rejected(dir, ['-Prepare'], /verification ZIP is missing/, { localRuntime: false });
  });
  await test('corrupt Node archive is refused before extraction/execution', async () => {
    const dir = mini('corrupt-archive'); fs.mkdirSync(path.join(dir, '.tools/arena-runtime/node-v24.21.0-win-x64'), { recursive: true });
    fs.writeFileSync(path.join(dir, '.tools/arena-runtime/node-v24.21.0-win-x64.zip'), 'not a release');
    await rejected(dir, ['-Prepare'], /checksum failed/, { localRuntime: false });
  });
  await test('modified previously verified runtime file is detected', async () => {
    const file = path.join(root, '.tools/arena-runtime/node-v24.21.0-win-x64/README.md');
    await temporarily(file, 'corrupted runtime file', () => rejected(root, ['-Verify'], /Corrupted local Node runtime/, { localRuntime: false }));
  });
  await test('missing admin config fails Start without touching DB', async () => {
    const before = sha(dbFile); await temporarily(config, null, () => rejected(root, ['-Start', '-Port', '3100'], /config is missing or malformed/)); assert.equal(sha(dbFile), before);
  });
  await test('malformed admin config is not overwritten by Prepare', async () => {
    await temporarily(config, '{broken:secret}', async () => { await rejected(root, ['-Prepare'], /config is missing or malformed/); assert.equal(fs.readFileSync(config, 'utf8'), '{broken:secret}'); });
  });
  await test('interrupted first preparation refuses Start and preserves DB', async () => {
    await temporarily(path.join(state, 'prepared.json'), null, () => rejected(root, ['-Start', '-Port', '3100'], /Preparation is missing or interrupted/));
  });
  await test('interrupted build cannot reuse old preparation marker', async () => {
    await temporarily(path.join(root, 'apps/server/dist/app.js'), '// partial build', () => rejected(root, ['-Start', '-Port', '3100'], /build changed or a build was interrupted/));
  });
  await test('occupied port fails without stopping its listener', async () => {
    const listener = createServer(); listener.listen(0, '127.0.0.1'); await once(listener, 'listening');
    try { await rejected(root, ['-Start', '-Port', String(listener.address().port)], /occupied or unavailable/); assert(listener.listening); }
    finally { await new Promise(resolve => listener.close(resolve)); }
  });
  await test('locked DB gives safe startup error and is not reset', async () => {
    db = new Database(dbFile); db.exec('BEGIN IMMEDIATE');
    try { await rejected(root, ['-Start', '-Port', '3100'], /Production startup failed/); }
    finally { db.exec('ROLLBACK'); db.close(); }
    assert.match(fs.readFileSync(path.join(state, 'server.log'), 'utf8'), /locked or inaccessible/);
  });
  await test('inaccessible DB path fails without deleting anything', async () => {
    const moved = path.join(state, 'inaccessible-test.sqlite'); fs.renameSync(dbFile, moved); fs.mkdirSync(dbFile);
    try { await rejected(root, ['-Verify'], /locked or inaccessible|Cannot open database/); }
    finally { fs.rmdirSync(dbFile); fs.renameSync(moved, dbFile); }
  });
  await test('reset refuses junction escape and preserves outside sentinel', async () => {
    const dir = mini('junction'), outside = path.join(suite, 'outside-preserve'); fs.mkdirSync(outside); fs.writeFileSync(path.join(outside, 'sentinel'), 'unchanged');
    fs.mkdirSync(path.join(dir, '.local')); fs.symlinkSync(outside, path.join(dir, '.local/arena-demo'), 'junction');
    await rejected(dir, ['-ResetDemoData'], /Symlink\/junction/); assert.equal(fs.readFileSync(path.join(outside, 'sentinel'), 'utf8'), 'unchanged');
  });
  await test('stale PID Status/Stop never signal an unrelated process', async () => {
    const file = path.join(state, 'server.json');
    await temporarily(file, JSON.stringify({ pid: process.pid, instance: randomUUID() }), async () => {
      const before = sha(file); assert.match((await invoke(root, ['-Status'])).output, /Stale status file ignored/); assert.equal(sha(file), before);
      assert.equal((await invoke(root, ['-Stop'])).code, 0); process.kill(process.pid, 0);
    });
  });
  await test('unexpected task-owned server termination recovers persisted SQLite', async () => {
    assert.equal((await invoke(root, ['-Start', '-Port', '3100'])).code, 0);
    const own = JSON.parse(fs.readFileSync(path.join(state, 'server.json'))); assert.equal(own.root.toLowerCase(), root.toLowerCase()); assert(own.instance && own.pid !== process.pid);
    process.kill(own.pid); await delay(200);
    assert.equal((await invoke(root, ['-Start', '-Port', '3100'])).code, 0);
    assert.equal((await fetch('http://127.0.0.1:3100/ready')).status, 200);
    assert.equal((await invoke(root, ['-Stop'])).code, 0);
    db = new Database(dbFile); try { assert.equal(db.prepare('SELECT value FROM foundation_metadata WHERE key=?').get(sentinel).value, 'preserve'); } finally { db.close(); }
  });
  assert.equal(sha(config), originalConfig);
  await test('explicit reset preserves password and verified previous-state backup', async () => {
    const backups = path.join(state, 'backups'); const before = fs.existsSync(backups) ? fs.readdirSync(backups) : [];
    const reset = await invoke(root, ['-ResetDemoData']); assert.equal(reset.code, 0); assert(reset.output.includes(dbFile)); assert.equal(sha(config), originalConfig);
    const added = fs.readdirSync(backups).filter(n => !before.includes(n) && n.startsWith('before-reset-') && n.endsWith('.sqlite')); assert.equal(added.length, 1);
    db = new Database(path.join(backups, added[0]), { readonly: true }); try { assert.equal(db.prepare('SELECT value FROM foundation_metadata WHERE key=?').get(sentinel).value, 'preserve'); assert.equal(db.pragma('integrity_check', { simple: true }), 'ok'); } finally { db.close(); }
    db = new Database(dbFile); try { assert.equal(db.prepare('SELECT count(*) n FROM foundation_metadata').get().n, 0); } finally { db.close(); }
  });
  console.log(`${results.length} unique failure/lifecycle cases passed in ${((Date.now() - started) / 1000).toFixed(3)}s`);
} catch (e) {
  console.error('Failure group stopped at: ' + current + ' (' + e.name + ')');
  console.error((e.stack ?? '').split('\n').filter(line => /failures\.mjs:\d/.test(line)).join('\n')); process.exitCode = 1;
} finally { clearTimeout(watchdog); await invoke(root, ['-Stop']).catch(() => {}); }
