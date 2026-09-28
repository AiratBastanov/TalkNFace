import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { createServer } from 'node:net';
import { randomUUID } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';
import { hashPassword } from '../../apps/server/src/access/password.ts';
import { root, data, configFile, databaseFile, toolsDir, preparedFile, stateFile, safe, safeDatabase, json, writeJson,
  sourceDigest, buildDigest, checkLock, checkTree, config, control, requireStopped, friendly } from './common.mjs';

process.chdir(root);
const [action, argument] = process.argv.slice(2);
const npm = path.join(path.dirname(process.execPath), 'node_modules/npm/bin/npm-cli.js');
const stageTimes = {};
const started = Date.now();
// All operations have finite budgets; the detached production server has its own lifecycle.
const budget = action === 'prepare' ? 650_000 : ['backup', 'restore', 'reset'].includes(action) ? 60_000 : 25_000;
const watchdog = setTimeout(() => { console.error('Demo operation exceeded its fixed time budget. Inspect -Status and retry the affected command. Database/configuration were not automatically deleted.'); process.exit(1); }, budget).unref();
function env() {
  const result = { ...process.env };
  for (const k of Object.keys(result)) if (/^npm_config_|^node_options$|^node_path$|^admin_password_hash$/i.test(k)) delete result[k];
  result.PATH = path.dirname(process.execPath) + path.delimiter + process.env.PATH;
  result.npm_config_cache = path.join(root, '.tools/arena-npm-cache');
  result.npm_config_userconfig = path.join(toolsDir, 'empty-user.npmrc');
  result.npm_config_globalconfig = path.join(toolsDir, 'empty-global.npmrc');
  result.npm_config_registry = 'https://registry.npmjs.org/';
  result.npm_config_audit = 'false'; result.npm_config_fund = 'false';
  result.npm_config_fetch_retries = '1'; result.npm_config_fetch_timeout = '60000';
  result.npm_config_update_notifier = 'false'; result.NODE_ENV = 'development';
  return result;
}
async function run(label, args, timeout, cwd = root, capture = false) {
  const time = Date.now(); console.log(label + '...');
  const result = await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, args, { cwd, env: env(), windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let output = ''; let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      // This exact newly-created child owns the subprocess tree. Never read a PID file to kill.
      const killer = spawn('taskkill.exe', ['/pid', String(child.pid), '/t', '/f'], { windowsHide: true, stdio: 'ignore' });
      killer.on('error', () => child.kill());
    }, timeout);
    child.stdout.on('data', b => { if (capture) output += b; else process.stdout.write(b); });
    // npm/prebuild logs contain no credentials: ambient npm config is disabled.
    child.stderr.on('data', b => { if (!capture) process.stderr.write(b); });
    child.once('error', () => { clearTimeout(timer); reject(Error(label + ' could not start. Retry -Prepare; saved data is safe.')); });
    child.once('close', code => { clearTimeout(timer); code === 0 && !timedOut ? resolve(output) : reject(Error(label + (timedOut ? ' exceeded its time budget.' : ' failed.') + ' Allow HTTPS to registry.npmjs.org and GitHub release assets, then retry -Prepare. No Python/build-tool fallback is used. Source/lockfile and saved demo data are preserved.')); });
  });
  stageTimes[label] = (Date.now() - time) / 1000; console.log(`${label}: ${stageTimes[label].toFixed(3)}s`); return result;
}
const driver = () => createRequire(path.join(root, 'apps/server/package.json'))('better-sqlite3');
function integrity(db) {
  if (db.pragma('integrity_check', { simple: true }) !== 'ok' || db.pragma('foreign_key_check').length) throw Error('SQLite integrity check failed. Keep the current DB; restore a verified backup while stopped.');
  const versions = db.prepare('SELECT version FROM schema_migrations ORDER BY version').all().map(r => r.version);
  if (versions.join(',') !== '1,2,3,4,5') throw Error('Unsupported demo DB schema. Use a matching source version; the database was not reset.');
}
async function initDatabase() {
  const { openDatabase } = await import('../../apps/server/dist/database.js');
  const db = openDatabase(safeDatabase(databaseFile)); try { integrity(db); } finally { db.close(); }
}
function verifyPrepared() {
  config();
  let p; try { p = json(preparedFile); } catch { throw Error('Preparation is missing or interrupted. Run -Prepare to install/build again. Existing DB and administrator config are preserved.'); }
  if (p.node !== process.version || p.source !== sourceDigest() || p.build !== buildDigest()) throw Error('Source/runtime/build changed or a build was interrupted. Run -Prepare before -Start; your DB and password are preserved.');
  const count = checkTree();
  const Database = driver(), db = new Database(safeDatabase(databaseFile), { readonly: true, fileMustExist: true, timeout: 5000 });
  try { integrity(db); } finally { db.close(); }
  return count;
}
async function backupTo(id) {
  const dest = safe(path.join(data, 'backups', id + '.sqlite'));
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  const Database = driver(), source = new Database(safeDatabase(databaseFile), { readonly: true, fileMustExist: true, timeout: 5000 });
  const temp = safe(dest + '.partial'), deadline = Date.now() + 50_000;
  try {
    integrity(source);
    await source.backup(safeDatabase(temp), { progress: () => { if (Date.now() > deadline) throw Error('Backup exceeded 50 seconds; existing database and previous backups are safe.'); return 256; } });
    const checked = new Database(safeDatabase(temp), { readonly: true, fileMustExist: true });
    try { integrity(checked); } finally { checked.close(); }
    fs.renameSync(temp, dest);
    console.log('Verified backup: ' + id + ' (.local/arena-demo/backups)');
    return dest;
  } finally { source.close(); }
}
const backupId = prefix => prefix + '-' + new Date().toISOString().replace(/[:.]/g, '-') + '-' + randomUUID().slice(0, 8);
async function replaceDatabase(sourceFile) {
  const Database = driver(), source = new Database(safeDatabase(sourceFile), { readonly: true, fileMustExist: true, timeout: 5000 });
  try {
    integrity(source);
    // SQLite backup API coordinates locking and WAL; never copy a live SQLite file.
    await source.backup(safeDatabase(databaseFile), { progress: () => { if (Date.now() - started > 50_000) throw Error('Restore timed out; previous DB is preserved in backups.'); return 256; } });
  } finally { source.close(); }
  const checked = new Database(databaseFile, { readonly: true, fileMustExist: true });
  try { integrity(checked); } finally { checked.close(); }
}
async function restoreWithoutRevivingAccess(sourceFile) {
  const Database = driver();
  const current = new Database(safeDatabase(databaseFile), { readonly: true, fileMustExist: true, timeout: 5000 });
  let live;
  try { live = new Map(current.prepare('SELECT * FROM access_sessions').all().map(row => [row.token_digest, row])); }
  finally { current.close(); }
  const candidate = safe(path.join(data, 'restore-' + randomUUID() + '.sqlite'));
  const source = new Database(sourceFile, { readonly: true, fileMustExist: true });
  try { await source.backup(candidate); } finally { source.close(); }
  const restored = new Database(candidate);
  try {
    const now = restored.prepare('SELECT unixepoch() n').get().n;
    restored.transaction(() => {
      for (const row of restored.prepare('SELECT * FROM access_sessions').all()) {
        const previous = live.get(row.token_digest);
        const valid = previous && previous.revoked_at === null && previous.idle_expires_at > now && previous.absolute_expires_at > now &&
          ['principal_id', 'role', 'csrf_digest', 'credential_digest', 'created_at'].every(key => previous[key] === row[key]);
        if (!valid) restored.prepare('UPDATE access_sessions SET revoked_at = COALESCE(revoked_at, ?) WHERE token_digest = ?').run(now, row.token_digest);
        else restored.prepare('UPDATE access_sessions SET idle_expires_at = min(idle_expires_at, ?), absolute_expires_at = min(absolute_expires_at, ?) WHERE token_digest = ?')
          .run(previous.idle_expires_at, previous.absolute_expires_at, row.token_digest);
      }
    }).immediate();
    integrity(restored);
  } finally { restored.close(); }
  await replaceDatabase(candidate);
  fs.unlinkSync(safe(candidate));
}
async function main() {
  if (process.version !== 'v24.21.0' || process.arch !== 'x64') throw Error('This launcher requires exact Node 24.21.0 x64. Run windows-demo.ps1 -Prepare.');
  safe(data); safe(configFile);
  if (action === 'config-check' || action === 'configure') {
    await requireStopped();
    const replace = argument === 'replace';
    if (action === 'config-check') {
      if (!replace && fs.existsSync(configFile)) { config(); console.log('Administrator config preserved.'); }
      else console.log('PASSWORD_REQUIRED');
      return;
    }
    if (!replace && fs.existsSync(configFile)) throw Error('Administrator config already exists; use -SetAdminPassword for an explicit replacement.');
    let password = ''; process.stdin.setEncoding('utf8');
    for await (const chunk of process.stdin) { password += chunk; if (password.length > 256) throw Error('Use a password of 12-256 characters. Existing config/database are unchanged.'); }
    if (password.length < 12) throw Error('Use a password of 12-256 characters. Existing config/database are unchanged.');
    writeJson(configFile, { schema: 1, adminPasswordHash: await hashPassword(password) }); password = '';
    console.log('Administrator hash saved in ignored local config. No plaintext password was saved.'); return;
  }
  if (action === 'prepare') {
    await requireStopped(); config(); checkLock();
    fs.mkdirSync(data, { recursive: true }); fs.mkdirSync(safe(toolsDir), { recursive: true });
    for (const name of ['empty-user.npmrc', 'empty-global.npmrc']) fs.writeFileSync(safe(path.join(toolsDir, name)), '');
    // A previous successful preparation cannot authorize partially replaced dependencies/builds.
    if (fs.existsSync(preparedFile)) fs.unlinkSync(safe(preparedFile));
    const before = sourceDigest();
    const installStart = Date.now();
    // Only the native prebuilt hook is needed on Windows. Disable the package's node-gyp/Python fallback.
    await run('npm ci', [npm, 'ci', '--ignore-scripts', '--include=dev', '--no-audit', '--no-fund'], 300_000);
    const prebuild = createRequire(path.join(root, 'apps/server/node_modules/better-sqlite3/package.json')).resolve('prebuild-install/bin.js');
    await run('SQLite official prebuilt', [prebuild], Math.max(1, 300_000 - (Date.now() - installStart)), path.join(root, 'apps/server/node_modules/better-sqlite3'));
    await run('dependency tree', [npm, 'ls', '--all', '--json'], 30_000, root, true);
    const count = checkTree(), Database = driver(), memory = new Database(':memory:');
    try { memory.prepare('SELECT sqlite_version()').get(); } finally { memory.close(); }
    await run('production build', [npm, 'run', 'build'], 300_000);
    await initDatabase();
    if (sourceDigest() !== before) throw Error('Source/lockfile changed during preparation. Stop and inspect checkout; saved demo data was not reset.');
    writeJson(preparedFile, { schema: 1, node: process.version, npm: '11.19.0', source: before, build: buildDigest(), dependencies: count, timings: stageTimes, preparedAt: new Date().toISOString() });
    console.log('Prepared: exact locked dependencies, native SQLite, production assets, schema 5 and administrator config. Run -Start.'); return;
  }
  if (action === 'status') {
    const live = await control();
    console.log(live ? `Demo ${live.status}: http://127.0.0.1:${live.port}/admin (managed PID ${live.pid})` : `Demo stopped.${fs.existsSync(stateFile) ? ' Stale status file ignored; no PID was signalled.' : ''}`);
    const backups = path.join(data, 'backups'); safe(backups);
    if (fs.existsSync(backups)) console.log('Backups: ' + fs.readdirSync(backups).filter(n => n.endsWith('.sqlite')).map(n => n.slice(0, -7)).join(', '));
    return;
  }
  if (action === 'stop') {
    const live = await control('stop');
    if (live) { const end = Date.now() + 12_000; while (await control()) { if (Date.now() > end) throw Error('Graceful stop timed out. Retry -Status; no unrelated process was killed. Data remains on disk.'); await delay(100); } }
    console.log(live ? 'Demo stopped; database and access sessions preserved.' : 'Demo already stopped; stale PID data is never used to kill processes.'); return;
  }
  if (action === 'verify') { console.log(`Verified: ${verifyPrepared()} external locked packages; native SQLite integrity/schema 5; configuration and source/build fingerprints.`); return; }
  if (action === 'start') {
    const existing = await control();
    if (existing) { console.log(`Demo already ${existing.status}: http://127.0.0.1:${existing.port}/admin`); return; }
    verifyPrepared();
    const port = Number(argument); if (!Number.isInteger(port) || port < 1024 || port > 65535) throw Error('Invalid demo port. Use -Port 1024..65535.');
    await new Promise((resolve, reject) => { const probe = createServer(); probe.once('error', () => reject(Error(`Port ${port} is occupied or unavailable. Stop its application or choose -Start -Port 3001. Existing demo data is safe.`))); probe.listen(port, '127.0.0.1', () => probe.close(resolve)); });
    const fd = fs.openSync(safe(path.join(data, 'server.log')), 'a');
    const instance = randomUUID();
    const child = spawn(process.execPath, [fileURLToPath(new URL('./server.mjs', import.meta.url)), String(port), instance], {
      cwd: root, env: env(), detached: true, windowsHide: true, stdio: ['ignore', fd, fd],
    });
    fs.closeSync(fd); child.unref();
    let failed = false; child.once('error', () => { failed = true; }); child.once('exit', () => { failed = true; });
    const deadline = Date.now() + 20_000;
    while (Date.now() < deadline && !failed) {
      // SQLite's bounded busy timeout can briefly block the starting child's event loop.
      // Keep the overall 20s startup deadline and report the child's safe startup diagnostic.
      let live; try { live = await control(); } catch { if (Date.now() >= deadline) break; }
      if (live?.instance === instance && live.status === 'ready') {
        console.log(`Open http://127.0.0.1:${port}/admin\nProduction startup: ${((Date.now() - started) / 1000).toFixed(3)}s. Use -Stop; Stop/Start preserves .local/arena-demo/arena.sqlite.`); return;
      }
      await delay(100);
    }
    // Kill only the actual child object just created here, never a persisted PID.
    if (!failed) child.kill();
    throw Error('Production startup failed within 20s. Check .local/arena-demo/server.log, folder access/DB locks and port; run -Verify. Existing data was not reset.');
  }
  if (action === 'backup') { await backupTo(backupId('demo')); return; }
  if (action === 'restore' || action === 'reset') {
    await requireStopped();
    let source;
    if (action === 'restore') {
      if (!/^(demo|before-restore|before-reset)-[0-9TZ-]+-[0-9a-f]{8}$/.test(argument ?? '')) throw Error('Invalid backup ID. Use an ID shown by -Status, not a path; database is unchanged.');
      source = safe(path.join(data, 'backups', argument + '.sqlite'));
      const Database = driver(), checked = new Database(safeDatabase(source), { readonly: true, fileMustExist: true });
      try { integrity(checked); } finally { checked.close(); }
    }
    console.log(`${action === 'reset' ? 'Explicit reset' : 'Explicit restore'} target: ${databaseFile}`);
    if (fs.existsSync(databaseFile)) await backupTo(backupId('before-' + action));
    if (action === 'reset') {
      source = safe(path.join(data, 'reset-' + randomUUID() + '.sqlite'));
      const { openDatabase } = await import('../../apps/server/dist/database.js'); const empty = openDatabase(source); empty.close();
    }
    if (action === 'restore') await restoreWithoutRevivingAccess(source);
    else await replaceDatabase(source);
    if (action === 'reset') fs.unlinkSync(safe(source));
    console.log('Database integrity verified. Previous state is in backups; administrator config is preserved. Run -Start.'); return;
  }
  throw Error('Unknown demo action. Use windows-demo.ps1 -Help.');
}
try { await main(); } catch (error) { console.error(friendly(error)); process.exitCode = 1; } finally { clearTimeout(watchdog); }
