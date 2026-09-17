import { describe, expect, it } from 'vitest';
import type { CanonicalAction, ScenarioDefinition } from '@arena/contracts';
import { argumentDiscount, aspiration, evaluateAuthority, evaluateConstraints, evaluateUtility, selectCounteroffer, transition } from '../src/index.ts';
import { S1, S2, acknowledge, argument, clarification, offer, pressure, question, supplyTerms, workloadTerms } from '../../scenarios/src/index.ts';
import { initial, play, step } from '../../scenarios/test/helpers.ts';
import { s1Prefix } from '../../scenarios/test/goldens.ts';

describe('social state, disclosure and anti-farming', () => {
  it.each([['neutral', 50, 20], ['friendly', 60, 10], ['skeptical', 40, 30]] as const)('%s starts at %i/%i', (tone, trust, tension) => {
    const scenario = structuredClone(S1); scenario.policy.tone = tone;
    expect(initial(scenario)).toMatchObject({ trust, tension });
  });
  it.each([['beginner', 35, 8], ['normal', 45, 15], ['advanced', 55, 20]] as const)('%s exact disclosure equality and premium', (difficulty, threshold, premium) => {
    const scenario = structuredClone(S1); scenario.policy.difficulty = difficulty;
    const equal = initial(scenario); equal.trust = threshold - 4;
    const below = initial(scenario); below.trust = threshold - 5;
    expect(step(scenario, equal, question('logistics')).knownFactIds).toContain('logistics-saving');
    expect(step(scenario, below, question('logistics')).knownFactIds).not.toContain('logistics-saving');
    expect(aspiration(scenario, initial(scenario), supplyTerms(95, 'split40at7_rest14', 50))).toBe(20 + premium);
  });
  it('a compound question reveals only the primary topic and cannot use its new fact as pre-turn evidence', () => {
    const action = question('logistics'); action.secondaryTopicId = 'payment';
    const state = play(S1, [action]);
    expect(state.knownFactIds).toContain('logistics-saving');
    expect(state.knownFactIds).not.toContain('cashflow-need');
    action.argumentId = 'logistics-argument';
    const start = initial(S1);
    const result = transition(S1, start, { requestId: 'future-fact', expectedRevision: 0, action });
    expect(result).toMatchObject({ ok: false, state: start });
    if (!result.ok) expect(result.errors[0]?.code).toBe('UNAVAILABLE_ARGUMENT');
  });
  it('repeated question, acknowledgement and argument earn no further social effect or credit', () => {
    const first = play(S1, [question('logistics'), acknowledge('logistics-saving'), argument('logistics-argument')]);
    const repeated = play(S1, [question('logistics'), acknowledge('logistics-saving'), argument('logistics-argument')], first);
    expect(repeated).toMatchObject({ trust: first.trust, tension: first.tension, progressCredits: first.progressCredits, groundedArgumentIds: first.groundedArgumentIds });
    expect(repeated.earnedEventKeys).toEqual(first.earnedEventKeys);
  });
  it('compound turn caps trust at +6 and progress at one; skipped rewards are not farmable later', () => {
    const before = play(S1, [question('logistics')]);
    const compound = question('payment'); compound.acknowledgementFactId = 'logistics-saving'; compound.argumentId = 'logistics-argument';
    const after = step(S1, before, compound);
    expect(after.trust - before.trust).toBe(6);
    expect(after.progressCredits - before.progressCredits).toBe(1);
    const repeated = play(S1, [acknowledge('logistics-saving'), argument('logistics-argument'), question('payment')], after);
    expect(repeated.progressCredits).toBe(after.progressCredits);
    expect(repeated.trust).toBe(after.trust);
  });
  it('credits cap at five despite additional meaningful actions', () => {
    const actions = [question('logistics'), question('payment'), acknowledge('logistics-saving'), acknowledge('cashflow-need'), argument('logistics-argument'), argument('cashflow-argument'), acknowledge('launch-bound')];
    const state = play(S1, actions);
    expect(state.progressCredits).toBe(5);
    expect(state.events.filter(event => event.payload.type === 'progress_credit_earned')).toHaveLength(5);
  });
  it('damaging turn suppresses trust, repair, credit and new argument discount, retaining prior applicable discounts', () => {
    const before = play(S1, s1Prefix());
    const compound = offer(supplyTerms(90, 'split40at7_rest14', 50));
    compound.tone = 'threat'; compound.acknowledgementFactId = 'logistics-saving'; compound.argumentId = 'cashflow-argument';
    const after = step(S1, before, compound);
    expect(after).toMatchObject({ trust: before.trust - 15, tension: before.tension + 20, progressCredits: before.progressCredits });
    expect(after.groundedArgumentIds).toEqual(['logistics-argument']);
    expect(argumentDiscount(S1, after, compound.terms)).toBe(2);
    expect(after.earnedEventKeys).not.toContain('ack:logistics-saving');
  });
  it('strongest damaging effect is selected once, including explicit contradiction', () => {
    const action = question('logistics', 'accusatory'); action.contradictsFactId = 'launch-bound';
    expect(play(S1, [action])).toMatchObject({ trust: 40, tension: 20, progressCredits: 0 });
    action.tone = 'threat';
    expect(play(S1, [action])).toMatchObject({ trust: 35, tension: 40 });
  });
  it('trust and tension clip at 0 and 100', () => {
    const high = initial(S1); high.trust = 99; high.tension = 2;
    expect(step(S1, high, acknowledge('launch-bound'))).toMatchObject({ trust: 100, tension: 0 });
    const low = initial(S1); low.trust = 3; low.tension = 95;
    expect(step(S1, low, pressure())).toMatchObject({ trust: 0, tension: 100 });
  });
  it('79 does not warn, 80 warns, then a damaging offer triggers walkaway before any new offer', () => {
    const below = initial(S1); below.tension = 59;
    expect(step(S1, below, pressure())).toMatchObject({ tension: 79, warning: false, terminalReason: null });
    const exact = initial(S1); exact.tension = 60;
    const warned = step(S1, exact, pressure());
    expect(warned).toMatchObject({ tension: 80, warning: true, terminalReason: null });
    const damagingOffer = offer(supplyTerms(115, 'split40at7_rest14', 50)); damagingOffer.tone = 'accusatory';
    const result = step(S1, warned, damagingOffer);
    expect(result.terminalReason).toBe('opponent_walkaway');
    expect(result.lastUserOffer).toBeNull();
    expect(result.events.filter(event => event.turnNumber === 2).some(event => event.payload.type === 'offer_proposed')).toBe(false);
  });
  it.each([['neutral', 76], ['skeptical', 78]] as const)('unused exact acknowledgement repairs a %s warning to tension %i', (tone, tension) => {
    const scenario = structuredClone(S1); scenario.policy.tone = tone;
    const before = initial(scenario); before.warning = true; before.tension = 80;
    expect(step(scenario, before, acknowledge('launch-bound'))).toMatchObject({ tension, warning: false });
    expect(step(scenario, before, clarification())).toMatchObject({ tension: 80, warning: true });
    before.earnedEventKeys.push('ack:launch-bound');
    expect(step(scenario, before, acknowledge('launch-bound'))).toMatchObject({ tension: 80, warning: true });
  });
  it('questions and rejection explain physical/authority boundaries independently of trust', () => {
    const authorityQuery = initial(S1); authorityQuery.trust = 0;
    expect(step(S1, authorityQuery, question('authority')).knownFactIds).toContain('supplier-authority');
    const manager = structuredClone(S1);
    manager.participants[1].roleId = 'account-manager';
    manager.participants[1].authority.allowedValues[0]!.valueIds = ['100', '105', '110', '115'];
    const low = initial(manager); low.trust = 0;
    const rejected = step(manager, low, offer(supplyTerms(95, 'split40at7_rest14', 50)));
    expect(rejected.events.some(event => event.payload.type === 'offer_rejected_authority')).toBe(true);
    expect(rejected.knownFactIds).toContain('supplier-authority');
    expect(rejected.outcome).toBeNull();
  });
  it('empty clarification and elapsed turns never lower aspiration', () => {
    const before = initial(S1);
    const after = play(S1, Array.from({ length: 7 }, () => clarification()), before);
    const terms = supplyTerms(95, 'split40at7_rest14', 50);
    expect(after).toMatchObject({ trust: 50, progressCredits: 0, tension: 20 });
    expect(aspiration(S1, after, terms)).toBe(aspiration(S1, before, terms));
  });
  it('a repeated identical offer cannot earn first-offer or conditional-exchange credit', () => {
    const terms = supplyTerms(90, 'all7', 0);
    const state = play(S1, [offer(terms), offer(terms, [terms[1]!]), offer(terms)]);
    expect(state.progressCredits).toBe(1);
  });
  it('a conditional exchange earns credit only for a new reciprocal change on another issue', () => {
    const first = play(S1, [offer(supplyTerms(90, 'split40at7_rest14', 0))]);
    const terms = supplyTerms(90, 'all7', 50);
    const after = step(S1, first, offer(terms, [{ issueId: 'DELIVERY', valueId: 'all7' }]));
    expect(after.progressCredits).toBe(2);
    expect(after.earnedEventKeys.some(key => key.startsWith('credit:exchange:'))).toBe(true);
    const noImprovement = step(S1, first, offer(supplyTerms(95, 'split40at7_rest14', 0), [{ issueId: 'DELIVERY', valueId: 'split40at7_rest14' }]));
    expect(noImprovement.progressCredits).toBe(1);
  });
  it('returning to an identical offer through another package cannot farm exchange credit', () => {
    const repeated = supplyTerms(95, 'all7', 50);
    const condition = [{ issueId: 'DELIVERY', valueId: 'all7' }];
    const state = play(S1, [offer(supplyTerms(90, 'split40at7_rest14', 0)), offer(repeated, condition), offer(supplyTerms(95, 'split40at7_rest14', 0)), offer(repeated, condition)]);
    expect(state.progressCredits).toBe(2);
    expect(state.events.filter(event => event.payload.type === 'progress_credit_earned' && event.payload.key.startsWith('credit:exchange:'))).toHaveLength(1);
  });
  it('a damaging first feasible offer cannot replay the same one-time credit on a later turn', () => {
    const first = offer(supplyTerms(90, 'split40at7_rest14', 0)); first.tone = 'threat';
    const state = play(S1, [first, offer(first.terms), offer(supplyTerms(95, 'split40at7_rest14', 0))]);
    expect(state.progressCredits).toBe(0);
  });
});

