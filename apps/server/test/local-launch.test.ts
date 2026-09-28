import { fork } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { createServer } from 'node:net';
import { once } from 'node:events';
import { expect, it } from 'vitest';
import { temporaryDatabase } from './helpers.ts';

it('owner launch uses UTF-8 stdin / ephemeral hash, real production build and loopback; logs omit credentials', async () => {
  const probe = createServer(); probe.listen(0, '127.0.0.1'); await once(probe, 'listening');
  const address = probe.address(); if (!address || typeof address === 'string') throw new Error('No port');
  await new Promise<void>((resolve, reject) => probe.close(e => e ? reject(e) : resolve()));
  const temp = temporaryDatabase(), password = 'Секрет-' + randomBytes(24).toString('base64url');
  const child = fork('scripts/local-demo.mjs', ['--stdin'], { execArgv: [], windowsHide: true, stdio: ['pipe', 'pipe', 'pipe', 'ipc'],
    env: { SystemRoot: process.env.SystemRoot, WINDIR: process.env.WINDIR, PATH: process.env.PATH, PORT: String(address.port), DATABASE_PATH: temp.filename } });
  let output = ''; child.stdout!.on('data', c => { output += c; }); child.stderr!.on('data', c => { output += c; });
  const exited = once(child, 'exit');
  const deadline = setTimeout(() => child.kill(), 9_000);
  try {
    const message = once(child, 'message'); child.stdin!.end(password, 'utf8');
    const [started] = await Promise.race([message, exited.then(() => { throw new Error('Owner launch exited before readiness'); })]);
    expect(started).toMatchObject({ type: 'started' });
    const origin = `http://127.0.0.1:${address.port}`;
    const bootstrap = await fetch(origin + '/api/auth/bootstrap', { method: 'POST', headers: {
      Origin: origin, 'Content-Type': 'application/json', 'X-Arena-Bootstrap': '1',
    }, body: '{}', signal: AbortSignal.timeout(1000) });
    expect(bootstrap.status).toBe(200); const cookie = bootstrap.headers.getSetCookie()[0]!.split(';')[0]!;
    const { csrfToken } = await bootstrap.json() as { csrfToken: string };
    const login = await fetch(origin + '/api/auth/login', { method: 'POST', headers: {
      Origin: origin, 'Content-Type': 'application/json', Cookie: cookie, 'X-CSRF-Token': csrfToken,
    }, body: JSON.stringify({ password }), signal: AbortSignal.timeout(1000) });
    expect(login.status).toBe(200); expect((await login.json() as { role: string }).role).toBe('admin');
    child.send('shutdown'); const [code] = await exited; expect(code).toBe(0);
    expect(output.includes(password) || output.includes(csrfToken) || output.includes(cookie) || output.includes('scrypt$')).toBe(false);
  } finally { clearTimeout(deadline); if (child.exitCode === null) { child.kill(); await exited; } temp.cleanup(); }
});
