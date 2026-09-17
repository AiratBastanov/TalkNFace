import { randomUUID } from 'node:crypto';
import { CanonicalActionSchema, DomainEventSchema, NegotiationStateSchema } from '@arena/contracts';
import type { NegotiationState, PublicProjection, ScenarioDefinition } from '@arena/contracts';
import { PlayTurnSchema, PublishedScenarioSchema, ReferencePreviewSchema, SessionViewSchema } from '@arena/contracts/g2';
import type { BasicResult, PublicTurn, SessionView } from '@arena/contracts/g2';
import { createInitialState, projectPlayer, transition } from '@arena/domain';
import { S1 } from '@arena/scenarios';
import { ApiError, corruptState } from '../api-error.ts';
import { ArenaRepository, hashBody, readPublicResponse } from '../repositories/arena-repository.ts';
import type { SessionRow, VersionRow } from '../repositories/arena-repository.ts';
import { basicResult, guidedActions, renderTurn } from '../presentation/renderers.ts';

export function referencePreview(definition: ScenarioDefinition = S1) {
  const p = projectPlayer(definition, createInitialState(definition, { sessionId: 'preview', scenarioVersionId: 'preview' }));
  return ReferencePreviewSchema.parse({ templateId: definition.templateId, scenario: p.scenario,
    difficulty: definition.policy.difficulty, tone: definition.policy.tone, maxTurns: p.maxTurns, publicFacts: p.knownFacts });
}
function view(row: Pick<SessionRow, 'scenario_version_id' | 'replay_of'>, p: PublicProjection, transcript: PublicTurn[], result: BasicResult | null): SessionView {
  return SessionViewSchema.parse({ mode: 'DEMO_FALLBACK', scenarioVersionId: row.scenario_version_id, replayOf: row.replay_of,
    projection: p, actions: guidedActions(p), transcript, result });
}