describe('economic policy and role/resource separation', () => {
  it('the aspiration formula has exact trust floors, per-package discounts and reservation floor', () => {
    const terms = supplyTerms(90, 'split40at7_rest14', 50);
    const state = initial(S1); state.progressCredits = 5; state.groundedArgumentIds = ['logistics-argument', 'cashflow-argument'];
    state.trust = 59; expect(aspiration(S1, state, terms)).toBe(21);
    state.trust = 60; expect(aspiration(S1, state, terms)).toBe(20);
    state.trust = 100; expect(aspiration(S1, state, terms)).toBe(20);
    expect(argumentDiscount(S1, state, terms)).toBe(4);
    expect(argumentDiscount(S1, state, supplyTerms(90, 'all7', 50))).toBe(2);
    expect(argumentDiscount(S1, state, supplyTerms(90, 'split40at7_rest14', 0))).toBe(2);
    expect(argumentDiscount(S1, state, supplyTerms(90, 'all7', 0))).toBe(0);
  });
  it('reservation equality is accepted with >=; below reservation never is', () => {
    const state = initial(S1); state.trust = 100; state.progressCredits = 5;
    const equality = step(S1, state, offer(supplyTerms(100, 'split40at7_rest14', 30)));
    expect(equality.terminalReason).toBe('agreed'); expect(equality.outcome?.opponentUtility).toBe(20);
    const below = step(S1, state, offer(supplyTerms(95, 'split40at7_rest14', 30)));
    expect(below.terminalReason).toBeNull();
  });
  it('max trust, credit and arguments cannot override physical impossibility or authority', () => {
    const scenarios: ScenarioDefinition[] = [structuredClone(S1), structuredClone(S2)];
    for (const scenario of scenarios) {
      const state = initial(scenario); state.trust = 100; state.progressCredits = 5; state.groundedArgumentIds = scenario.arguments.map(binding => binding.id);
      const impossible = scenario.templateId === S1.templateId ? supplyTerms(115, 'all14', 50) : workloadTerms('full', 2, 0, 0);
      const result = step(scenario, state, offer(impossible));
      expect(result.outcome).toBeNull();
      expect(result.events.some(event => event.payload.type === 'offer_rejected_physical')).toBe(true);
      expect(result.turnNumber).toBe(1);
    }
    const scenario = structuredClone(S1); scenario.participants[1].authority.allowedValues[0]!.valueIds = ['100', '105', '110', '115'];
    const state = initial(scenario); state.trust = 100; state.progressCredits = 5;
    const result = step(scenario, state, offer(supplyTerms(95, 'split40at7_rest14', 50)));
    expect(result.events.some(event => event.payload.type === 'offer_rejected_authority')).toBe(true);
    expect(result.outcome).toBeNull();
  });
  it('specialist cannot initiate help; team lead can; a player offer grants a resource to either role', () => {
    const terms = workloadTerms('core', 2, 1, 1);
    expect(evaluateConstraints(S2, terms).feasible).toBe(true);
    expect(evaluateAuthority(S2, 'opponent', terms, 'propose').feasible).toBe(false);
    expect(evaluateAuthority(S2, 'opponent', terms, 'accept').feasible).toBe(true);
    const teamLead = structuredClone(S2); teamLead.participants[1].roleId = 'team-lead'; teamLead.participants[1].authority.resources[0]!.proposalRequiresAuthorization = false;
    expect(evaluateAuthority(teamLead, 'opponent', terms, 'propose').feasible).toBe(true);
    const given = play(S2, [offer(workloadTerms('core', 2, 1, 0))]);
    expect(given.resourceAuthorizations).toEqual(['helper-authorization']);
    expect(evaluateAuthority(S2, 'opponent', terms, 'propose', given.resourceAuthorizations).feasible).toBe(true);
  });
  it('new opponent commitment reveals resources, but S1 prepayment never auto-reveals cashflow motivation', () => {
    const s1 = play(S1, [offer(supplyTerms(90, 'all7', 0))]);
    expect(s1.activeOffer?.terms.some(term => term.issueId === 'PREPAY' && term.valueId === '50')).toBe(true);
    expect(s1.knownFactIds).not.toContain('cashflow-need');
    const s2 = play(S2, [offer(workloadTerms('full', 2, 0, 0))]);
    expect(s2.knownFactIds).toContain('report-deferrable');
    expect(s2.knownFactIds).not.toContain('helper-available');
    expect(s2.progressCredits).toBe(0);
  });
  it('counteroffer selection cannot consult the player BATNA or private utility', () => {
    const altered = structuredClone(S1); altered.participants[0].batna.utility = 199; altered.participants[0].utility.base = -9000;
    const proposed = supplyTerms(90, 'all7', 0);
    expect(selectCounteroffer(S1, initial(S1), proposed)).toEqual(selectCounteroffer(altered, initial(altered), proposed));
  });
});
