import { randomUUID } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { CanonicalAction } from '@arena/contracts';
import { PublishedScenarioSchema, SessionViewSchema } from '@arena/contracts/g2';
import type { SessionView } from '@arena/contracts/g2';
import { PublishedCatalogScenarioSchema, ReferenceCatalogSchema, formatIssueValue } from '@arena/contracts/catalog';
import { S1, S2, acknowledge, argument, offer, question, workloadTerms, walkAway, accept } from '@arena/scenarios';
import { buildApp } from './authenticated-fixture.ts';
import { openDatabase } from '../src/database.ts';
import { ArenaRepository } from '../src/repositories/arena-repository.ts';
import { referencePreview } from '../src/services/session-service.ts';
import { temporaryDatabase } from './helpers.ts';
import { WEB_ROOT } from '../src/paths.ts';

// Independently written application actions; no ML corpus or evaluation fixtures.
const cases: { family: string; actions: CanonicalAction[]; utility: number | null }[] = [
  { family: 'MUTUAL_GAIN', utility: 47, actions: [question('priorities'), question('resources'), acknowledge('report-deferrable'), argument('resource-argument'), offer(workloadTerms('full', 2, 1, 1))] },
  { family: 'ACCEPTABLE_PARTIAL', utility: 32, actions: [question('resources'), acknowledge('helper-available'), offer(workloadTerms('core', 2, 1, 0))] },
  { family: 'POOR_AGREEMENT', utility: 20, actions: [question('resources'), acknowledge('helper-available'), offer(workloadTerms('core', 5, 0, 0))] },
  { family: 'NO_AGREEMENT', utility: null, actions: [offer(workloadTerms('full', 2, 0, 0)), walkAway()] },
];
const secretKeys = /"(?:trust|tension|resourceAuthorizations|opponentUtility|opponentBatna|witnessTraces|definition_json|participants)"\s*:/;
function publicOnly(value: unknown, known: string[] = []) {
  const body = JSON.stringify(value); expect(body).not.toMatch(secretKeys);
  for (const scenario of [S1, S2]) {
    expect(body).not.toContain(scenario.participants[1].privateBrief);
    expect(body).not.toContain(scenario.participants[1].batna.description);
    for (const fact of scenario.facts.filter(f => f.visibility === 'hidden' && !known.includes(f.id))) {
      expect(body).not.toContain(fact.text); expect(body).not.toContain(fact.id);
    }
  }
}
describe('application catalog and S2 through the existing transaction', () => {
  let temp: ReturnType<typeof temporaryDatabase>;
  let db: ReturnType<typeof openDatabase>;
  let app: Awaited<ReturnType<typeof buildApp>>;
  beforeEach(async () => {
    temp = temporaryDatabase(); db = openDatabase(temp.filename);
    app = await buildApp({ NODE_ENV: 'development', HOST: '127.0.0.1', PORT: 3000, DATABASE_PATH: temp.filename }, { database: db });
  });
  afterEach(async () => { await app.close(); temp.cleanup(); });
  async function publish(key = 's2') {
    const r = await app.inject({ method: 'POST', url: `/api/admin/reference-scenarios/${key}/publish`, payload: {} });
    expect(r.statusCode, r.body).toBe(200); publicOnly(r.json());
    return PublishedCatalogScenarioSchema.parse(r.json());
  }
  async function create(key = 's2') {
    const version = await publish(key);
    const r = await app.inject({ method: 'POST', url: '/api/sessions', payload: { scenarioVersionId: version.id } });
    expect(r.statusCode).toBe(201); publicOnly(r.json()); return SessionViewSchema.parse(r.json());
  }
  async function turn(s: SessionView, action: CanonicalAction, requestId = randomUUID()) {
    const r = await app.inject({ method: 'POST', url: `/api/sessions/${s.projection.sessionId}/turns`,
      payload: { requestId, expectedRevision: s.projection.revision, action } });
    expect(r.statusCode, r.body).toBe(200);
    const next = SessionViewSchema.parse(r.json()); publicOnly(next, next.projection.knownFacts.map(f => f.id)); return next;
  }
  it('publishes the original definitions once, with additive public catalog schemas and safe unknown IDs', async () => {
    const catalog = ReferenceCatalogSchema.parse((await app.inject('/api/reference-scenarios')).json());
    expect(catalog.map(p => p.templateId)).toEqual([S1.templateId, S2.templateId]); publicOnly(catalog);
    const s1 = await publish('s1'); expect(PublishedScenarioSchema.safeParse(s1).success).toBe(true);
    const s2 = await publish(); expect(await publish()).toEqual(s2);
    const repo = new ArenaRepository(db); expect(repo.definition(repo.version(s1.id))).toEqual(S1);
    expect(repo.definition(repo.version(s2.id))).toEqual(S2);
    expect(repo.versions()).toHaveLength(2);
    for (const key of ['s3', 'constructor', '__proto__']) {
      const r = await app.inject({ method: 'POST', url: `/api/admin/reference-scenarios/${key}/publish`, payload: {} });
      expect(r.statusCode).toBe(404); expect(r.json().code).toBe('NOT_FOUND'); publicOnly(r.json());
    }
    const invalid = await app.inject({ method: 'POST', url: '/api/admin/reference-scenarios/s2/publish', payload: { definition: S2 } });
    expect(invalid.statusCode).toBe(400); publicOnly(invalid.json());
  });
  for (const fixture of cases) it(`S2 ${fixture.family}: result evidence, terminal rejection and clean replay`, async () => {
    let s = await create();
    for (const action of fixture.actions) s = await turn(s, action);
    expect(s.result?.family).toBe(fixture.family); expect(s.result?.playerUtility).toBe(fixture.utility);
    expect(s.result?.playerBatna).toBe(25); expect(s.result?.playerTarget).toBe(45);
    const repo = new ArenaRepository(db); const turns = repo.turns(s.projection.sessionId);
    for (const observation of s.result!.observations) {
      const events = JSON.parse(turns[observation.turnNumber - 1]!.events_json) as { id: string }[];
      expect(events.some(e => e.id === observation.eventId)).toBe(true);
    }
    const url = `/api/sessions/${s.projection.sessionId}`;
    const terminal = await app.inject({ method: 'POST', url: url + '/turns', payload: { requestId: randomUUID(), expectedRevision: s.projection.revision, action: walkAway() } });
    expect(terminal.statusCode).toBe(409); expect(terminal.json().code).toBe('SESSION_TERMINAL');
    const replay = await app.inject({ method: 'POST', url: url + '/replay', payload: {} });
    expect(replay.statusCode).toBe(201); const fresh = SessionViewSchema.parse(replay.json());
    expect(fresh.scenarioVersionId).toBe(s.scenarioVersionId); expect(fresh.replayOf).toBe(s.projection.sessionId);
    expect(fresh.projection.sessionId).not.toBe(s.projection.sessionId);
    expect(fresh.projection.revision).toBe(0); expect(fresh.transcript).toEqual([]); publicOnly(fresh);
    expect((await app.inject(url)).json()).toEqual(s);
  });
  it('enforces capacity and specialist proposal authority on the server, including resource grants', async () => {
    let s = await create();
    s = await turn(s, offer(workloadTerms('full', 2, 0, 0)));
    expect(s.result).toBeNull(); expect(s.transcript[0]!.observations.some(o => o.ruleId === 'PHYSICAL_REJECTION')).toBe(true);
    expect(s.projection.activeOffer!.terms.find(t => t.issueId === 'HELP')?.valueId).toBe('0');
    let state = JSON.parse(new ArenaRepository(db).session(s.projection.sessionId).state_json);
    expect(state.resourceAuthorizations).toEqual([]);
    // A manager offer grants the helper; even a capacity-invalid package never bypasses feasibility.
    s = await turn(s, offer(workloadTerms('full', 2, 1, 0)));
    expect(s.result).toBeNull(); expect(s.transcript.at(-1)!.observations.some(o => o.ruleId === 'PHYSICAL_REJECTION')).toBe(true);
    state = JSON.parse(new ArenaRepository(db).session(s.projection.sessionId).state_json);
    expect(state.resourceAuthorizations).toContain('helper-authorization');
  });
  it('keeps duplicate results stable, rejects stale proposals, and accepts the exact active terms', async () => {
    const first = await create(); const action = offer(workloadTerms('full', 2, 0, 0)); const requestId = randomUUID();
    const s = await turn(first, action, requestId); expect(await turn(first, action, requestId)).toEqual(s);
    const oldOffer = s.projection.activeOffer!;
    const next = await turn(s, offer(workloadTerms('full', 2, 1, 0)));
    const url = `/api/sessions/${s.projection.sessionId}/turns`;
    for (const [revision, code] of [[s.projection.revision, 'STALE_REVISION'], [next.projection.revision, 'DOMAIN_REJECTED']] as const) {
      const r = await app.inject({ method: 'POST', url, payload: { requestId: randomUUID(), expectedRevision: revision, action: accept(oldOffer.id) } });
      expect(r.json().code).toBe(code);
    }
    const terms = next.projection.activeOffer!.terms;
    const ended = await turn(next, accept(next.projection.activeOffer!.id));
    expect(ended.result?.agreementOffer?.terms).toEqual(terms);
    expect(new ArenaRepository(db).turns(s.projection.sessionId)).toHaveLength(3);
  });
  it('S1 and S2 reopen through additive preparation migration, with immutable historical version bindings', async () => {
    const s1 = await turn(await create('s1'), question('logistics'));
    const s2 = await turn(await create(), question('resources'));
    const changed = structuredClone(S2); changed.title = 'Следующая редакция S2';
    const repo = new ArenaRepository(db); const newer = repo.immediate(() => repo.publish(changed));
    expect(newer.id).not.toBe(s2.scenarioVersionId);
    expect(() => db.prepare('UPDATE scenario_versions SET definition_json = ? WHERE id = ?').run('{}', s2.scenarioVersionId)).toThrow();
    const jars = app.jars; await app.close(); db = openDatabase(temp.filename);
    app = await buildApp({ NODE_ENV: 'development', HOST: '127.0.0.1', PORT: 3000, DATABASE_PATH: temp.filename }, { database: db }, jars);
    expect(db.prepare('SELECT version FROM schema_migrations ORDER BY version').all()).toEqual([{ version: 1 }, { version: 2 }, { version: 3 }, { version: 4 }, { version: 5 }]);
    for (const s of [s1, s2]) expect((await app.inject(`/api/sessions/${s.projection.sessionId}`)).json()).toEqual(s);
    expect((await turn(s2, acknowledge('helper-available'))).projection.scenario.title).toBe(S2.title);
  });
  it('renders nominal resource choices without claiming absent resources; ordered scope shows hours', () => {
    const p = referencePreview(S2);
    const help = p.scenario.issues.find(i => i.id === 'HELP')!;
    expect(formatIssueValue(help, help.values[0]!)).toBe('Без помощника');
    const scope = p.scenario.issues.find(i => i.id === 'SCOPE')!;
    expect(formatIssueValue(scope, scope.values[1]!)).toBe('Полный объём (16 часов работы)');
  });
  it('does not bundle private definitions, facts, witness paths or provider code into the frontend', () => {
    const files = readdirSync(join(WEB_ROOT, 'assets')).filter(f => f.endsWith('.js'));
    expect(files.length).toBeGreaterThan(0);
    const bundle = files.map(f => readFileSync(join(WEB_ROOT, 'assets', f), 'utf8')).join('\n');
    for (const scenario of [S1, S2]) {
      expect(bundle).not.toContain(scenario.participants[1].privateBrief);
      for (const fact of scenario.facts.filter(f => f.visibility === 'hidden')) expect(bundle).not.toContain(fact.text);
      expect(bundle).not.toContain(scenario.configFingerprint);
      for (const witness of scenario.validation.witnessTraces) expect(bundle.includes(witness.id), `bundled witness ${witness.id}`).toBe(false);
    }
    // Schema field names can exist in shared Zod code; they are not scenario values.
    expect(/api\.openai\.com|sk-[A-Za-z0-9]{16}/i.test(bundle)).toBe(false);
  });
});