export class SessionService {
  readonly repository: ArenaRepository;
  constructor(repository: ArenaRepository) { this.repository = repository; }
  published(row: VersionRow) {
    const definition = this.repository.definition(row);
    return PublishedScenarioSchema.parse({ id: row.id, definitionHash: row.definition_hash,
      schemaVersion: row.schema_version, engineVersion: row.engine_version, rubricVersion: row.rubric_version,
      configFingerprint: row.config_fingerprint, createdAt: row.created_at, publishedAt: row.published_at, preview: referencePreview(definition) });
  }
  publish() { return this.repository.immediate(() => this.published(this.repository.publish(S1))); }
  scenarios() { return this.repository.read(() => this.repository.versions().map(row => this.published(row))); }
  private load(id: string) {
    const row = this.repository.session(id);
    const definition = this.repository.definition(this.repository.version(row.scenario_version_id));
    const state = this.repository.state(row, definition);
    const turns = this.repository.turns(id);
    if (turns.length !== state.revision) return corruptState();
    const transcript: PublicTurn[] = [];
    let persistedResult: BasicResult | null = null;
    try {
      for (const [index, turn] of turns.entries()) {
        const saved = readPublicResponse(turn.public_response_json);
        const publicTurn = saved.transcript.at(-1);
        const snapshot = NegotiationStateSchema.parse(JSON.parse(turn.state_after_json));
        CanonicalActionSchema.parse(JSON.parse(turn.action_json));
        DomainEventSchema.array().parse(JSON.parse(turn.events_json));
        if (turn.turn_number !== index + 1 || saved.projection.sessionId !== id || saved.scenarioVersionId !== row.scenario_version_id
          || saved.projection.revision !== turn.turn_number || saved.transcript.length !== turn.turn_number
          || publicTurn?.requestId !== turn.request_id || publicTurn.turnNumber !== turn.turn_number
          || snapshot.sessionId !== id || snapshot.scenarioVersionId !== row.scenario_version_id || snapshot.revision !== turn.turn_number) return corruptState();
        transcript.push(publicTurn);
        if (index === turns.length - 1) {
          if (hashBody(snapshot) !== hashBody(state)) return corruptState();
          persistedResult = saved.result;
        }
      }
      if ((state.outcome === null) !== (persistedResult === null)) return corruptState();
    } catch { return corruptState(); }
    return { row, definition, state, transcript, persistedResult };
  }
  get(id: string): SessionView {
    return this.repository.read(() => {
      const loaded = this.load(id);
      return view(loaded.row, projectPlayer(loaded.definition, loaded.state), loaded.transcript, loaded.persistedResult);
    });
  }
  private newSession(versionId: string, replayOf: string | null): SessionView {
    const definition = this.repository.definition(this.repository.version(versionId));
    const state = createInitialState(definition, { sessionId: randomUUID(), scenarioVersionId: versionId });
    this.repository.insertSession(state, replayOf);
    return view({ scenario_version_id: versionId, replay_of: replayOf }, projectPlayer(definition, state), [], null);
  }
  create(versionId: string) { return this.repository.immediate(() => this.newSession(versionId, null)); }
  replay(id: string) {
    return this.repository.immediate(() => {
      const loaded = this.load(id);
      if (!loaded.state.outcome) throw new ApiError(409, 'SESSION_NOT_TERMINAL', 'Сначала завершите текущие переговоры.');
      return this.newSession(loaded.row.scenario_version_id, id);
    });
  }
  result(id: string): BasicResult {
    const result = this.get(id).result;
    if (!result) throw new ApiError(409, 'SESSION_NOT_TERMINAL', 'Переговоры ещё не завершены.');
    return result;
  }
  playTurn(id: string, input: unknown): SessionView {
    const parsed = PlayTurnSchema.safeParse(input);
    if (!parsed.success) throw new ApiError(400, 'INVALID_REQUEST', 'Проверьте формат действия и все условия предложения.');
    const command = parsed.data;
    const bodyHash = hashBody(command);
    // Entire synchronous G1 -> renderer -> writes path uses BEGIN IMMEDIATE.
    return this.repository.immediate(() => {
      const existing = this.repository.request(id, command.requestId);
      if (existing) {
        if (existing.request_body_hash !== bodyHash) throw new ApiError(409, 'IDEMPOTENCY_CONFLICT', 'Этот идентификатор отправки уже использован для другого действия.');
        return readPublicResponse(existing.public_response_json);
      }
      const loaded = this.load(id);
      const { state, definition, row, transcript } = loaded;
      if (command.expectedRevision !== state.revision) throw new ApiError(409, 'STALE_REVISION', 'В другой вкладке уже сделан ход. Состояние нужно обновить.', state.revision);
      if (state.outcome) throw new ApiError(409, 'SESSION_TERMINAL', 'Переговоры уже завершены. Можно повторить ситуацию.');
      const moved = transition(definition, state, command);
      if (!moved.ok) {
        if (moved.errors.some(error => error.code === 'INVALID_STATE')) return corruptState();
        throw new ApiError(422, 'DOMAIN_REJECTED', 'Действие недоступно: проверьте выбранные факты, условия и актуальность предложения. Ход не израсходован.');
      }
      const played = moved.events.find(event => event.payload.type === 'action_played');
      if (played?.payload.type !== 'action_played') return corruptState();
      const publicTurn = renderTurn(command.requestId, played.payload.action, moved.events, projectPlayer(definition, state), moved.public);
      const updatedTranscript = [...transcript, publicTurn];
      const response = view(row, moved.public, updatedTranscript, basicResult(moved.public, updatedTranscript));
      const now = new Date().toISOString();
      this.repository.insertTurn({ session_id: id, turn_number: moved.state.turnNumber, request_id: command.requestId,
        request_body_hash: bodyHash, action_json: JSON.stringify(played.payload.action), events_json: JSON.stringify(moved.events),
        public_response_json: JSON.stringify(response), state_after_json: JSON.stringify(moved.state), created_at: now });
      this.repository.updateSession(moved.state, state.revision, now);
      return response;
    });
  }
}
