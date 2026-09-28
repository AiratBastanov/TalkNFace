import { randomUUID } from 'node:crypto';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import Driver from 'better-sqlite3';
import { afterAll, afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { CanonicalAction, NegotiationState } from '@arena/contracts';
import { BasicResultSchema, PublishedScenarioSchema, SessionViewSchema } from '@arena/contracts/g2';
import type { SessionView } from '@arena/contracts/g2';
import { createInitialState, projectPlayer, transition } from '@arena/domain';
import { S1, accept, acknowledge, argument, offer, pressure, question, supplyTerms, walkAway } from '@arena/scenarios';
import { GOLDENS } from '../../../packages/scenarios/test/goldens.ts';
import { buildApp } from './authenticated-fixture.ts';
import { openDatabase } from '../src/database.ts';
import { ArenaRepository, hashBody } from '../src/repositories/arena-repository.ts';
import { renderOpponent, renderPlayer, observations } from '../src/presentation/renderers.ts';
import { temporaryDatabase } from './helpers.ts';
import { PROJECT_ROOT } from '../src/paths.ts';

const durations: number[] = [];
const outcomes: { trace: string; expected: string; actual: string; turns: number; batnaComparison: string }[] = [];
let serializedResponses = 0;
function privacy(body: string, knownIds: string[] = []) {
  serializedResponses += 1;
  expect(body).not.toMatch(/"(?:trust|tension|warning|earnedEventKeys|progressCredits|groundedArgumentIds|resourceAuthorizations|aspiration|opponentUtility|opponentBatna|witnessTraces|definition_json|definitionJson|participants)"\s*:/);
  expect(body).not.toMatch(/"(?:social_state_changed|progress_credit_earned)"/);
  expect(body).not.toContain(S1.participants[1].privateBrief);
  expect(body).not.toContain(S1.participants[1].batna.description);
  for (const fact of S1.facts.filter(f => f.visibility === 'hidden' && !knownIds.includes(f.id))) {
    expect(body).not.toContain(fact.text); expect(body).not.toContain(fact.id);
  }
  expect(body).not.toMatch(/(?:sk-[A-Za-z0-9]{12}|BEGIN PRIVATE KEY|SQLITE_CONSTRAINT|[A-Z]:\\Users\\|"stack")/);
}

describe('G2 actual HTTP / SQLite application boundary', () => {
  let temp: ReturnType<typeof temporaryDatabase>;
  let db: Driver.Database;
  let app: Awaited<ReturnType<typeof buildApp>>;
  beforeEach(async () => {
    temp = temporaryDatabase(); db = openDatabase(temp.filename);
    app = await buildApp({ NODE_ENV: 'development', HOST: '127.0.0.1', PORT: 3000, DATABASE_PATH: temp.filename }, { database: db });
  });
  afterEach(async () => { await app.close(); temp.cleanup(); });
  async function publish() {
    const response = await app.inject({ method: 'POST', url: '/api/admin/reference-scenarios/s1/publish', payload: {} });
    expect(response.statusCode).toBe(200); privacy(response.body);
    return PublishedScenarioSchema.parse(response.json());
  }
  async function create(versionId?: string) {
    const id = versionId ?? (await publish()).id;
    const response = await app.inject({ method: 'POST', url: '/api/sessions', payload: { scenarioVersionId: id } });
    expect(response.statusCode).toBe(201); privacy(response.body);
    return SessionViewSchema.parse(response.json());
  }
  async function play(state: SessionView, action: CanonicalAction, requestId = randomUUID()) {
    const started = performance.now();
    const response = await app.inject({ method: 'POST', url: `/api/sessions/${state.projection.sessionId}/turns`,
      payload: { requestId, expectedRevision: state.projection.revision, action } });
    durations.push(performance.now() - started);
    expect(response.statusCode, response.body).toBe(200);
    const result = SessionViewSchema.parse(response.json());
    privacy(response.body, result.projection.knownFacts.map(f => f.id));
    return result;
  }
  it('publishes S1 once, stores exact immutable definition and metadata; only public previews/listing', async () => {
    expect((await app.inject('/api/scenarios')).json()).toEqual([]);
    for (const url of ['/api/reference-scenarios', '/api/admin/reference-scenarios/s1']) {
      const response = await app.inject(url); expect(response.statusCode).toBe(200); privacy(response.body);
    }
    const first = await publish(); const second = await publish(); expect(second).toEqual(first);
    const repo = new ArenaRepository(db); const row = repo.version(first.id);
    expect(repo.definition(row)).toEqual(S1); expect(row.definition_hash).toBe(hashBody(S1));
    expect(row.engine_version).toBe('deterministic-core-v1'); expect(row.schema_version).toBe(1);
    expect(row.rubric_version).toBe(S1.evaluation.rubricVersion); expect(row.config_fingerprint).toBe(S1.configFingerprint);
    expect(repo.versions()).toHaveLength(1);
    expect(() => db.prepare('UPDATE scenario_versions SET definition_json = ? WHERE id = ?').run('{}', first.id)).toThrow();
    expect(() => db.prepare('DELETE FROM scenario_versions WHERE id = ?').run(first.id)).toThrow();
    const list = await app.inject('/api/scenarios'); privacy(list.body); expect(list.json()).toEqual([first]);
  });
  it('pins old sessions to stored definitions; a changed reference is a new version', async () => {
    const first = await create(); const repo = new ArenaRepository(db);
    const modified = structuredClone(S1); modified.title = 'Новая редакция';
    const newer = repo.immediate(() => repo.publish(modified)); expect(newer.id).not.toBe(first.scenarioVersionId);
    const after = await play(first, question('logistics'));
    expect(after.projection.scenario.title).toBe(S1.title);
    expect((await create(newer.id)).projection.scenario.title).toBe('Новая редакция');
  });
  for (const golden of GOLDENS.filter(g => g.id.startsWith('GS'))) it(`persists and renders ${golden.id} exactly through G1: ${golden.expected.family}`, async () => {
    let current = await create();
    let oracle = createInitialState(S1, { sessionId: current.projection.sessionId, scenarioVersionId: current.scenarioVersionId });
    for (const action of golden.actions) {
      const requestId = randomUUID();
      const expected = transition(S1, oracle, { requestId, expectedRevision: oracle.revision, action });
      expect(expected.ok).toBe(true); if (!expected.ok) throw new Error('G1 golden failed');
      oracle = expected.state; current = await play(current, action, requestId);
      expect(current.projection).toEqual(expected.public);
      const row = new ArenaRepository(db).session(current.projection.sessionId);
      expect(JSON.parse(row.state_json)).toEqual(oracle);
    }
    expect(current.result?.family).toBe(golden.expected.family);
    expect(current.result?.agreementOffer?.terms ?? null).toEqual(golden.expected.terms);
    const response = await app.inject(`/api/sessions/${current.projection.sessionId}/result`);
    expect(BasicResultSchema.parse(response.json())).toEqual(current.result);
    privacy(response.body, current.projection.knownFacts.map(f => f.id));
    for (const observation of current.result?.observations ?? []) {
      expect(oracle.events.some(event => event.id === observation.eventId && event.turnNumber === observation.turnNumber)).toBe(true);
    }
    const get = await app.inject(`/api/sessions/${current.projection.sessionId}`);
    expect(get.json()).toEqual(current); privacy(get.body, current.projection.knownFacts.map(f => f.id));
    outcomes.push({ trace: golden.id, expected: golden.expected.family, actual: current.result!.family,
      turns: current.projection.turnNumber, batnaComparison: current.result!.batnaComparison });
    if (golden.expected.family === 'POOR_AGREEMENT') {
      expect(current.result?.batnaComparison).toBe('below');
      expect(current.result?.observations.some(o => o.ruleId === 'BELOW_OWN_BATNA')).toBe(true);
    }
    if (golden.id === 'GS1') {
      expect(current.result?.targetReached).toBe(true); expect(current.result?.batnaComparison).toBe('above');
      expect(current.result?.observations.map(o => o.ruleId)).toContain('GROUNDED_ARGUMENT');
    }
  });
  it('returns identical persisted response for duplicate request before checking revision, even after later moves', async () => {
    const initial = await create(); const id = initial.projection.sessionId;
    const command = { requestId: randomUUID(), expectedRevision: 0, action: question('logistics') };
    const url = `/api/sessions/${id}/turns`;
    const results = await Promise.all([app.inject({ method: 'POST', url, payload: command }), app.inject({ method: 'POST', url, payload: command })]);
    expect(results[0]!.statusCode).toBe(200); expect(results[1]!.body).toBe(results[0]!.body);
    const first = SessionViewSchema.parse(results[0]!.json());
    expect(new ArenaRepository(db).turns(id)).toHaveLength(1);
    await play(first, question('payment'));
    const retry = await app.inject({ method: 'POST', url, payload: command }); expect(retry.body).toBe(results[0]!.body);
    expect(new ArenaRepository(db).session(id).revision).toBe(2);
    const conflict = await app.inject({ method: 'POST', url, payload: { ...command, action: question('payment') } });
    expect(conflict.statusCode).toBe(409); expect(conflict.json().code).toBe('IDEMPOTENCY_CONFLICT'); privacy(conflict.body);
  });
  it('allows just one of two different requests with the same expected revision to commit', async () => {
    const initial = await create(); const id = initial.projection.sessionId;
    const results = await Promise.all(['logistics', 'payment'].map(topic => app.inject({ method: 'POST', url: `/api/sessions/${id}/turns`,
      payload: { requestId: randomUUID(), expectedRevision: 0, action: question(topic) } })));
    expect(results.map(r => r.statusCode).sort()).toEqual([200, 409]);
    const rejected = results.find(r => r.statusCode === 409)!;
    expect(rejected.json()).toMatchObject({ code: 'STALE_REVISION', currentRevision: 1 }); privacy(rejected.body);
    expect(new ArenaRepository(db).turns(id)).toHaveLength(1); expect(new ArenaRepository(db).session(id).revision).toBe(1);
  });
  it('rolls back an inserted turn when SQLite fails during the session update; exact retry succeeds after repair', async () => {
    const initial = await create(); const repo = new ArenaRepository(db); const id = initial.projection.sessionId;
    const before = repo.session(id);
    db.exec("CREATE TRIGGER fail_g2_update BEFORE UPDATE ON sessions BEGIN SELECT RAISE(ABORT, 'test-only failure'); END;");
    const payload = { requestId: randomUUID(), expectedRevision: 0, action: question('logistics') };
    const failed = await app.inject({ method: 'POST', url: `/api/sessions/${id}/turns`, payload });
    expect(failed.statusCode).toBe(500); expect(failed.json().code).toBe('INTERNAL_ERROR'); privacy(failed.body);
    expect(repo.turns(id)).toEqual([]); expect(repo.session(id)).toEqual(before); expect(db.inTransaction).toBe(false);
    db.exec('DROP TRIGGER fail_g2_update');
    expect((await app.inject({ method: 'POST', url: `/api/sessions/${id}/turns`, payload })).statusCode).toBe(200);
    expect(repo.turns(id)).toHaveLength(1);
  });
  it('physically impossible valid offer consumes a turn and displays rejection plus exact counteroffer', async () => {
    const result = await play(await create(), offer(supplyTerms(95, 'all14', 50)));
    expect(result.projection.revision).toBe(1);
    expect(result.transcript[0]?.opponentText).toContain('обязательные условия');
    expect(result.transcript[0]?.observations.map(o => o.ruleId)).toContain('PHYSICAL_REJECTION');
    expect(result.projection.activeOffer).not.toBeNull();
  });
  it('keeps an active opponent commitment through an unrelated question and accepts its exact ID', async () => {
    let current = await play(await create(), offer(supplyTerms(90, 'all7', 0)));
    const active = current.projection.activeOffer!;
    current = await play(current, question('payment')); expect(current.projection.activeOffer).toEqual(active);
    const stale = await app.inject({ method: 'POST', url: `/api/sessions/${current.projection.sessionId}/turns`,
      payload: { requestId: randomUUID(), expectedRevision: 2, action: accept('old-offer') } });
    expect(stale.statusCode).toBe(422); expect(new ArenaRepository(db).session(current.projection.sessionId).revision).toBe(2); privacy(stale.body);
    current = await play(current, accept(active.id)); expect(current.result?.agreementOffer).toEqual(active);
    expect(current.transcript.at(-1)?.playerText).toContain('Принимаю ваше предложение');
  });
  it('replays with a new ID, the same version, clean private G1 state, and unchanged original', async () => {
    const initial = await create(); let current = await play(initial, question('logistics'));
    current = await play(current, pressure()); current = await play(current, walkAway());
    const id = current.projection.sessionId; const repo = new ArenaRepository(db); const before = repo.session(id);
    const response = await app.inject({ method: 'POST', url: `/api/sessions/${id}/replay`, payload: {} });
    expect(response.statusCode).toBe(201); const replay = SessionViewSchema.parse(response.json()); privacy(response.body);
    expect(replay.projection.sessionId).not.toBe(id); expect(replay.scenarioVersionId).toBe(current.scenarioVersionId);
    expect(replay.replayOf).toBe(id); expect(replay.transcript).toEqual([]);
    expect(JSON.parse(repo.session(replay.projection.sessionId).state_json)).toEqual(createInitialState(S1, {
      sessionId: replay.projection.sessionId, scenarioVersionId: current.scenarioVersionId }));
    expect(repo.session(id)).toEqual(before);
  });
  it('recovers the same session/transcript on database reopen and can continue to agreement', async () => {
    let current = await play(await create(), question('logistics')); current = await play(current, question('payment'));
    const id = current.projection.sessionId; const jars = app.jars; await app.close();
    db = openDatabase(temp.filename);
    app = await buildApp({ NODE_ENV: 'development', HOST: '127.0.0.1', PORT: 3000, DATABASE_PATH: temp.filename }, { database: db }, jars);
    const recovered = await app.inject(`/api/sessions/${id}`); expect(recovered.json()).toEqual(current);
    current = await play(current, acknowledge('cashflow-need')); current = await play(current, argument('logistics-argument'));
    current = await play(current, offer(supplyTerms(95, 'split40at7_rest14', 50))); expect(current.result?.family).toBe('MUTUAL_GAIN');
  });
  it('reloads stored prose without regenerating historical replies', async () => {
    const current = await play(await create(), question('logistics')); const id = current.projection.sessionId;
    const saved = structuredClone(current); saved.transcript[0]!.opponentText = 'Ранее сохранённая публичная реплика.';
    db.prepare('UPDATE turns SET public_response_json = ? WHERE session_id = ?').run(JSON.stringify(saved), id);
    const recovered = await app.inject(`/api/sessions/${id}`); expect(recovered.json().transcript).toEqual(saved.transcript);
    const next = await play(saved, question('payment')); expect(next.transcript[0]).toEqual(saved.transcript[0]);
  });
  for (const corrupt of ['{invalid', '{}', 'schema-valid-incoherent']) it(`fails closed on corrupt persisted state: ${corrupt}`, async () => {
    const current = await create(); const id = current.projection.sessionId;
    const altered = createInitialState(S1, { sessionId: id, scenarioVersionId: current.scenarioVersionId }); altered.revision = 1;
    db.prepare('UPDATE sessions SET state_json = ? WHERE id = ?').run(corrupt === 'schema-valid-incoherent' ? JSON.stringify(altered) : corrupt, id);
    for (const url of [`/api/sessions/${id}`, `/api/sessions/${id}/result`]) {
      const response = await app.inject(url); expect(response.statusCode).toBe(500); expect(response.json().code).toBe('CORRUPT_STATE'); privacy(response.body);
    }
    expect(new ArenaRepository(db).turns(id)).toHaveLength(0);
  });
  it('rejects a corrupt definition hash and semantic-invalid stored definition without changing a session', async () => {
    const current = await create(); const id = current.projection.sessionId;
    db.exec('DROP TRIGGER scenario_version_immutable_update'); // Test-only corruption, isolated file.
    const altered = structuredClone(S1); altered.participants[1].utility.unary[0]!.cells.pop();
    db.prepare('UPDATE scenario_versions SET definition_json = ?, definition_hash = ?').run(JSON.stringify(altered), hashBody(altered));
    const response = await app.inject(`/api/sessions/${id}`); expect(response.statusCode).toBe(500); expect(response.json().code).toBe('CORRUPT_STATE'); privacy(response.body);
    expect(new ArenaRepository(db).session(id).revision).toBe(0);
  });
  it('validates body/params, unknown resources, terminal/result state, and safe errors', async () => {
    const current = await create(); const id = current.projection.sessionId;
    const base = { requestId: randomUUID(), expectedRevision: 0, action: question('logistics') };
    for (const [payload, status] of [[{}, 400], [{ ...base, extra: 'private' }, 400],
      [{ ...base, action: argument('cashflow-argument') }, 422], [{ ...base, action: acknowledge('cashflow-need') }, 422],
      [{ ...base, action: offer(supplyTerms(97, 'all7', 0)) }, 422], [{ ...base, action: { ...offer(supplyTerms(95, 'all7', 0)), terms: [{ issueId: 'PRICE', valueId: '95' }, { issueId: 'PRICE', valueId: '95' }] } }, 422]] as const) {
      const response = await app.inject({ method: 'POST', url: `/api/sessions/${id}/turns`, payload }); expect(response.statusCode).toBe(status); privacy(response.body);
    }
    const malformed = await app.inject({ method: 'POST', url: `/api/sessions/${id}/turns`, headers: { 'content-type': 'application/json' }, payload: '{bad' });
    expect(malformed.statusCode).toBe(400); privacy(malformed.body);
    expect((await app.inject('/api/sessions/not-a-uuid')).statusCode).toBe(404);
    expect((await app.inject(`/api/sessions/${randomUUID()}`)).statusCode).toBe(404);
    expect((await app.inject({ method: 'POST', url: '/api/sessions', payload: { scenarioVersionId: randomUUID() } })).statusCode).toBe(404);
    expect((await app.inject(`/api/sessions/${id}/result`)).statusCode).toBe(409);
    expect((await app.inject({ method: 'POST', url: `/api/sessions/${id}/replay`, payload: {} })).statusCode).toBe(409);
    expect(new ArenaRepository(db).session(id).revision).toBe(0);
    const final = await play(current, walkAway());
    const terminal = await app.inject({ method: 'POST', url: `/api/sessions/${id}/turns`, payload: { ...base, expectedRevision: final.projection.revision } });
    expect(terminal.statusCode).toBe(409); expect(terminal.json().code).toBe('SESSION_TERMINAL'); privacy(terminal.body);
  });
  it('keeps damaging wording distinct from respectful firmness through HTTP and rendering', async () => {
    const neutral = await play(await create(), question('logistics'));
    const accusatory = await play(await create(), question('logistics', 'accusatory'));
    expect(neutral.projection.knownFacts.some(f => f.id === 'logistics-saving')).toBe(true);
    expect(accusatory.projection.knownFacts.some(f => f.id === 'logistics-saving')).toBe(false);
    expect(accusatory.transcript[0]?.playerText).toContain('не хотите идти навстречу');
    expect(accusatory.transcript[0]?.observations.map(o => o.ruleId)).toContain('DAMAGING_TONE');
    const firm = await play(await create(), pressure('respectful_firm'));
    expect(firm.transcript[0]?.observations.map(o => o.ruleId)).not.toContain('DAMAGING_TONE');
  });
});

it('upgrades an existing G0 file once, retaining original sentinel and migration timestamp', () => {
  const temp = temporaryDatabase(); mkdirSync(join(temp.directory, 'nested'), { recursive: true });
  let db = new Driver(temp.filename);
  try {
    db.exec(`CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))) STRICT;
      INSERT INTO schema_migrations VALUES(1, 'foundation_metadata', '2026-09-16T00:00:00Z');
      CREATE TABLE foundation_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL) STRICT;
      INSERT INTO foundation_metadata VALUES('sentinel', 'keep-g0');`);
    db.close(); db = openDatabase(temp.filename);
    const versions = db.prepare('SELECT * FROM schema_migrations ORDER BY version').all();
    expect(versions).toHaveLength(5); expect(versions[0]).toMatchObject({ version: 1, applied_at: '2026-09-16T00:00:00Z' });
    db.close(); db = openDatabase(temp.filename); expect(db.prepare('SELECT * FROM schema_migrations ORDER BY version').all()).toEqual(versions);
    expect(db.prepare('SELECT value FROM foundation_metadata').get()).toEqual({ value: 'keep-g0' });
  } finally { if (db.open) db.close(); temp.cleanup(); }
});

it('renders authority rejection from real G1 events without its private thresholds', () => {
  const scenario = structuredClone(S1); scenario.participants[1].authority.allowedValues[0]!.valueIds = ['100', '105', '110', '115'];
  const initial = createInitialState(scenario, { sessionId: randomUUID(), scenarioVersionId: randomUUID() });
  const action = offer(supplyTerms(95, 'split40at7_rest14', 50));
  const moved = transition(scenario, initial, { requestId: randomUUID(), expectedRevision: 0, action });
  expect(moved.ok).toBe(true); if (!moved.ok) return;
  const text = renderOpponent(moved.events, moved.public); expect(text).toContain('пределы полномочий');
  expect(text).not.toMatch(/aspiration|utility|reservation/);
  expect(observations(moved.events, moved.public).some(o => o.ruleId === 'AUTHORITY_REJECTION')).toBe(true);
});
it('renders identical canonical replies and own player messages for identical G1 events/projections', () => {
  for (const golden of GOLDENS.filter(g => g.id.startsWith('GS'))) {
    let state: NegotiationState = createInitialState(S1, { sessionId: randomUUID(), scenarioVersionId: randomUUID() });
    for (const action of golden.actions) {
      const before = projectPlayer(S1, state); const moved = transition(S1, state, { requestId: randomUUID(), expectedRevision: state.revision, action });
      expect(moved.ok).toBe(true); if (!moved.ok) throw new Error('G1 failure');
      expect(renderOpponent(moved.events, moved.public)).toBe(renderOpponent(structuredClone(moved.events), structuredClone(moved.public)));
      expect(renderPlayer(action, before)).toBe(renderPlayer(structuredClone(action), structuredClone(before)));
      state = moved.state;
    }
  }
});
afterAll(() => {
  durations.sort((a, b) => a - b);
  mkdirSync(join(PROJECT_ROOT, '.tools'), { recursive: true });
  writeFileSync(join(PROJECT_ROOT, '.tools/g2-api-evidence.json'), JSON.stringify({ outcomes, serializedResponses,
    timing: { sample: durations.length, p95Ms: durations[Math.max(0, Math.ceil(durations.length * .95) - 1)], targetMs: 500, kind: 'local Fastify inject; not production capacity' } }, null, 2));
});
