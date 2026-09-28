import { randomUUID } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import type { CanonicalAction, ScenarioDefinition } from '@arena/contracts';
import { S1, S2 } from '@arena/scenarios';
import { FeedbackReportSchema } from '@arena/contracts/feedback';
import type { FeedbackReport } from '@arena/contracts/feedback';
import { createInitialState } from '@arena/domain';
import { buildApp } from '../src/app.ts';
import { openDatabase } from '../src/database.ts';
import { ArenaRepository } from '../src/repositories/arena-repository.ts';
import { SessionService } from '../src/services/session-service.ts';
import { FeedbackService, compareReports } from '../src/feedback/service.ts';
import { neutral, validateSuggestion } from '../src/feedback/predicates.ts';
import { savedSpan } from '../src/feedback/records.ts';
import { temporaryDatabase } from './helpers.ts';

// Independent application examples, from public controls and finite domain rules.
// No model-evaluation cases, golden traces, witness actions or evaluator-derived expectations.
const q = (topic: string): CanonicalAction => ({ ...neutral(), kind: 'question', primaryTopicId: topic, secondaryTopicId: null });
const ack = (fact: string): CanonicalAction => ({ ...neutral(), kind: 'acknowledge', acknowledgementFactId: fact });
const arg = (id: string): CanonicalAction => ({ ...neutral(), kind: 'argument', argumentId: id });
const exit = (): CanonicalAction => ({ ...neutral(), kind: 'walk_away' });
const offer = (values: Record<string, string>, condition?: string): CanonicalAction => ({
  ...neutral(), kind: 'offer', terms: Object.entries(values).map(([issueId, valueId]) => ({ issueId, valueId })),
  conditionalOn: condition ? [{ issueId: condition, valueId: values[condition]! }] : [],
});
const supply = (price: string, delivery: string, prepay: string, condition?: string) =>
  offer({ PRICE: price, DELIVERY: delivery, PREPAY: prepay }, condition);
const work = (scope: string, deadline: string, help: string, defer: string) =>
  offer({ SCOPE: scope, DEADLINE: deadline, HELP: help, DEFER_REPORT: defer });
const cleaners: (() => void)[] = [];
afterEach(() => { for (const clean of cleaners.splice(0).reverse()) clean(); });
function harness(scenario: ScenarioDefinition = S1, prepared = false) {
  const temp = temporaryDatabase(); const db = openDatabase(temp.filename), repo = new ArenaRepository(db);
  cleaners.push(() => { if (db.open) db.close(); temp.cleanup(); });
  const sessions = new SessionService(repo), feedback = new FeedbackService(repo);
  const version = repo.publish(scenario); let view = sessions.create(version.id);
  const id = view.projection.sessionId;
  const player = scenario.participants.find(p => p.party === 'player')!;
  const preparation = { expectedRevision: 0, goal: 'target', ownBoundary: player.batna.utility, acknowledgedAlternative: true };
  if (prepared) feedback.savePreparation(id, preparation);
  return {
    temp, db, repo, sessions, feedback, version, id, preparation,
    play(action: CanonicalAction, requestId = randomUUID()) {
      view = sessions.playTurn(id, { action, requestId, expectedRevision: view.projection.revision }); return view;
    },
    report() { return feedback.report(id, sessions.get(id).projection.revision); },
    view() { return sessions.get(id); },
  };
}
function goodS1(h: ReturnType<typeof harness>) {
  h.play(q('logistics')); h.play(ack('logistics-saving')); h.play(arg('logistics-argument'));
  h.play(q('payment')); return h.play(supply('95', 'split40at7_rest14', '50'));
}
function goodS2(h: ReturnType<typeof harness>) {
  h.play(q('priorities')); h.play(q('resources')); h.play(ack('report-deferrable'));
  h.play(arg('resource-argument')); return h.play(work('full', '2', '1', '1'));
}
function check(r: FeedbackReport, id: string) { return r.dimensions.flatMap(d => d.checks).find(c => c.id === id)!; }

