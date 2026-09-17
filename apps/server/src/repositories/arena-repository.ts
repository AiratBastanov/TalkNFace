import { createHash, randomUUID } from 'node:crypto';
import type Database from 'better-sqlite3';
import { NegotiationStateSchema } from '@arena/contracts';
import type { NegotiationState, ScenarioDefinition } from '@arena/contracts';
import { SessionViewSchema } from '@arena/contracts/g2';
import { validateScenario } from '@arena/domain';
import { ApiError, corruptState } from '../api-error.ts';

export function stableJson(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return '[' + value.map(stableJson).join(',') + ']';
  return '{' + Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)
    .map(([key, item]) => JSON.stringify(key) + ':' + stableJson(item)).join(',') + '}';
}
export const hashBody = (value: unknown) => createHash('sha256').update(stableJson(value)).digest('hex');

export type VersionRow = {
  id: string; template_id: string; schema_version: number; engine_version: string; rubric_version: string;
  config_fingerprint: string; definition_hash: string; definition_json: string; created_at: string; published_at: string;
};
export type SessionRow = {
  id: string; scenario_version_id: string; revision: number; phase: string; state_json: string;
  mode: string; replay_of: string | null; created_at: string; updated_at: string; terminal_at: string | null;
};
export type TurnRow = {
  session_id: string; turn_number: number; request_id: string; request_body_hash: string;
  action_json: string; events_json: string; public_response_json: string; state_after_json: string; created_at: string;
};
export function readPublicResponse(json: string) {
  try { return SessionViewSchema.parse(JSON.parse(json)); } catch { return corruptState(); }
}

// SQL and persisted-data validation only. Negotiation policy stays in G1.
export class ArenaRepository {
  readonly db: Database.Database;
  constructor(db: Database.Database) { this.db = db; }
  immediate<T>(work: () => T): T { return this.db.transaction(work).immediate(); }
  read<T>(work: () => T): T { return this.db.transaction(work)(); }
  version(id: string): VersionRow {
    const row = this.db.prepare<[string], VersionRow>('SELECT * FROM scenario_versions WHERE id = ?').get(id);
    if (!row) throw new ApiError(404, 'NOT_FOUND', 'Опубликованная версия не найдена.');
    return row;
  }
  versions(): VersionRow[] {
    return this.db.prepare<[], VersionRow>('SELECT * FROM scenario_versions ORDER BY published_at, id').all();
  }
  definition(row: VersionRow): ScenarioDefinition {
    try {
      const result = validateScenario(JSON.parse(row.definition_json));
      if (!result.valid) return corruptState();
      const definition = result.scenario;
      if (hashBody(definition) !== row.definition_hash || definition.templateId !== row.template_id
        || definition.schemaVersion !== row.schema_version || row.engine_version !== 'deterministic-core-v1'
        || definition.evaluation.rubricVersion !== row.rubric_version || definition.configFingerprint !== row.config_fingerprint) return corruptState();
      return definition;
    } catch { return corruptState(); }
  }
  publish(definition: ScenarioDefinition): VersionRow {
    const result = validateScenario(definition);
    if (!result.valid || definition.templateId === null) return corruptState();
    const hash = hashBody(result.scenario);
    const existing = this.db.prepare<[string], VersionRow>('SELECT * FROM scenario_versions WHERE definition_hash = ?').get(hash);
    if (existing) { this.definition(existing); return existing; }
    const now = new Date().toISOString();
    const row: VersionRow = { id: randomUUID(), template_id: definition.templateId, schema_version: definition.schemaVersion,
      engine_version: 'deterministic-core-v1', rubric_version: definition.evaluation.rubricVersion,
      config_fingerprint: definition.configFingerprint, definition_hash: hash, definition_json: JSON.stringify(result.scenario),
      created_at: now, published_at: now };
    this.db.prepare(`INSERT INTO scenario_versions VALUES (@id, @template_id, @schema_version, @engine_version,
      @rubric_version, @config_fingerprint, @definition_hash, @definition_json, @created_at, @published_at)`).run(row);
    return row;
  }
  session(id: string): SessionRow {
    const row = this.db.prepare<[string], SessionRow>('SELECT * FROM sessions WHERE id = ?').get(id);
    if (!row) throw new ApiError(404, 'NOT_FOUND', 'Сессия не найдена.');
    return row;
  }
  state(row: SessionRow, definition: ScenarioDefinition): NegotiationState {
    try {
      const state = NegotiationStateSchema.parse(JSON.parse(row.state_json));
      if (state.sessionId !== row.id || state.scenarioVersionId !== row.scenario_version_id
        || state.revision !== row.revision || state.turnNumber !== row.revision || state.phase !== row.phase
        || state.configHash !== definition.configFingerprint || state.rubricVersion !== definition.evaluation.rubricVersion
        || row.mode !== 'DEMO_FALLBACK' || (state.terminalReason === null) !== (row.terminal_at === null)
        || (state.outcome === null) !== (state.terminalReason === null)
        || (state.terminalReason !== null && state.phase !== state.terminalReason)
        || state.knownFactIds.some(id => !definition.facts.some(fact => fact.id === id))) return corruptState();
      return state;
    } catch { return corruptState(); }
  }
  insertSession(state: NegotiationState, replayOf: string | null) {
    const now = new Date().toISOString();
    this.db.prepare(`INSERT INTO sessions VALUES (?, ?, ?, ?, ?, 'DEMO_FALLBACK', ?, ?, ?, NULL)`)
      .run(state.sessionId, state.scenarioVersionId, state.revision, state.phase, JSON.stringify(state), replayOf, now, now);
  }
  turns(sessionId: string): TurnRow[] {
    return this.db.prepare<[string], TurnRow>('SELECT * FROM turns WHERE session_id = ? ORDER BY turn_number').all(sessionId);
  }
  request(sessionId: string, requestId: string): TurnRow | undefined {
    return this.db.prepare<[string, string], TurnRow>('SELECT * FROM turns WHERE session_id = ? AND request_id = ?').get(sessionId, requestId);
  }
  insertTurn(row: TurnRow) {
    this.db.prepare(`INSERT INTO turns VALUES (@session_id, @turn_number, @request_id, @request_body_hash,
      @action_json, @events_json, @public_response_json, @state_after_json, @created_at)`).run(row);
  }
  updateSession(state: NegotiationState, expectedRevision: number, now: string) {
    const result = this.db.prepare(`UPDATE sessions SET revision = ?, phase = ?, state_json = ?, updated_at = ?, terminal_at = ?
      WHERE id = ? AND revision = ?`).run(state.revision, state.phase, JSON.stringify(state), now,
      state.terminalReason === null ? null : now, state.sessionId, expectedRevision);
    if (result.changes !== 1) throw new ApiError(409, 'STALE_REVISION', 'Сессия уже изменилась. Загрузите актуальное состояние.');
  }
}
