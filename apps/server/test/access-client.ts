import { randomBytes } from 'node:crypto';
import type { FastifyInstance, InjectOptions } from 'fastify';
import { AccessSessionSchema } from '@arena/contracts/access';
import { hashPassword } from '../src/access/password.ts';

// Test credentials are freshly generated in memory, never logged or snapshotted.
export const testPassword = randomBytes(24).toString('base64url');
export const testPasswordHash = await hashPassword(testPassword);
export class AccessClient {
  cookie = '';
  csrf = '';
  readonly origin: string;
  app: FastifyInstance;
  constructor(app: FastifyInstance, origin = 'http://127.0.0.1:3000') { this.app = app; this.origin = origin; }
  async send(input: string | InjectOptions) {
    const options = typeof input === 'string' ? { url: input } : input;
    const response = await this.app.inject({ ...options, headers: {
      cookie: this.cookie, origin: this.origin, 'x-csrf-token': this.csrf, ...options.headers,
    } });
    for (const c of response.cookies) this.cookie = c.maxAge === 0 ? '' : `${c.name}=${c.value}`;
    const parsed = AccessSessionSchema.safeParse(response.body ? response.json() : null);
    if (parsed.success) this.csrf = parsed.data.csrfToken;
    return response;
  }
  bootstrap() { return this.send({ method: 'POST', url: '/api/auth/bootstrap', payload: {}, headers: { 'x-arena-bootstrap': '1' } }); }
  login(password = testPassword) { return this.send({ method: 'POST', url: '/api/auth/login', payload: { password } }); }
}
