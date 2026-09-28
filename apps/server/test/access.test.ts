import { createHash, randomUUID } from 'node:crypto';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { buildApp } from '../src/app.ts';
import { openDatabase } from '../src/database.ts';
import { parseEnv } from '../src/env.ts';
import { AccessSessionSchema } from '@arena/contracts/access';
import { SessionViewSchema } from '@arena/contracts/g2';
import { question, walkAway, S1 } from '@arena/scenarios';
import { temporaryDatabase } from './helpers.ts';
import { AccessClient, testPassword, testPasswordHash } from './access-client.ts';

const origin = 'http://127.0.0.1:3000';
const sha = (s: string) => createHash('sha256').update(s).digest('hex');
// Independent expected outcomes: never import the production route-policy table.
describe('G8 real HTTP boundary / durable access', () => {
  let temp: ReturnType<typeof temporaryDatabase>, db: ReturnType<typeof openDatabase>, app: Awaited<ReturnType<typeof buildApp>>;
  let a: AccessClient, b: AccessClient, admin: AccessClient;
  beforeEach(async () => {
    temp = temporaryDatabase(); db = openDatabase(temp.filename);
    app = await buildApp(parseEnv({ NODE_ENV: 'test', DATABASE_PATH: temp.filename, ADMIN_PASSWORD_HASH: testPasswordHash }), { database: db });
    a = new AccessClient(app); b = new AccessClient(app); admin = new AccessClient(app);
  });
  afterEach(async () => { await app.close(); temp.cleanup(); });
  async function restart(hash: string | undefined = testPasswordHash) {
    await app.close(); db = openDatabase(temp.filename);
    app = await buildApp(parseEnv({ NODE_ENV: 'test', DATABASE_PATH: temp.filename, ADMIN_PASSWORD_HASH: hash }), { database: db });
    for (const client of [a, b, admin]) client.app = app;
  }
  async function publish() {
    await admin.bootstrap(); expect((await admin.login()).statusCode).toBe(200);
    return (await admin.send({ method: 'POST', url: '/api/admin/reference-scenarios/s1/publish', payload: {} })).json().id as string;
  }
  async function create() {
    const version = await publish(); await a.bootstrap(); await b.bootstrap();
    const r = await a.send({ method: 'POST', url: '/api/sessions', payload: { scenarioVersionId: version } });
    expect(r.statusCode).toBe(201); return SessionViewSchema.parse(r.json());
  }
  it('bootstrap issues only a fresh player and ignores a fixed attacker bearer; bearer is absent from JSON/SQLite', async () => {
    expect((await app.inject('/api/auth/session')).statusCode).toBe(401);
    a.cookie = 'arena_session=' + 'A'.repeat(43);
    const r = await a.bootstrap(), view = AccessSessionSchema.parse(r.json());
    expect(view.role).toBe('player'); expect(a.cookie.endsWith('A'.repeat(43))).toBe(false);
    const token = a.cookie.split('=')[1]!;
    expect(Buffer.from(token, 'base64url').length).toBe(32); expect(r.body.includes(token)).toBe(false);
    const stored = JSON.stringify(db.prepare('SELECT * FROM access_sessions').all());
    expect(stored.includes(token) || stored.includes(view.csrfToken) || stored.includes(testPassword) || stored.includes(testPasswordHash)).toBe(false);
    const before = a.cookie; await a.bootstrap(); expect(a.cookie === before).toBe(true);
    expect(db.prepare('SELECT count(*) n FROM access_sessions').get()).toEqual({ n: 1 });
  });
  it('public projections need no cookie and reveal neither hidden scenario data nor access credentials', async () => {
    await publish();
    for (const path of ['/api/scenarios', '/api/reference-scenarios', '/health', '/ready']) {
      const r = await app.inject(path); expect(r.statusCode).toBe(200); expect(r.cookies).toHaveLength(0);
      expect(r.body).not.toContain(S1.participants[1].privateBrief);
      expect(r.body).not.toMatch(/"(?:csrfToken|token_digest|definition_json|witnessTraces|opponentUtility|trust|tension)"/);
    }
  });
  it('every admin read/mutation denies anonymous and player, including guessed route IDs', async () => {
    await a.bootstrap();
    for (const [method, url] of [
      ['GET', '/api/admin/reference-scenarios/s1'], ['GET', '/api/admin/context-draft'],
      ['POST', '/api/admin/reference-scenarios/s1/publish'], ['POST', '/api/admin/context-draft/save'],
      ['POST', '/api/admin/context-draft/validate'], ['POST', '/api/admin/context-draft/publish'],
    ] as const) {
      const options = { method, url, ...(method === 'POST' ? { payload: {} } : {}) };
      expect((await app.inject({ ...options, headers: { origin } })).statusCode).toBe(401);
      expect((await a.send(options)).statusCode).toBe(403);
    }
    expect(db.prepare('SELECT count(*) n FROM scenario_versions').get()).toEqual({ n: 0 });
  });
  it('wrong credentials give safe 401 and no privilege; correct password rotates bearer + CSRF, preserving only own identity', async () => {
    await a.bootstrap(); const before = a.cookie, oldCsrf = a.csrf;
    const wrong = await a.login('synthetic-incorrect-password'); expect(wrong.statusCode).toBe(401);
    expect(wrong.json().code).toBe('LOGIN_FAILED'); expect(wrong.body.includes('synthetic-incorrect-password')).toBe(false);
    expect((await a.send('/api/admin/context-draft')).statusCode).toBe(403);
    expect((await a.login()).statusCode).toBe(200);
    expect(a.cookie === before || a.csrf === oldCsrf).toBe(false);
    expect((await a.send('/api/admin/context-draft')).statusCode).toBe(200);
    expect((await app.inject({ url: '/api/admin/context-draft', headers: { cookie: before } })).statusCode).toBe(401);
    const rows = db.prepare('SELECT principal_id FROM access_sessions').all() as { principal_id: string }[];
    expect(new Set(rows.map(r => r.principal_id)).size).toBe(1);
    const stale = await a.send({ method: 'POST', url: '/api/auth/logout', payload: {}, headers: { 'x-csrf-token': oldCsrf } });
    expect(stale.statusCode).toBe(403);
  });
  it('logout deletes the cookie and persists revocation across restart', async () => {
    await a.bootstrap(); await a.login(); const stolen = a.cookie, token = a.csrf;
    const r = await a.send({ method: 'POST', url: '/api/auth/logout', payload: {} }); expect(r.statusCode).toBe(200);
    expect(r.headers['set-cookie']).toMatch(/Max-Age=0/); expect(a.cookie).toBe('');
    await restart();
    expect((await app.inject({ method: 'POST', url: '/api/admin/reference-scenarios/s1/publish', payload: {},
      headers: { origin, cookie: stolen, 'x-csrf-token': token } })).statusCode).toBe(401);
  });
  it('logout during asynchronous password verification prevents the pending elevation from reviving access', async () => {
    await a.bootstrap();
    const pending = a.login();
    await new Promise(resolve => setTimeout(resolve, 5));
    expect((await a.send({ method: 'POST', url: '/api/auth/logout', payload: {} })).statusCode).toBe(200);
    expect((await pending).statusCode).toBe(401);
    expect(db.prepare("SELECT count(*) n FROM access_sessions WHERE role = 'admin' AND revoked_at IS NULL").get()).toEqual({ n: 0 });
  });
  it('missing CSRF rejects every classified browser mutation before domain state changes', async () => {
    const s = await create();
    for (const url of ['/api/auth/login', '/api/auth/logout', '/api/sessions',
      '/api/admin/reference-scenarios/s1/publish', '/api/admin/context-draft/save', '/api/admin/context-draft/validate', '/api/admin/context-draft/publish',
      ...['turns', 'preparation', 'replay'].map(p => `/api/sessions/${s.projection.sessionId}/${p}`)]) {
      const r = await app.inject({ method: 'POST', url, payload: {}, headers: { origin, cookie: admin.cookie } });
      expect(r.statusCode, url).toBe(403); expect(r.json().code).toBe('CSRF_REJECTED');
    }
    expect(db.prepare('SELECT count(*) n FROM turns').get()).toEqual({ n: 0 });
    expect(db.prepare('SELECT revision FROM context_drafts').get()).toEqual({ revision: 0 });
  });
  it.each(['idle_expires_at', 'absolute_expires_at'] as const)('%s cannot revive after restart', async field => {
    await a.bootstrap(); await a.login();
    db.prepare(`UPDATE access_sessions SET ${field} = unixepoch() - 1, idle_expires_at = unixepoch() - 1`).run();
    await restart(); expect((await a.send('/api/admin/context-draft')).statusCode).toBe(401);
    expect((await a.send({ method: 'POST', url: '/api/admin/reference-scenarios/s1/publish', payload: {} })).statusCode).toBe(401);
  });
  it('changing/removing the deployment hash invalidates previous administrator sessions after restart', async () => {
    await a.bootstrap(); await a.login();
    await app.close(); db = openDatabase(temp.filename);
    app = await buildApp(parseEnv({ NODE_ENV: 'test', DATABASE_PATH: temp.filename }), { database: db }); a.app = app;
    expect((await a.send('/api/admin/context-draft')).statusCode).toBe(401);
    await a.bootstrap(); const result = await a.login(); expect(result.statusCode).toBe(503);
    expect(result.json().code).toBe('ADMIN_UNAVAILABLE');
    expect((await a.send('/api/scenarios')).statusCode).toBe(200);
  });
  it('owner can refresh/restart/continue; duplicates still commit once and stale/different requests retain 409', async () => {
    const s = await create(), url = `/api/sessions/${s.projection.sessionId}`;
    const command = { requestId: randomUUID(), expectedRevision: 0, action: question('logistics') };
    const first = await a.send({ method: 'POST', url: url + '/turns', payload: command }); expect(first.statusCode).toBe(200);
    await restart(); expect((await a.send(url)).body).toBe(first.body);
    const duplicate = await a.send({ method: 'POST', url: url + '/turns', payload: command }); expect(duplicate.body).toBe(first.body);
    const stale = await a.send({ method: 'POST', url: url + '/turns', payload: { ...command, requestId: randomUUID() } });
    expect(stale.statusCode).toBe(409); expect(stale.json().code).toBe('STALE_REVISION');
    const conflict = await a.send({ method: 'POST', url: url + '/turns', payload: { ...command, action: walkAway() } });
    expect(conflict.statusCode).toBe(409); expect(conflict.json().code).toBe('IDEMPOTENCY_CONFLICT');
    expect(db.prepare('SELECT count(*) n FROM turns').get()).toEqual({ n: 1 });
    expect((await a.send({ method: 'POST', url: url + '/turns', payload: { ...command, requestId: randomUUID(), expectedRevision: 1, action: walkAway() } })).statusCode).toBe(200);
  });
  it('exact foreign UUID, report/replay, duplicate receipt and admin override all fail before protected data loads', async () => {
    const s = await create(), id = s.projection.sessionId, base = '/api/sessions/';
    const command = { requestId: randomUUID(), expectedRevision: 0, action: walkAway() };
    await a.send({ method: 'POST', url: base + id + '/turns', payload: command });
    for (const client of [b, admin]) {
      for (const suffix of ['', '/result', '/preparation', '/feedback?revision=1', '/feedback/comparison?revision=1&predecessorId=' + id]) {
        const r = await client.send(base + id + suffix); const missing = await client.send(base + randomUUID() + suffix);
        expect(r.statusCode).toBe(404); expect(r.body).toBe(missing.body);
      }
      for (const suffix of ['/turns', '/preparation', '/replay']) {
        expect((await client.send({ method: 'POST', url: base + id + suffix, payload: suffix === '/turns' ? command : {} })).statusCode).toBe(404);
      }
    }
    expect((await a.send(base + id + '/feedback?revision=1')).statusCode).toBe(200);
    const replay = await a.send({ method: 'POST', url: base + id + '/replay', payload: {} }); expect(replay.statusCode).toBe(201);
    const replayId = replay.json().projection.sessionId;
    expect((await b.send(base + replayId)).statusCode).toBe(404);
    expect(db.prepare('SELECT count(*) n FROM session_owners').get()).toEqual({ n: 2 });
    expect(db.prepare('SELECT count(*) n FROM turns').get()).toEqual({ n: 1 });
  });
  it('comparison verifies predecessor ownership even for an owned current attempt', async () => {
    const s = await create();
    const own = await b.send({ method: 'POST', url: '/api/sessions', payload: { scenarioVersionId: s.scenarioVersionId } });
    expect((await b.send(`/api/sessions/${own.json().projection.sessionId}/feedback/comparison?revision=1&predecessorId=${s.projection.sessionId}`)).statusCode).toBe(404);
  });
  it.each(['missing', 'wrong', 'other-session'])('rejects %s CSRF on owned mutation, leaves domain unchanged', async kind => {
    const s = await create();
    const headers: Record<string, string> = { origin, cookie: a.cookie };
    if (kind !== 'missing') headers['x-csrf-token'] = kind === 'wrong' ? 'X'.repeat(43) : b.csrf;
    const r = await app.inject({ method: 'POST', url: `/api/sessions/${s.projection.sessionId}/turns`, headers,
      payload: { requestId: randomUUID(), expectedRevision: 0, action: walkAway() } });
    expect(r.statusCode).toBe(403); expect(r.json().code).toBe('CSRF_REJECTED');
    expect(db.prepare('SELECT count(*) n FROM turns').get()).toEqual({ n: 0 });
  });
  it('login CSRF, logout CSRF and authenticated admin mutation without CSRF are refused', async () => {
    await a.bootstrap();
    for (const url of ['/api/auth/login', '/api/auth/logout']) {
      const r = await app.inject({ method: 'POST', url, headers: { origin, cookie: a.cookie }, payload: { password: testPassword } });
      expect(r.statusCode).toBe(403);
    }
    await a.login();
    expect((await app.inject({ method: 'POST', url: '/api/admin/reference-scenarios/s1/publish', headers: { origin, cookie: a.cookie }, payload: {} })).statusCode).toBe(403);
  });
  it.each([
    { origin: 'https://foreign.example' }, { origin: 'null' }, { origin: '' },
    { origin, 'sec-fetch-site': 'cross-site' }, { origin, 'sec-fetch-site': 'same-site' },
  ])('rejects unsafe origin/Fetch Metadata %j even with valid authentication and CSRF', async extra => {
    await a.bootstrap();
    const r = await a.send({ method: 'POST', url: '/api/auth/logout', payload: {}, headers: extra });
    expect(r.statusCode).toBe(403); expect(r.json().code).toBe('ORIGIN_REJECTED');
    expect(r.headers['access-control-allow-origin']).toBeUndefined();
    expect((await a.send('/api/auth/session')).statusCode).toBe(200);
  });
  it('missing Origin is denied; defined no-Fetch-Metadata fallback requires exact Origin plus CSRF', async () => {
    await a.bootstrap();
    const r = await app.inject({ method: 'POST', url: '/api/auth/logout', payload: {}, headers: { cookie: a.cookie, 'x-csrf-token': a.csrf } });
    expect(r.statusCode).toBe(403);
    expect((await a.send({ method: 'POST', url: '/api/auth/logout', payload: {} })).statusCode).toBe(200);
  });
  it('bootstrap is state-changing POST only, requires the custom header and cannot take identity from body', async () => {
    for (const payload of [{}, { principalId: randomUUID() }]) {
      const r = await app.inject({ method: 'POST', url: '/api/auth/bootstrap', payload, headers: { origin } }); expect(r.statusCode).toBe(403);
    }
    expect((await app.inject('/api/auth/bootstrap')).statusCode).toBe(404);
    expect(db.prepare('SELECT count(*) n FROM access_principals').get()).toEqual({ n: 0 });
    expect((await app.inject({ method: 'POST', url: '/api/auth/bootstrap', payload: {}, headers: { origin: 'https://foreign.example', 'x-arena-bootstrap': '1' } })).statusCode).toBe(403);
  });
  it('GET/HEAD, auth inspection and static/public reads never write or slide idle lifetime', async () => {
    const s = await create(); db.prepare('UPDATE access_sessions SET last_seen_at = last_seen_at - 600').run();
    const count = () => (db.prepare('SELECT total_changes() n').get() as { n: number }).n;
    const before = count();
    for (const url of ['/api/auth/session', '/api/scenarios', '/api/reference-scenarios', `/api/sessions/${s.projection.sessionId}`, '/health', '/ready']) {
      for (const method of ['GET', 'HEAD'] as const) expect((await a.send({ method, url })).statusCode).toBe(200);
    }
    expect(count()).toBe(before);
  });
  it('idle refresh is bounded, absolute deadline remains fixed, and invalid unsafe requests do not touch it', async () => {
    const s = await create(); const token = sha(a.cookie.split('=')[1]!);
    db.prepare('UPDATE access_sessions SET last_seen_at = last_seen_at - 600, idle_expires_at = idle_expires_at - 600 WHERE token_digest = ?').run(token);
    const state = () => db.prepare('SELECT last_seen_at, idle_expires_at, absolute_expires_at FROM access_sessions WHERE token_digest = ?').get(token);
    const before = state() as { absolute_expires_at: number };
    await a.send({ method: 'POST', url: '/api/sessions', payload: { scenarioVersionId: s.scenarioVersionId } });
    const after = state() as { absolute_expires_at: number }; expect(after.absolute_expires_at).toBe(before.absolute_expires_at);
    expect(after).not.toEqual(before);
    await a.send({ method: 'POST', url: '/api/sessions', payload: { scenarioVersionId: s.scenarioVersionId } }); expect(state()).toEqual(after);
    await a.send({ method: 'POST', url: '/api/auth/logout', payload: {}, headers: { 'x-csrf-token': 'wrong' } }); expect(state()).toEqual(after);
  });
  it('global login work budget survives new browsers and process restart, and expires after 15min', async () => {
    await a.bootstrap();
    for (let i = 0; i < 10; i++) expect((await a.login('wrong')).statusCode).toBe(401);
    await restart(); await b.bootstrap(); expect((await b.login()).statusCode).toBe(429);
    expect((await b.send('/api/admin/context-draft')).statusCode).toBe(403);
    db.prepare('UPDATE access_login_budget SET window_start = unixepoch() - 901').run();
    expect((await b.login()).statusCode).toBe(200);
  });
  it('malformed/oversized login errors never echo credential input or framework stacks', async () => {
    await a.bootstrap();
    for (const payload of ['{"password":"sensitive-test-input",', JSON.stringify({ password: 'secret-test'.repeat(300) }), { password: 'private-value', extra: 'private-value' }]) {
      const r = await a.send({ method: 'POST', url: '/api/auth/login', payload, headers: { 'content-type': 'application/json' } });
      expect(r.statusCode).toBeGreaterThanOrEqual(400); expect(r.body).not.toMatch(/sensitive-test|secret-test|private-value|stack|SyntaxError/);
    }
  });
  it.each(['PUT', 'PATCH', 'DELETE', 'OPTIONS'] as const)('unclassified %s cannot publish, including valid auth/CSRF', async method => {
    await a.bootstrap(); await a.login();
    expect((await a.send({ method, url: '/api/admin/reference-scenarios/s1/publish', payload: {} })).statusCode).toBe(404);
    expect(db.prepare('SELECT count(*) n FROM scenario_versions').get()).toEqual({ n: 0 });
  });
  it('local cookie has explicit bounded HttpOnly/Strict/Path semantics and no false Host claim', async () => {
    const r = await a.bootstrap(), c = r.cookies[0]!;
    expect(c.name).toBe('arena_session'); expect(c.httpOnly).toBe(true); expect(c.sameSite).toBe('Strict'); expect(c.path).toBe('/');
    expect(c.secure).toBeUndefined(); expect(c.domain).toBeUndefined(); expect(c.maxAge).toBe(7 * 86400);
    const authenticated = await a.login(); expect(authenticated.cookies[0]!.maxAge).toBe(8 * 3600);
  });
});

