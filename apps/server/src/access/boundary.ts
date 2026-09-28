import { createHash, createHmac, randomBytes, randomUUID, timingSafeEqual } from 'node:crypto';
import cookie from '@fastify/cookie';
import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import type Database from 'better-sqlite3';
import { z } from 'zod';
import { AccessSessionSchema } from '@arena/contracts/access';
import type { SessionView } from '@arena/contracts/g2';
import { ApiError } from '../api-error.ts';
import type { ServerConfig } from '../env.ts';
import { verifyPassword } from './password.ts';

type Role = 'player' | 'admin';
type AccessRow = {
  token_digest: string; principal_id: string; role: Role; csrf_digest: string; credential_digest: string | null;
  created_at: number; last_seen_at: number; idle_expires_at: number; absolute_expires_at: number; revoked_at: number | null;
};
declare module 'fastify' { interface FastifyRequest { arenaAccess: AccessRow | null } }
type Policy = 'public' | 'bootstrap' | 'principal' | 'admin' | 'owner';
// Enumerated route templates, not a permissive /api/admin or /api/sessions prefix.
const policy = new Map<string, Policy>();
function routes(method: string, access: Policy, urls: string[]) {
  for (const url of urls) {
    policy.set(`${method} ${url}`, access);
    if (method === 'GET') policy.set(`HEAD ${url}`, access);
  }
}
routes('GET', 'public', ['/health', '/ready', '/api/scenarios', '/api/reference-scenarios', '/*']);
routes('POST', 'bootstrap', ['/api/auth/bootstrap']);
routes('GET', 'principal', ['/api/auth/session']);
routes('POST', 'principal', ['/api/auth/login', '/api/auth/logout', '/api/sessions']);
routes('GET', 'admin', ['/api/admin/context-draft', '/api/admin/reference-scenarios/:key']);
routes('POST', 'admin', ['/api/admin/reference-scenarios/:key/publish', '/api/admin/context-draft/save',
  '/api/admin/context-draft/validate', '/api/admin/context-draft/publish']);
routes('GET', 'owner', ['/api/sessions/:sessionId', '/api/sessions/:sessionId/result',
  '/api/sessions/:sessionId/preparation', '/api/sessions/:sessionId/feedback', '/api/sessions/:sessionId/feedback/comparison']);
routes('POST', 'owner', ['/api/sessions/:sessionId/turns', '/api/sessions/:sessionId/preparation', '/api/sessions/:sessionId/replay']);
const digest = (value: string) => createHash('sha256').update(value).digest('hex');
const csrf = (bearer: string) => createHmac('sha256', bearer).update('arena.csrf.v1').digest('base64url');
const idle: Record<Role, number> = { player: 24 * 3600, admin: 30 * 60 };
const absolute: Record<Role, number> = { player: 7 * 86400, admin: 8 * 3600 };
const unsafe = (method: string) => !['GET', 'HEAD', 'OPTIONS'].includes(method);
const empty = z.strictObject({});
const login = z.strictObject({ password: z.string().min(1).max(256) });
const unauthenticated = () => new ApiError(401, 'UNAUTHENTICATED', 'Срок доступа истёк или вход не выполнен. Откройте приложение заново; администратору нужно войти.');
const notFound = () => new ApiError(404, 'NOT_FOUND', 'Попытка недоступна в этом браузере или не найдена.');

