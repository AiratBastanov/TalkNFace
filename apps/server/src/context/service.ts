import { randomUUID } from 'node:crypto';
import { z } from 'zod';
import { BindingSchema, SaveDraftSchema, PublishCandidateSchema, DraftSchema, DEFAULT_SETTINGS, ContextPublicationSchema } from '@arena/contracts/context-config';
import type { Draft } from '@arena/contracts/context-config';
import { validateScenario } from '@arena/domain';
import { ApiError, corruptState } from '../api-error.ts';
import { ArenaRepository, hashBody } from '../repositories/arena-repository.ts';
import type { VersionRow } from '../repositories/arena-repository.ts';
import { SessionService } from '../services/session-service.ts';
import { compileSettings, APPROVAL_VERSION } from './compiler.ts';

type Row = { revision: number; settings_hash: string; settings_json: string; validation_json: string | null; definition_json: string | null };
function parse<T>(schema: z.ZodType<T>, input: unknown): T {
  const result = schema.safeParse(input);
  if (!result.success) throw new ApiError(400, 'INVALID_REQUEST', 'Проверьте все шесть настроек: разрешены только варианты из формы, без дополнительных полей.');
  return result.data;
}
export class ContextService {
  readonly repository: ArenaRepository;
  constructor(repository: ArenaRepository) {
    this.repository = repository;
    repository.db.prepare('INSERT OR IGNORE INTO context_drafts VALUES (1, 0, ?, ?, NULL, NULL)')
      .run(hashBody(DEFAULT_SETTINGS), JSON.stringify(DEFAULT_SETTINGS));
  }
  private row(): Row {
    const row = this.repository.db.prepare<[], Row>('SELECT * FROM context_drafts WHERE id = 1').get();
    if (!row) return corruptState();
    return row;
  }
  get(): Draft {
    const row = this.row();
    try {
      const draft = DraftSchema.parse({ revision: row.revision, settingsHash: row.settings_hash, settings: JSON.parse(row.settings_json),
        validation: row.validation_json ? JSON.parse(row.validation_json) : null });
      if (hashBody(draft.settings) !== draft.settingsHash) return corruptState();
      // An older compiler approval cannot survive a compiler-policy update.
      if (draft.validation?.compilerVersion !== APPROVAL_VERSION) draft.validation = null;
      return draft;
    } catch { return corruptState(); }
  }
  private same(input: z.infer<typeof BindingSchema>) {
    const row = this.row();
    if (input.expectedRevision !== row.revision || input.settingsHash !== row.settings_hash)
      throw new ApiError(409, 'STALE_REVISION', 'Черновик изменён в другой вкладке. Ваш ввод сохранён на экране. Загрузите сохранённый черновик и проверьте различия.', row.revision);
    return row;
  }
  private previous(requestId: string, bodyHash: string): unknown | undefined {
    const row = this.repository.db.prepare<[string], { body_hash: string; response_json: string }>('SELECT * FROM context_requests WHERE request_id = ?').get(requestId);
    if (!row) return undefined;
    if (row.body_hash !== bodyHash) throw new ApiError(409, 'IDEMPOTENCY_CONFLICT', 'Идентификатор отправки уже использован с другими данными.');
    try { return JSON.parse(row.response_json); } catch { return corruptState(); }
  }
  private remember(requestId: string, bodyHash: string, response: unknown) {
    this.repository.db.prepare('INSERT INTO context_requests VALUES (?, ?, ?)').run(requestId, bodyHash, JSON.stringify(response));
  }
  save(input: unknown): Draft {
    const c = parse(SaveDraftSchema, input), bodyHash = hashBody({ operation: 'save', ...c });
    return this.repository.immediate(() => {
      const old = this.previous(c.requestId, bodyHash); if (old) return DraftSchema.parse(old);
      this.same(c);
      this.repository.db.prepare('UPDATE context_drafts SET revision = revision + 1, settings_hash = ?, settings_json = ?, validation_json = NULL, definition_json = NULL WHERE id = 1')
        .run(hashBody(c.settings), JSON.stringify(c.settings));
      const response = this.get(); this.remember(c.requestId, bodyHash, response); return response;
    });
  }
  validate(input: unknown): Draft {
    const c = parse(BindingSchema, input), bodyHash = hashBody({ operation: 'validate', ...c });
    const old = this.previous(c.requestId, bodyHash); if (old) return DraftSchema.parse(old);
    this.same(c);
    const settings = this.get().settings;
    // Bounded compilation / witness work is outside the SQLite write transaction.
    const compiled = compileSettings(settings);
    const validation = { ...compiled.validation, revision: c.expectedRevision, settingsHash: c.settingsHash };
    return this.repository.immediate(() => {
      const repeated = this.previous(c.requestId, bodyHash); if (repeated) return DraftSchema.parse(repeated);
      this.same(c);
      this.repository.db.prepare('UPDATE context_drafts SET validation_json = ?, definition_json = ? WHERE id = 1')
        .run(JSON.stringify(validation), compiled.definition ? JSON.stringify(compiled.definition) : null);
      const response = this.get(); this.remember(c.requestId, bodyHash, response); return response;
    });
  }
  publish(input: unknown) {
    const c = parse(PublishCandidateSchema, input), bodyHash = hashBody({ operation: 'publish', ...c });
    const old = this.previous(c.requestId, bodyHash); if (old) return ContextPublicationSchema.parse(old);
    const snapshot = this.same(c), draft = this.get(), approval = draft.validation;
    if (!snapshot.definition_json || approval?.status !== 'valid' || approval.revision !== c.expectedRevision
      || approval.settingsHash !== c.settingsHash || approval.candidateHash !== c.candidateHash || approval.compilerVersion !== APPROVAL_VERSION) {
      throw new ApiError(409, 'DOMAIN_REJECTED', 'Эта версия не проверена. Сохраните настройки, выполните проверку и подтвердите новый предпросмотр.');
    }
    const validation = validateScenario(JSON.parse(snapshot.definition_json));
    if (!validation.valid || hashBody(validation.scenario) !== c.candidateHash) return corruptState();
    // The persisted server-generated candidate is used exactly, never client JSON or current defaults.
    const definition = validation.scenario;
    return this.repository.immediate(() => {
      const repeated = this.previous(c.requestId, bodyHash); if (repeated) return ContextPublicationSchema.parse(repeated);
      const current = this.same(c);
      if (current.definition_json !== snapshot.definition_json || current.validation_json !== snapshot.validation_json)
        throw new ApiError(409, 'STALE_REVISION', 'Проверка черновика обновилась. Откройте актуальный предпросмотр.');
      let row = this.repository.db.prepare<[string], VersionRow>('SELECT * FROM scenario_versions WHERE definition_hash = ?').get(c.candidateHash);
      if (!row) {
        const now = new Date().toISOString();
        row = { id: randomUUID(), template_id: definition.templateId!, schema_version: definition.schemaVersion,
          engine_version: 'deterministic-core-v1', rubric_version: definition.evaluation.rubricVersion,
          config_fingerprint: definition.configFingerprint, definition_hash: c.candidateHash,
          definition_json: snapshot.definition_json!, created_at: now, published_at: now };
        this.repository.db.prepare(`INSERT INTO scenario_versions VALUES (@id, @template_id, @schema_version, @engine_version,
          @rubric_version, @config_fingerprint, @definition_hash, @definition_json, @created_at, @published_at)`).run(row);
      }
      const response = ContextPublicationSchema.parse({ publication: new SessionService(this.repository).published(row),
        revision: c.expectedRevision, candidateHash: c.candidateHash });
      this.remember(c.requestId, bodyHash, response); return response;
    });
  }
}