it('injected public HTTPS profile emits __Host Secure cookie, same attributes on explicit logout; no public listen', async () => {
  const temp = temporaryDatabase(), origin = 'https://arena.example';
  const app = await buildApp(parseEnv({ NODE_ENV: 'test', DATABASE_PATH: temp.filename, ACCESS_PROFILE: 'public', APP_ORIGIN: origin }));
  try {
    const client = new AccessClient(app, origin), response = await client.bootstrap(), c = response.cookies[0]!;
    expect(c.name).toBe('__Host-arena_session'); expect(c.secure).toBe(true); expect(c.httpOnly).toBe(true);
    expect(c.path).toBe('/'); expect(c.domain).toBeUndefined(); expect(c.sameSite).toBe('Strict');
    const logout = await client.send({ method: 'POST', url: '/api/auth/logout', payload: {} });
    expect(logout.cookies[0]).toMatchObject({ name: '__Host-arena_session', secure: true, httpOnly: true, path: '/', maxAge: 0 });
  } finally { await app.close(); temp.cleanup(); }
});

it.each([
  { HOST: '0.0.0.0' }, { HOST: '192.168.1.2' }, { APP_ORIGIN: 'http://public.example' }, { APP_ORIGIN: 'https://127.0.0.1' },
  { ACCESS_PROFILE: 'public' }, { ACCESS_PROFILE: 'public', APP_ORIGIN: 'http://arena.example' },
  { ACCESS_PROFILE: 'public', APP_ORIGIN: 'https://arena.example/path' },
  { ACCESS_PROFILE: 'public', APP_ORIGIN: 'https://user:password@arena.example' },
  { ACCESS_PROFILE: 'public', APP_ORIGIN: 'https://arena.example/?token=private' },
  { ADMIN_PASSWORD_HASH: 'private-invalid-hash' },
])('fails closed on contradictory access configuration %j without exposing values', config => {
  expect(() => parseEnv(config)).toThrow(/Invalid configuration:/);
  try { parseEnv(config); } catch (e) { expect(String(e)).not.toMatch(/private-invalid|user:password|token=private/); }
});