export class AccessBoundary {
  private readonly db: Database.Database;
  private readonly config: ServerConfig;
  private readonly cookieName: string;
  private readonly credentialDigest: string | null;
  constructor(database: Database.Database, config: ServerConfig) {
    this.db = database; this.config = config;
    this.cookieName = config.ACCESS_PROFILE === 'public' ? '__Host-arena_session' : 'arena_session';
    this.credentialDigest = config.ADMIN_PASSWORD_HASH ? digest(config.ADMIN_PASSWORD_HASH) : null;
  }
  private now() { return this.db.prepare<[], { now: number }>('SELECT unixepoch() AS now').get()!.now; }
  private bearer(request: FastifyRequest) { return request.cookies[this.cookieName]; }
  private resolve(bearer: string | undefined): AccessRow | null {
    if (!bearer || !/^[A-Za-z0-9_-]{43}$/.test(bearer)) return null;
    const row = this.db.prepare<[string, number, number], AccessRow>(`SELECT * FROM access_sessions
      WHERE token_digest = ? AND revoked_at IS NULL AND idle_expires_at > ? AND absolute_expires_at > ?`)
      .get(digest(bearer), this.now(), this.now());
    if (!row || (row.role === 'admin' && (!this.credentialDigest || row.credential_digest !== this.credentialDigest))) return null;
    return row;
  }
  private current(request: FastifyRequest) {
    const row = this.resolve(this.bearer(request));
    if (!row) throw unauthenticated();
    return row;
  }
  private cookieOptions() {
    return { httpOnly: true, sameSite: 'strict' as const, path: '/', secure: this.config.ACCESS_PROFILE === 'public' };
  }
  private projection(row: AccessRow, bearer: string) {
    return AccessSessionSchema.parse({ role: row.role, csrfToken: csrf(bearer), adminConfigured: !!this.credentialDigest,
      expiresAt: row.absolute_expires_at, idleExpiresAt: row.idle_expires_at });
  }
  private issue(role: Role, principalId?: string) {
    const now = this.now(), bearer = randomBytes(32).toString('base64url'), principal = principalId ?? randomUUID();
    if (!principalId) this.db.prepare('INSERT INTO access_principals VALUES (?, ?)').run(principal, now);
    const row: AccessRow = { token_digest: digest(bearer), principal_id: principal, role, csrf_digest: digest(csrf(bearer)),
      credential_digest: role === 'admin' ? this.credentialDigest : null, created_at: now, last_seen_at: now,
      idle_expires_at: now + idle[role], absolute_expires_at: now + absolute[role], revoked_at: null };
    this.db.prepare(`INSERT INTO access_sessions VALUES (@token_digest, @principal_id, @role, @csrf_digest,
      @credential_digest, @created_at, @last_seen_at, @idle_expires_at, @absolute_expires_at, @revoked_at)`).run(row);
    return { row, bearer };
  }
  private setCookie(reply: FastifyReply, issued: ReturnType<AccessBoundary['issue']>) {
    reply.setCookie(this.cookieName, issued.bearer, { ...this.cookieOptions(), maxAge: absolute[issued.row.role] });
    return this.projection(issued.row, issued.bearer);
  }
  assertOwner(request: FastifyRequest, sessionId: unknown) {
    const row = request.arenaAccess;
    if (!row) throw unauthenticated();
    if (typeof sessionId !== 'string' || !this.db.prepare(`SELECT 1 FROM session_owners
      WHERE session_id = ? AND principal_id = ?`).get(sessionId, row.principal_id)) throw notFound();
  }
  createOwned(request: FastifyRequest, create: () => SessionView) {
    // Callback creates a NEW attempt inside this same transaction. No claim-by-UUID endpoint exists.
    return this.db.transaction(() => {
      const principal = this.current(request).principal_id;
      const view = create();
      this.db.prepare('INSERT INTO session_owners VALUES (?, ?)').run(view.projection.sessionId, principal);
      return view;
    }).immediate();
  }
  private checkOrigin(request: FastifyRequest) {
    // Mandatory Origin also defines the fallback for API clients without Fetch Metadata.
    const site = request.headers['sec-fetch-site'];
    if (request.headers.origin !== this.config.APP_ORIGIN || (site !== undefined && site !== 'same-origin')) {
      throw new ApiError(403, 'ORIGIN_REJECTED', 'Запрос отклонён: откройте приложение по его основному адресу.');
    }
  }
  private checkCsrf(request: FastifyRequest, row: AccessRow) {
    const token = request.headers['x-csrf-token'];
    if (typeof token !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(token)
      || !timingSafeEqual(Buffer.from(digest(token), 'hex'), Buffer.from(row.csrf_digest, 'hex'))) {
      throw new ApiError(403, 'CSRF_REJECTED', 'Защитный токен устарел или отсутствует. Обновите страницу и повторите действие.');
    }
  }
  private consumeLoginBudget() {
    this.db.transaction(() => {
      const now = this.now();
      const budget = this.db.prepare<[], { window_start: number; attempts: number }>('SELECT * FROM access_login_budget WHERE id = 1').get();
      if (!budget || now >= budget.window_start + 15 * 60) {
        this.db.prepare('INSERT OR REPLACE INTO access_login_budget VALUES (1, ?, 1)').run(now);
      } else {
        if (budget.attempts >= 10) throw new ApiError(429, 'LOGIN_THROTTLED', 'Слишком много попыток входа. Повторите через 15 минут.');
        this.db.prepare('UPDATE access_login_budget SET attempts = attempts + 1 WHERE id = 1').run();
      }
    }).immediate();
  }
  async register(app: FastifyInstance) {
    await app.register(cookie);
    app.decorateRequest('arenaAccess', null);
    app.addHook('onRequest', async (request, reply) => {
      reply.header('Referrer-Policy', 'no-referrer').header('X-Content-Type-Options', 'nosniff');
      if (request.url.startsWith('/api/')) reply.header('Cache-Control', 'no-store');
      const route = request.routeOptions.url;
      const access = policy.get(`${request.method} ${route}`);
      // A not-found SPA navigation can serve the public shell only. A newly added real route is denied.
      if (!access) {
        if (request.is404 && ['GET', 'HEAD'].includes(request.method)) return;
        throw new ApiError(404, 'NOT_FOUND', 'Маршрут не найден.');
      }
      if (access === 'public') return;
      try {
        if (unsafe(request.method)) this.checkOrigin(request);
        if (access === 'bootstrap') return;
        const row = this.current(request); request.arenaAccess = row;
        if (unsafe(request.method)) this.checkCsrf(request, row);
        if (access === 'admin' && row.role !== 'admin') throw new ApiError(403, 'FORBIDDEN', 'Для этого действия нужен вход администратора.');
        if (access === 'owner') this.assertOwner(request, (request.params as { sessionId?: string }).sessionId);
      } catch (error) {
        if (error instanceof ApiError) app.log.info({ event: 'access.denied', routeClass: access, reason: error.body.code }, 'Access denied');
        throw error;
      }
    });
    app.addHook('onResponse', async (request, reply) => {
      const row = request.arenaAccess;
      if (!row || !unsafe(request.method) || reply.statusCode >= 400 || !this.db.open) return;
      const now = this.now();
      if (now - row.last_seen_at < 300) return;
      this.db.prepare(`UPDATE access_sessions SET last_seen_at = ?, idle_expires_at = MIN(absolute_expires_at, ?)
        WHERE token_digest = ? AND revoked_at IS NULL AND idle_expires_at > ? AND absolute_expires_at > ? AND last_seen_at <= ?`)
        .run(now, now + idle[row.role], row.token_digest, now, now, now - 300);
    });
    const query = (request: FastifyRequest) => {
      if (!empty.safeParse(request.query).success) throw new ApiError(400, 'INVALID_REQUEST', 'Параметры запроса не поддерживаются.');
    };
    app.post('/api/auth/bootstrap', { bodyLimit: 128 }, async (request, reply) => {
      query(request);
      if (request.headers['x-arena-bootstrap'] !== '1' || !request.headers['content-type']?.startsWith('application/json')
        || !empty.safeParse(request.body).success) throw new ApiError(403, 'CSRF_REJECTED', 'Откройте приложение, чтобы начать сессию.');
      const row = this.resolve(this.bearer(request));
      if (row) return this.projection(row, this.bearer(request)!);
      return this.setCookie(reply, this.db.transaction(() => this.issue('player')).immediate());
    });
    app.get('/api/auth/session', async request => { query(request); return this.projection(this.current(request), this.bearer(request)!); });
    app.post('/api/auth/login', { bodyLimit: 2048 }, async (request, reply) => {
      query(request);
      if (!this.config.ADMIN_PASSWORD_HASH) throw new ApiError(503, 'ADMIN_UNAVAILABLE', 'Вход администратора не настроен. Владелец должен задать ADMIN_PASSWORD_HASH.');
      this.consumeLoginBudget();
      const parsed = login.safeParse(request.body);
      if (!parsed.success || !await verifyPassword(parsed.data.password, this.config.ADMIN_PASSWORD_HASH)) {
        app.log.info({ event: 'access.login_failed', routeClass: 'auth', reason: 'credential' }, 'Login failed');
        throw new ApiError(401, 'LOGIN_FAILED', 'Не удалось войти. Проверьте пароль администратора.');
      }
      const issued = this.db.transaction(() => {
        // Logout/expiry during asynchronous scrypt must win over privilege elevation.
        const previous = this.current(request);
        this.db.prepare('UPDATE access_sessions SET revoked_at = ? WHERE token_digest = ?').run(this.now(), previous.token_digest);
        return this.issue('admin', previous.principal_id);
      }).immediate();
      app.log.info({ event: 'access.login', routeClass: 'auth' }, 'Administrator authenticated');
      return this.setCookie(reply, issued);
    });
    app.post('/api/auth/logout', { bodyLimit: 128 }, async (request, reply) => {
      query(request);
      if (!empty.safeParse(request.body).success) throw new ApiError(400, 'INVALID_REQUEST', 'Некорректный запрос выхода.');
      this.db.prepare('UPDATE access_sessions SET revoked_at = ? WHERE token_digest = ?').run(this.now(), this.current(request).token_digest);
      reply.clearCookie(this.cookieName, this.cookieOptions());
      app.log.info({ event: 'access.logout', routeClass: 'auth' }, 'Access revoked');
      return { loggedOut: true };
    });
  }
}
