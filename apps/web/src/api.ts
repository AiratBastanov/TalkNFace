import { ApiErrorSchema } from '@arena/contracts/g2';
import type { ApiErrorBody } from '@arena/contracts/g2';

export class RequestError extends Error {
  readonly code: ApiErrorBody['code'] | 'NETWORK';
  constructor(code: RequestError['code'], message: string) { super(message); this.code = code; }
}
export async function request<T>(path: string, schema: { parse(value: unknown): T }, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { ...(body === undefined ? {} : { method: 'POST', body: JSON.stringify(body), headers: { 'Content-Type': 'application/json' } }),
      signal: AbortSignal.timeout(12_000), cache: 'no-store' });
  } catch { throw new RequestError('NETWORK', 'Связь с приложением прервалась. Отправку можно безопасно повторить.'); }
  let value: unknown;
  try { value = await response.json(); } catch { throw new RequestError('NETWORK', 'Не удалось прочитать ответ. Отправку можно безопасно повторить.'); }
  if (!response.ok) {
    const error = ApiErrorSchema.safeParse(value);
    throw new RequestError(error.success ? error.data.code : 'INTERNAL_ERROR', error.success ? error.data.message : 'Не удалось выполнить запрос.');
  }
  return schema.parse(value);
}
export const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'Не удалось выполнить действие.';