describe('deterministic feedback over committed application records', () => {
  it('S1 prepared agreement: independently calculated 64 utility and 100 process, separate facts', () => {
    const h = harness(S1, true), ended = goodS1(h), before = JSON.stringify(h.view());
    const r = h.report();
    expect(ended.result?.family).toBe('MUTUAL_GAIN'); expect(ended.result?.playerUtility).toBe(64); // 170 - 95 - 5 - 6
    expect(r.overall.score).toBe(100); expect(r.overall.applicableChecks).toBe(7); expect(r.overall.progressCredits).toBe(5);
    expect(r.dimensions.map(d => d.weight)).toEqual([15, 25, 20, 15, 15, 10]);
    expect(r.outcome).toEqual(ended.result); expect(JSON.stringify(h.view())).toBe(before);
  });
  it('S2 prepared agreement: independently calculated 47 utility and linked evidence', () => {
    const h = harness(S2, true); goodS2(h); const r = h.report();
    expect(r.outcome.playerUtility).toBe(47); // 65 - 8 - 10
    expect(r.overall.score).toBe(100); expect(check(r, 'interests.use').status).toBe('passed');
    expect(check(r, 'interests.use').evidenceIds.map(id => r.evidence.find(e => e.id === id)?.turnNumber)).toEqual([3, 5]);
  });
  it('poor S2 agreement retains utility 20 and independent weighted process 44.12', () => {
    const h = harness(S2, true); h.play(q('resources')); h.play(ack('helper-available')); h.play(work('core', '5', '0', '0'));
    const r = h.report();
    expect(r.outcome.family).toBe('POOR_AGREEMENT'); expect(r.outcome.playerUtility).toBe(20);
    expect(r.overall.score).toBe(44.12); // (15*100 +25*50 +20*0 +15*0 +10*100)/85
    expect(check(r, 'interests.use').status).toBe('failed'); expect(check(r, 'value.mutual').status).toBe('failed');
  });
  it('no agreement can retain mutual-package process credit and 70 process', () => {
    const h = harness(S1, true);
    h.play(supply('95', 'split40at7_rest14', '50')); h.play(q('logistics'));
    h.play(ack('logistics-saving')); h.play(arg('logistics-argument')); h.play(exit());
    const r = h.report();
    expect(r.outcome.family).toBe('NO_AGREEMENT'); expect(r.outcome.playerUtility).toBeNull();
    expect(check(r, 'value.mutual').status).toBe('passed'); expect(r.overall.score).toBe(70);
  });
  it('legacy preparation is unobservable despite defaults and enough behavioral credit', () => {
    const h = harness(); goodS1(h); const r = h.report();
    expect(r.preparation).toBeNull(); expect(r.overall.progressCredits).toBe(5);
    expect(check(r, 'preparation.goal')).toMatchObject({ status: 'unobservable', applicability: 'applicable', evidenceSufficiency: 'missing' });
    expect(r.overall.score).toBeNull(); expect(r.overall.missingChecks).toEqual(['preparation.goal', 'preparation.boundary']);
  });
  it('early exit distinguishes a missed opportunity, no opportunity and missing evidence', () => {
    const h = harness(); h.play(exit()); const r = h.report();
    expect(check(r, 'interests.discovery').status).toBe('failed');
    expect(check(r, 'argument.objection').status).toBe('not_applicable');
    expect(check(r, 'preparation.goal').status).toBe('unobservable');
    expect(check(r, 'relationship.pressure').status).toBe('passed');
    expect(r.overall.score).toBeNull(); expect(r.overall.progressCredits).toBe(0);
    const e = r.evidence.find(e => e.id === check(r, 'interests.discovery').evidenceIds[0])!;
    expect(e).toMatchObject({ kind: 'window', quote: null, window: { from: 1, to: 1 } });
  });
  it('prepared early exit still does not get a perfect overall score', () => {
    const h = harness(S2, true); h.play(exit()); expect(h.report().overall.score).toBeNull();
  });
  it('request retries and repeated facts/questions cannot multiply accepted progress', () => {
    const h = harness(S1, true), requestId = randomUUID();
    const first = h.play(q('logistics'), requestId);
    expect(h.sessions.playTurn(h.id, { requestId, expectedRevision: 0, action: q('logistics') })).toEqual(first);
    h.play(q('logistics')); h.play(ack('logistics-saving')); h.play(ack('logistics-saving')); h.play(exit());
    const r = h.report(); expect(r.overall.progressCredits).toBe(2); expect(r.overall.score).toBeNull();
    expect(h.repo.turns(h.id)).toHaveLength(5);
    expect(new Set(r.overall.progressEvidenceIds).size).toBe(2);
  });
  it('an unrelated acknowledged fact does not earn linked-use credit', () => {
    const h = harness(S2, true);
    h.play(q('priorities')); h.play(q('resources')); h.play(ack('report-deferrable')); h.play(arg('resource-argument'));
    h.play(work('core', '2', '1', '0')); const r = h.report();
    expect(check(r, 'interests.use').status).toBe('failed'); expect(check(r, 'argument.grounded').status).toBe('passed');
  });
  it('a changed feasible package responds to the actual recorded capacity objection', () => {
    const h = harness(S2, true); h.play(work('full', '2', '0', '0')); h.play(work('core', '5', '0', '0'));
    if (!h.view().result) h.play(exit());
    const r = h.report(), c = check(r, 'argument.objection');
    expect(c.status).toBe('passed'); expect(c.evidenceIds.map(id => r.evidence.find(e => e.id === id)?.turnNumber)).toEqual([1, 2]);
  });
  it('ignoring an actual objection is a failure, not N/A', () => {
    const h = harness(S2, true); h.play(work('full', '2', '0', '0')); h.play(q('resources')); h.play(exit());
    expect(check(h.report(), 'argument.objection').status).toBe('failed');
  });
  it('Pareto credit compares the preceding own offers without requiring agreement', () => {
    const h = harness(S1, true); h.play(supply('110', 'all7', '50')); h.play(supply('95', 'split40at7_rest14', '50'));
    if (!h.view().result) h.play(exit());
    expect(check(h.report(), 'value.pareto').status).toBe('passed'); // own 54->64; opponent 26->27
  });
  it('genuine reciprocal exchange earns credit', () => {
    const h = harness(S1, true); h.play(supply('100', 'all7', '0')); h.play(supply('95', 'split40at7_rest14', '50', 'PRICE'));
    if (!h.view().result) h.play(exit());
    expect(check(h.report(), 'concession.reciprocal').status).toBe('passed');
  });
  it('a decorative condition earns no reciprocity and cannot hide wasteful concession', () => {
    const h = harness(S1, true); h.play(supply('95', 'split40at7_rest14', '50')); h.play(supply('110', 'all7', '50', 'PREPAY')); h.play(exit());
    const r = h.report(); expect(check(r, 'concession.reciprocal').status).toBe('failed');
    expect(check(r, 'concession.discipline').status).toBe('failed'); // own 64->54, opponent 27->26
  });
  it('unrepaired tension is a failure and its suggested alternative is validated at the original turn', () => {
    const h = harness(S1, true); h.play({ ...neutral(), kind: 'pressure', tone: 'threat' }); h.play(exit());
    const r = h.report(); expect(check(r, 'relationship.repair').status).toBe('failed');
    expect(r.suggestions[0]).toMatchObject({ checkId: 'relationship.pressure', priorRevision: 0, validation: 'prior_state',
      action: { kind: 'pressure', tone: 'respectful_firm' } });
  });
  it('warning removal without a specific causal binding is unobservable, not successful repair', () => {
    const h = harness(S1, true);
    for (let i = 0; i < 3; i++) h.play({ ...neutral(), kind: 'pressure', tone: 'threat' });
    h.play(ack('launch-bound')); h.play(exit()); const r = h.report();
    expect(check(r, 'relationship.repair').status).toBe('unobservable'); expect(r.overall.score).toBeNull();
  });
  it('valid-looking suggestions reject unknown facts, unavailable arguments, stale offers and impossible terms', () => {
    const before = createInitialState(S2, { sessionId: 'synthetic', scenarioVersionId: 'synthetic' });
    expect(validateSuggestion(S2, before, arg('resource-argument'))).toBeNull();
    expect(validateSuggestion(S2, before, ack('helper-available'))).toBeNull();
    expect(validateSuggestion(S2, before, { ...neutral(), kind: 'accept', offerId: 'old:offer:1:opponent' })).toBeNull();
    expect(validateSuggestion(S2, before, work('full', '2', '0', '0'))).toBeNull();
    expect(validateSuggestion(S2, before, q('resources'))?.kind).toBe('question');
  });
  it('preparation is explicit, validated, idempotent and immutable before and after first move', () => {
    const h = harness();
    expect(() => h.feedback.savePreparation(h.id, { ...h.preparation, acknowledgedAlternative: false })).toThrow();
    expect(() => h.feedback.savePreparation(h.id, { ...h.preparation, ownBoundary: 0 })).toThrow();
    const saved = h.feedback.savePreparation(h.id, h.preparation);
    expect(h.feedback.savePreparation(h.id, h.preparation)).toEqual(saved);
    expect(() => h.feedback.savePreparation(h.id, { ...h.preparation, goal: 'batna' })).toThrow();
    expect(() => h.db.prepare('UPDATE session_preparation SET record_json = ?').run('{}')).toThrow(/immutable/);
    h.play(exit()); expect(() => h.feedback.savePreparation(h.id, h.preparation)).toThrow(/первого хода/);
    expect(h.feedback.preparation(h.id)).toEqual(saved);
  });
  it('a rejected turn and an unconfirmed draft are never report evidence', () => {
    const h = harness(S2, true); expect(() => h.play(arg('resource-argument'))).toThrow();
    const draft = work('full', '2', '1', '1'); expect(draft.kind).toBe('offer');
    h.play(exit()); const r = h.report();
    expect(r.terminalRevision).toBe(1); expect(check(r, 'argument.grounded').status).toBe('failed'); expect(check(r, 'value.mutual').status).toBe('failed');
  });
  it('exact saved Cyrillic/emoji text is quoted, never regenerated with current templates', () => {
    const h = harness(S1, true); goodS1(h);
    const row = h.repo.turns(h.id).at(-1)!, response = JSON.parse(row.public_response_json);
    const text = 'Условия 😀: поставка к запуску — да.';
    response.transcript.at(-1).playerText = text;
    h.db.prepare('UPDATE turns SET public_response_json = ? WHERE session_id = ? AND turn_number = ?').run(JSON.stringify(response), h.id, row.turn_number);
    const r = h.report(), e = r.evidence.find(e => e.kind === 'guided_action' && e.turnNumber === 5)!;
    expect(e.quote).toEqual({ speaker: 'player', text, start: 0, end: text.length });
    expect(savedSpan('А😀Б', 1, 3)).toBe('😀');
    expect(() => savedSpan('А😀Б', 1, 2)).toThrow(); expect(() => savedSpan('А😀Б', 2, 3)).toThrow();
    expect(() => savedSpan('А😀Б', -1, 2)).toThrow(); expect(() => savedSpan('А😀Б', 0, 7)).toThrow();
  });
  it('cross-session event references fail closed without private diagnostics', () => {
    const h = harness(); h.play(exit()); const row = h.repo.turns(h.id)[0]!;
    const events = JSON.parse(row.events_json); events[0].id = randomUUID() + ':event:1';
    h.db.prepare('UPDATE turns SET events_json = ? WHERE session_id = ?').run(JSON.stringify(events), h.id);
    expect(() => h.report()).toThrow(/сохранён|данн|поврежд/i);
  });
  it('missing historical event instrumentation is explicit and cannot earn absence credit', () => {
    const h = harness(S1, true); h.play(exit()); const row = h.repo.turns(h.id)[0]!;
    const old = JSON.parse(row.events_json) as { id: string; sequence: number; payload: { type: string } }[];
    const events = old.filter(e => e.payload.type !== 'social_state_changed');
    const ids = new Map<string, string>();
    events.forEach((e, i) => { const id = h.id + ':event:' + (i + 1); ids.set(e.id, id); e.id = id; e.sequence = i + 1; });
    const state = JSON.parse(row.state_after_json); state.events = events;
    const response = JSON.parse(row.public_response_json);
    for (const observation of response.transcript[0].observations) observation.eventId = ids.get(observation.eventId);
    response.result.observations = response.transcript[0].observations;
    h.db.prepare('UPDATE turns SET events_json = ?, state_after_json = ?, public_response_json = ? WHERE session_id = ?')
      .run(JSON.stringify(events), JSON.stringify(state), JSON.stringify(response), h.id);
    h.db.prepare('UPDATE sessions SET state_json = ? WHERE id = ?').run(JSON.stringify(state), h.id);
    const r = h.report(); expect(check(r, 'relationship.pressure').status).toBe('unobservable'); expect(r.overall.score).toBeNull();
  });
  it('a missing acknowledgement event stays unobservable even when other event markers survive', () => {
    const h = harness(S1, true); h.play(ack('launch-bound')); h.play(exit());
    const all = JSON.parse(h.repo.turns(h.id).at(-1)!.state_after_json).events as { id: string; sequence: number; payload: { type: string } }[];
    const omitted = all.find(e => e.payload.type === 'fact_acknowledged')!.id;
    const kept = all.filter(e => e.id !== omitted), ids = new Map(kept.map((e, i) => [e.id, h.id + ':event:' + (i + 1)]));
    let finalState: unknown;
    for (const row of h.repo.turns(h.id)) {
      const rewrite = (events: typeof all) => events.filter(e => e.id !== omitted).map(e => ({
        ...e, id: ids.get(e.id)!, sequence: Number(ids.get(e.id)!.split(':').at(-1)),
      }));
      const state = JSON.parse(row.state_after_json); state.events = rewrite(state.events); finalState = state;
      const response = JSON.parse(row.public_response_json);
      for (const t of response.transcript) t.observations = t.observations.filter((o: { eventId: string }) => o.eventId !== omitted)
        .map((o: { eventId: string }) => ({ ...o, eventId: ids.get(o.eventId)! }));
      if (response.result) response.result.observations = response.transcript.flatMap((t: { observations: unknown[] }) => t.observations);
      h.db.prepare('UPDATE turns SET events_json = ?, state_after_json = ?, public_response_json = ? WHERE session_id = ? AND turn_number = ?')
        .run(JSON.stringify(rewrite(JSON.parse(row.events_json))), JSON.stringify(state), JSON.stringify(response), h.id, row.turn_number);
    }
    h.db.prepare('UPDATE sessions SET state_json = ? WHERE id = ?').run(JSON.stringify(finalState), h.id);
    const r = h.report(); expect(check(r, 'interests.use').status).toBe('unobservable'); expect(r.overall.score).toBeNull();
  });
  it('a saved public outcome inconsistent with the committed domain outcome is rejected', () => {
    const h = harness(S1, true); goodS1(h); const row = h.repo.turns(h.id).at(-1)!;
    const response = JSON.parse(row.public_response_json); response.result.playerUtility = 89;
    h.db.prepare('UPDATE turns SET public_response_json = ? WHERE session_id = ? AND turn_number = ?').run(JSON.stringify(response), h.id, row.turn_number);
    expect(() => h.report()).toThrow();
  });

  it('report identity and outcome survive a real file database reopening unchanged', () => {
    const h = harness(S2, true); goodS2(h); const r = h.report(), before = h.view();
    h.db.close(); const reopened = openDatabase(h.temp.filename);
    try {
      const repo = new ArenaRepository(reopened);
      expect(new FeedbackService(repo).report(h.id, 5)).toEqual(r);
      expect(new SessionService(repo).get(h.id)).toEqual(before);
    } finally { reopened.close(); }
  });
  it('direct replay compares shared checks, rejects unrelated/stale targets and leaves predecessor intact', () => {
    const h = harness(S1, true); goodS1(h); const before = h.report(), original = h.view();
    let replay = h.sessions.replay(h.id);
    replay = h.sessions.playTurn(replay.projection.sessionId, { requestId: randomUUID(), expectedRevision: 0, action: exit() });
    const c = h.feedback.comparison(replay.projection.sessionId, 1, h.id);
    expect(c.comparable).toBe(true); expect(c.excludedChecks).toContain('Явно выбрана достижимая цель');
    expect(c.sharedChecks.find(x => x.id === 'interests.discovery')).toMatchObject({ before: 'passed', after: 'failed' });
    expect(() => h.feedback.comparison(replay.projection.sessionId, 1, randomUUID())).toThrow();
    expect(() => h.feedback.comparison(replay.projection.sessionId, 2, h.id)).toThrow();
    expect(h.view()).toEqual(original); expect(h.report()).toEqual(before);
  });
  it('different config, definition or evaluator policies keep factual outcomes but refuse score comparison', () => {
    const h = harness(S1, true); goodS1(h); const r = h.report();
    for (const field of ['configHash', 'definitionHash', 'rubricVersion', 'evaluatorVersion'] as const) {
      const changed = { ...r, [field]: field === 'definitionHash' ? 'a'.repeat(64) : 'another-version' };
      const c = compareReports(r, changed);
      expect(c.comparable).toBe(false); expect(c.sharedChecks).toEqual([]); expect(c.currentOutcome).toEqual(r.outcome);
    }
  });
  it('HTTP rejects stale/malformed references, exposes only terminal policy and does not mutate on errors', async () => {
    const h = harness(S2, true); goodS2(h);
    const app = await buildApp({ NODE_ENV: 'test', HOST: '127.0.0.1', PORT: 3000, DATABASE_PATH: h.temp.filename }, { database: h.db });
    try {
      const before = h.view(), report = h.report();
      for (const suffix of ['?revision=4', '?revision=5&eventId=unrelated', '?revision=99']) {
        expect((await app.inject({ url: '/api/sessions/' + h.id + '/feedback' + suffix })).statusCode).toBeGreaterThanOrEqual(400);
      }
      const response = await app.inject({ url: '/api/sessions/' + h.id + '/feedback?revision=5' });
      expect(response.statusCode).toBe(200); expect(FeedbackReportSchema.parse(response.json())).toEqual(report);
      const body = response.body;
      expect(body).not.toMatch(/"opponentUtility"|"opponentBatna"|"trust"|"tension"|"participants"|"witnessTraces"/);
      expect(body).not.toContain(S2.participants[1]!.privateBrief); expect(body).not.toContain(S2.participants[1]!.batna.description);
      for (const f of S2.facts.filter(f => !before.projection.knownFacts.some(k => k.id === f.id))) {
        expect(body).not.toContain(f.id); expect(body).not.toContain(f.text);
      }
      expect(h.view()).toEqual(before); expect(h.report()).toEqual(report);
    } finally { await app.close(); }
  });
  it('built browser contains no hidden scenario definitions, utility tables or witness identifiers', () => {
    const root = join(process.cwd(), 'apps/web/dist/assets');
    const bundle = readdirSync(root).filter(p => p.endsWith('.js')).map(p => readFileSync(join(root, p), 'utf8')).join('');
    for (const s of [S1, S2]) {
      expect(bundle).not.toContain(s.participants[1]!.privateBrief);
      expect(bundle).not.toContain(s.participants[1]!.batna.description);
      for (const trace of s.validation.witnessTraces) expect(bundle).not.toContain(trace.id);
      for (const f of s.facts.filter(f => f.visibility === 'hidden')) expect(bundle).not.toContain(f.text);
    }
  });
});
