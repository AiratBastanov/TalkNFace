import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:net';
import { dirname, join, resolve, sep } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { randomBytes } from 'node:crypto';
import type { Page } from '@playwright/test';
import { hashPassword } from '../../apps/server/src/access/password.ts';

export async function productionHarness(options: { seedDatabase?: string; label?: string } = {}) {
  assert.equal(process.version, 'v24.21.0');
  const root = process.cwd(); const tempRoot = resolve(root, '.tmp');
  mkdirSync(tempRoot, { recursive: true });
  const directory = mkdtempSync(join(tempRoot, 'g2-browser-'));
  const database = join(directory, 'arena.sqlite');
  if (options.seedDatabase) copyFileSync(options.seedDatabase, database);
  const label = options.label ?? 'g2';
  const portServer = createServer(); portServer.listen(0, '127.0.0.1'); await once(portServer, 'listening');
  const address = portServer.address(); assert(address && typeof address !== 'string'); const port = address.port;
  await new Promise<void>((done, reject) => portServer.close(error => error ? reject(error) : done()));
  const origin = `http://127.0.0.1:${port}`;
  const password = randomBytes(24).toString('base64url');
  const passwordHash = await hashPassword(password);
  const gateDeadline = Date.now() + 175_000;
  const runtime = dirname(process.execPath);
  const pids: number[] = []; let starts = 0; let stops = 0; let running: Awaited<ReturnType<typeof launch>> | null = null;
  async function launch() {
    // Actual npm start, minimal environment, no AI credentials. Browser is separately owned by Playwright.
    const child = spawn(process.execPath, [join(runtime, 'node_modules/npm/bin/npm-cli.js'), 'start'], {
      cwd: root, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'],
      env: { PATH: runtime + (process.platform === 'win32' ? ';' : ':') + process.env.PATH,
        SystemRoot: process.env.SystemRoot, WINDIR: process.env.WINDIR,
        npm_config_cache: join(root, '.tools/npm-cache'), npm_config_update_notifier: 'false',
        NODE_OPTIONS: `--require="${join(root, 'scripts/g2-test-console.cjs').replaceAll('\\', '/')}"`,
        HOST: '127.0.0.1', PORT: String(port), DATABASE_PATH: database,
        ACCESS_PROFILE: 'local', APP_ORIGIN: origin, ADMIN_PASSWORD_HASH: passwordHash },
    });
    const owned = new Set<number>(child.pid ? [child.pid] : []); const exit = once(child, 'exit');
    let output = ''; let carry = ''; let forced = false;
    child.stdout.on('data', chunk => {
      output += chunk; carry += chunk; const lines = carry.split(/\r?\n/); carry = lines.pop() ?? '';
      for (const line of lines) if (line.startsWith('{"g2Process":')) {
        const message = JSON.parse(line) as { pid: number; parent: number }; owned.add(message.pid); owned.add(message.parent); pids.push(message.pid);
      }
    });
    child.stderr.on('data', chunk => { output += chunk; });
    async function forceStop() {
      if (child.exitCode !== null) return;
      forced = true;
      const ids = [...owned].filter(Number.isSafeInteger).filter(id => id !== process.pid);
      if (process.platform === 'win32') {
        const killer = spawn('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
          'Stop-Process -Id ' + ids.join(',') + ' -Force -ErrorAction SilentlyContinue'], { windowsHide: true, stdio: 'ignore' });
        await once(killer, 'exit');
      } else for (const id of ids.reverse()) { try { process.kill(id, 'SIGKILL'); } catch { /* Already closed. */ } }
    }
    const lifetime = setTimeout(() => { void forceStop(); }, Math.max(1, gateDeadline - Date.now()));
    const until = Date.now() + 12_000;
    try {
      let ready = false;
      while (Date.now() < until && child.exitCode === null) {
        try { const response = await fetch(origin + '/ready', { signal: AbortSignal.timeout(500) }); ready = response.status === 200; await response.text(); if (ready) break; }
        catch { /* Bounded startup wait. */ }
        await delay(100);
      }
      assert(ready, 'npm start was not ready: ' + output); starts++;
    } catch (error) { clearTimeout(lifetime); await forceStop(); throw error; }
    return {
      securityEvents() {
        return output.split(/\r?\n/).flatMap(line => {
          try { const v = JSON.parse(line); return typeof v.event === 'string' && v.event.startsWith('access.')
            ? [{ event: v.event, routeClass: v.routeClass, reason: v.reason }] : []; } catch { return []; }
        });
      },
      async stop() {
        child.stdin.write('g2-stop\n'); const deadline = setTimeout(() => { void forceStop(); }, 10_000);
        try {
          const [code, signal] = await exit; assert.equal(forced, false); assert.equal(code, 0, output); assert.equal(signal, null);
          assert.match(output, /database.closed/); assert.equal(existsSync(database + '-wal'), false); assert.equal(existsSync(database + '-shm'), false); stops++;
        } finally {
          clearTimeout(deadline); clearTimeout(lifetime);
          mkdirSync(join(root, '.tools/logs'), { recursive: true }); writeFileSync(join(root, `.tools/logs/${label}-browser-production-${starts}.log`), output);
          await forceStop();
        }
      },
    };
  }
  return {
    origin, database,
    securityEvents() { return running?.securityEvents() ?? []; },
    async login(page: Page) {
      await page.goto(origin + '/admin');
      await page.getByLabel('Пароль администратора', { exact: true }).fill(password);
      await page.getByRole('button', { name: 'Войти', exact: true }).click();
      await page.getByRole('button', { name: 'Выйти', exact: true }).waitFor();
    },
    async post(page: Page, url: string, data: object) {
      const session = await page.request.get(origin + '/api/auth/session');
      assert.equal(session.status(), 200);
      const { csrfToken } = await session.json() as { csrfToken: string };
      return page.request.post(url, { data, headers: { Origin: origin, 'X-CSRF-Token': csrfToken } });
    },
    async start() { assert.equal(running, null); running = await launch(); },
    async stop() { if (running) { const instance = running; running = null; await instance.stop(); } },
    evidence() { return { command: 'npm start', runtime: process.version, platform: process.platform, starts, cleanShutdowns: stops, serverPids: pids,
      aiCredentials: 'NONE', database: 'isolated real SQLite', shutdown: 'real SIGINT handler via test-only stdin adapter', orphanProcesses: running ? 1 : 0 }; },
    cleanup() { const target = resolve(directory); if (!target.startsWith(tempRoot + sep)) throw new Error('Unsafe cleanup'); rmSync(target, { recursive: true, force: true }); },
  };
}
