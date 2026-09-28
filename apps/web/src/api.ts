import { AccessErrorSchema as ApiErrorSchema, AccessSessionSchema } from '@arena/contracts/access';
import type { AccessErrorBody as ApiErrorBody, AccessSession } from '@arena/contracts/access';

export class RequestError extends Error {
  readonly code: ApiErrorBody['code'] | 'NETWORK';
  readonly status: number;
  constructor(code: RequestError['code'], message: string, status = 0) { super(message); this.code = code; this.status = status; }
}
// CSRF stays in module memory. Bearer credentials are managed only by the HttpOnly cookie.
let session: AccessSession | null = null;
let booting: Promise<AccessSession> | null = null;
export type AccessStatus = Pick<AccessSession, 'role' | 'adminConfigured'>;
const subscribers = new Set<(status: AccessStatus | null) => void>();
function remember(value: AccessSession | null) {
  session = value;
  for (const notify of subscribers) notify(value ? { role: value.role, adminConfigured: value.adminConfigured } : null);
}
export function subscribeAccess(notify: (status: AccessStatus | null) => void) { subscribers.add(notify); return () => { subscribers.delete(notify); }; }
async function transport<T>(path: string, schema: { parse(value: unknown): T }, body?: unknown, headers: Record<string, string> = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { ...(body === undefined ? {} : { method: 'POST', body: JSON.stringify(body), headers: { 'Content-Type': 'application/json', ...headers } }),
      signal: AbortSignal.timeout(12_000), cache: 'no-store', credentials: 'same-origin' });
  } catch { throw new RequestError('NETWORK', 'Связь с приложением прервалась. Отправку можно безопасно повторить.'); }
  let value: unknown;
  try { value = await response.json(); } catch { throw new RequestError('NETWORK', 'Не удалось прочитать ответ. Отправку можно безопасно повторить.'); }
  if (!response.ok) {
    const error = ApiErrorSchema.safeParse(value);
    const code = error.success ? error.data.code : 'INTERNAL_ERROR';
    if (code === 'UNAUTHENTICATED') remember(null);
    if (code === 'FORBIDDEN' || code === 'CSRF_REJECTED') {
      // Another tab may have rotated/logged out. Refresh identity, never replay a mutation.
      try { remember(await transport('/api/auth/session', AccessSessionSchema)); } catch { /* Preserve the original actionable error. */ }
    }
    throw new RequestError(code, error.success ? error.data.message : 'Не удалось выполнить запрос.', response.status);
  }
  return schema.parse(value);
}
async function ensureAccess() {
  if (session) return session;
  if (!booting) booting = (async () => {
    let value: AccessSession;
    try { value = await transport('/api/auth/session', AccessSessionSchema); }
    catch (error) {
      if (!(error instanceof RequestError) || error.code !== 'UNAUTHENTICATED') throw error;
      value = await transport('/api/auth/bootstrap', AccessSessionSchema, {}, { 'X-Arena-Bootstrap': '1' });
    }
    remember(value); return value;
  })().finally(() => { booting = null; });
  return booting;
}
export async function accessStatus(): Promise<AccessStatus> {
  const value = await ensureAccess(); return { role: value.role, adminConfigured: value.adminConfigured };
}
export async function request<T>(path: string, schema: { parse(value: unknown): T }, body?: unknown): Promise<T> {
  const value = await ensureAccess();
  return transport(path, schema, body, body === undefined ? {} : { 'X-CSRF-Token': value.csrfToken });
}
export async function adminLogin(password: string) { remember(await request('/api/auth/login', AccessSessionSchema, { password })); }
export async function logout() {
  await request('/api/auth/logout', { parse: (value: unknown) => value }, {});
  remember(null);
  try {
    localStorage.removeItem('arena:last-session');
    for (const key of Object.keys(sessionStorage)) if (key.startsWith('arena:')) sessionStorage.removeItem(key);
  } catch { /* Navigation IDs only. */ }
}
export const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'Не удалось выполнить действие.';
