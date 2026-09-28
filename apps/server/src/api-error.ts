import type { AccessErrorBody as ApiErrorBody } from '@arena/contracts/access';

export class ApiError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody;
  constructor(status: number, code: ApiErrorBody['code'], message: string, currentRevision?: number) {
    super(message);
    this.status = status;
    this.body = { code, message, ...(currentRevision === undefined ? {} : { currentRevision }) };
  }
}
export function corruptState(): never {
  throw new ApiError(500, 'CORRUPT_STATE', 'Сохранённая сессия или версия повреждена. Продолжение остановлено.');
}
