import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash, randomUUID } from 'node:crypto';
import { createConnection } from 'node:net';
import { validPasswordHash } from '../../apps/server/src/access/password.ts';

export const root = fileURLToPath(new URL('../../', import.meta.url)).replace(/[\\/]$/, '');
export const data = path.join(root, '.local/arena-demo');
export const configFile = path.join(root, '.local/arena-config/admin.json');
export const databaseFile = path.join(data, 'arena.sqlite');
export const toolsDir = path.join(root, '.tools/arena-runtime');
export const preparedFile = path.join(data, 'prepared.json');
export const stateFile = path.join(data, 'server.json');
export const sha = bytes => createHash('sha256').update(bytes).digest('hex');
export const pipe = '\\\\.\\pipe\\arena-demo-' + sha(root.toLowerCase()).slice(0, 32);
export const json = file => JSON.parse(fs.readFileSync(safe(file), 'utf8').replace(/^\uFEFF/, ''));
export function safe(filename) {
  const full = path.resolve(filename);
  if (!full.toLowerCase().startsWith(root.toLowerCase() + path.sep)) throw Error('Path escapes this checkout. No demo files were removed.');
  let part = full;
  while (true) {
    try { if (fs.lstatSync(part).isSymbolicLink()) throw Error('Symlink/junction in demo path. Use a regular directory; no data was removed.'); }
    catch (e) { if (e.code !== 'ENOENT') throw e; }
    const parent = path.dirname(part); if (part === parent) break; part = parent;
  }
  return full;
}
export function writeJson(file, value) {
  safe(file); fs.mkdirSync(path.dirname(file), { recursive: true });
  const temp = safe(file + '.' + randomUUID() + '.partial');
  fs.writeFileSync(temp, JSON.stringify(value, null, 2) + '\n', { flag: 'wx' });
  fs.renameSync(temp, file);
}
export function safeDatabase(file) {
  for (const suffix of ['', '-wal', '-shm', '-journal']) safe(file + suffix);
  return file;
}
export function config() {
  try {
    const c = json(configFile);
    if (c.schema !== 1 || Object.keys(c).sort().join(',') !== 'adminPasswordHash,schema' || !validPasswordHash(c.adminPasswordHash)) throw Error();
    return c;
  } catch {
    throw Error('Administrator config is missing or malformed (.local/arena-config/admin.json). Run -Prepare for first setup, or -SetAdminPassword to explicitly replace it while stopped. Database is preserved.');
  }
}
export const workspaces = ['apps/server', 'apps/web', 'packages/contracts', 'packages/domain', 'packages/scenarios'];
function filesIn(dir) {
  if (!fs.existsSync(dir)) throw Error('Source/build is incomplete. Retry -Prepare; database and admin config are preserved.');
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => {
    const p = path.join(dir, e.name); safe(p);
    return e.isDirectory() ? filesIn(p) : [p];
  });
}
function digest(files) { return sha(files.sort().map(p => path.relative(root, p) + ':' + sha(fs.readFileSync(safe(p)))).join('\n')); }
export function sourceDigest() {
  const files = ['package.json', 'package-lock.json', 'apps/web/index.html', 'apps/web/vite.config.ts', 'scripts/windows-demo.ps1', 'scripts/check-runtime.mjs'].map(p => path.join(root, p));
  for (const base of [root, ...workspaces.map(p => path.join(root, p))]) {
    files.push(...fs.readdirSync(base).filter(n => /^tsconfig.*\.json$/.test(n)).map(n => path.join(base, n)));
  }
  for (const ws of workspaces) files.push(path.join(root, ws, 'package.json'), ...filesIn(path.join(root, ws, 'src')));
  files.push(...filesIn(path.join(root, 'scripts/demo')));
  return digest(files);
}
export function buildDigest() { return digest(workspaces.flatMap(p => filesIn(path.join(root, p, 'dist')))); }
export function checkLock() {
  const lock = json(path.join(root, 'package-lock.json'));
  const pkg = json(path.join(root, 'package.json'));
  if (JSON.stringify(pkg.workspaces) !== JSON.stringify(workspaces) || JSON.stringify(lock.packages[''].workspaces) !== JSON.stringify(workspaces)) {
    throw Error('Unexpected workspace set. Only the five accepted application packages are supported; no AI/model workspace is installed.');
  }
  const canonical = value => JSON.stringify(Object.entries(value ?? {}).sort(([a], [b]) => a.localeCompare(b)));
  for (const ws of ['', ...workspaces]) {
    const manifest = json(path.join(root, ws, 'package.json')), pinned = lock.packages[ws];
    if (!pinned || manifest.name !== pinned.name || manifest.version !== pinned.version || ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies', 'engines'].some(k => canonical(manifest[k]) !== canonical(pinned[k]))) {
      throw Error('package.json and package-lock.json disagree. Obtain a matching source checkout; no dependency upgrade was attempted and demo data is safe.');
    }
  }
  const hooks = Object.entries(lock.packages).filter(([, p]) => p.hasInstallScript).map(([p]) => p).sort();
  if (JSON.stringify(hooks) !== JSON.stringify(['', 'apps/server/node_modules/better-sqlite3', 'node_modules/fsevents'])) {
    throw Error('Dependency install hooks changed. Review the lockfile before preparing; no unreviewed install scripts were run.');
  }
  if (Object.entries(lock.packages).some(([p, v]) => p === 'packages/ai' || p.startsWith('node_modules/@arena/ai') || (v.resolved && !v.link && !v.resolved.startsWith('https://registry.npmjs.org/')))) {
    throw Error('Lockfile contains an unsupported source/workspace. Use the accepted application lockfile.');
  }
  return lock;
}
export function checkTree() {
  const lock = checkLock(); let count = 0;
  for (const [relative, entry] of Object.entries(lock.packages)) {
    if (!relative.includes('node_modules/')) continue;
    if (entry.link) {
      if (fs.realpathSync(path.join(root, relative)).toLowerCase() !== fs.realpathSync(path.join(root, entry.resolved)).toLowerCase()) {
        throw Error('Workspace link points outside the accepted application. Retry -Prepare; data is preserved.');
      }
      continue;
    }
    const filename = path.join(root, relative, 'package.json');
    if (!fs.existsSync(filename) && entry.optional) continue;
    if (!fs.existsSync(filename) || json(filename).version !== entry.version) {
      throw Error('Installed dependencies differ from the lockfile. Retry -Prepare (npm ci); database/configuration are preserved.');
    }
    count++;
  }
  return count;
}
export async function control(command = 'status') {
  return new Promise((resolve, reject) => {
    const socket = createConnection(pipe); let result = '';
    socket.setTimeout(2_000, () => socket.destroy(Error('Demo control did not respond. Do not kill a PID from a stale file; retry -Status. Data remains on disk.')));
    socket.once('connect', () => socket.write(command + '\n'));
    socket.on('data', b => { result += b; if (result.length > 4096) socket.destroy(Error('Invalid demo control response.')); });
    socket.once('error', e => ['ENOENT', 'ECONNREFUSED'].includes(e.code) ? resolve(null) : reject(e));
    socket.once('end', () => {
      try { const r = JSON.parse(result); if (r.root !== root || !r.instance) throw Error(); resolve(r); }
      catch { reject(Error('Unrecognized demo control response. No process was terminated.')); }
    });
  });
}
export async function requireStopped() {
  if (await control()) throw Error('Demo is running. Run -Stop first, then repeat this command. Database and configuration are preserved.');
}
export function friendly(error) {
  if (/^SQLITE_|^EACCES$|^EPERM$|^EBUSY$/.test(error?.code ?? '')) return 'Database/files are locked or inaccessible. Close other tools using this checkout and retry; check folder write access. No automatic deletion or reset was performed.';
  return error instanceof Error ? error.message : 'Demo operation failed. Retry -Verify or -Prepare; do not delete .local (it contains your saved demo).';
}
