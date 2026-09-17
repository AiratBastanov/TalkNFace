import { describe, expect, it } from 'vitest';
import type { CanonicalAction } from '@arena/contracts';
import { aspiration, enumeratePackages, evaluateAuthority, evaluateConstraints, evaluateUtility, packageDistance, selectCounteroffer, transition } from '../src/index.ts';
import { S1, S2, accept, acknowledge, clarification, offer, pressure, question, supplyTerms, walkAway, workloadTerms } from '../../scenarios/src/index.ts';
import { initial, play, step } from '../../scenarios/test/helpers.ts';

describe('offer lifecycle and terminal precedence', () => {
  it('an active opponent offer survives unrelated questions, with its exact ID and terms', () => {
    const first = play(S1, [offer(supplyTerms(90, 'all7', 0))]);
    const queried = play(S1, [question('logistics'), question('payment')], first);
    expect(queried.activeOffer).toEqual(first.activeOffer);
    if (!queried.activeOffer) throw new Error('Expected active offer');
    const agreed = step(S1, queried, accept(queried.activeOffer.id));
    expect(agreed.agreementOffer).toEqual(first.activeOffer);
    expect(agreed.activeOffer).toBeNull();
  });
  it('an already-issued commitment survives an actual aspiration increase and is accepted on turn 8', () => {
    const scenario = structuredClone(S1); scenario.policy.tone = 'friendly';
    const issued = play(scenario, [question('logistics'), question('payment'), acknowledge('logistics-saving'), acknowledge('cashflow-need'), acknowledge('launch-bound'), offer(supplyTerms(90, 'split40at7_rest14', 30))]);
    const commitment = issued.activeOffer;
    if (!commitment) throw new Error('Expected opponent commitment');
    expect(commitment.terms).toEqual(supplyTerms(90, 'split40at7_rest14', 50));
    expect(issued.turnNumber).toBe(6);
    const utility = evaluateUtility(scenario, 'opponent', commitment.terms);
    expect(aspiration(scenario, issued, commitment.terms)).toBe(utility);
    const worsened = step(scenario, issued, pressure());
    expect(aspiration(scenario, worsened, commitment.terms)).toBeGreaterThan(utility);
    expect(worsened.activeOffer).toEqual(commitment);
    const accepted = step(scenario, worsened, accept(commitment.id));
    expect(accepted).toMatchObject({ turnNumber: 8, terminalReason: 'agreed' });
    expect(accepted.agreementOffer).toEqual(commitment);
    expect(accepted.events.some(event => event.payload.type === 'round_limit')).toBe(false);
  });
  it('replacement closes the former offer; a stale ID or arbitrary ID consumes no turn', () => {
    const first = play(S1, [offer(supplyTerms(90, 'all7', 0))]);
    if (!first.activeOffer) throw new Error('Expected offer');
    const second = step(S1, first, offer(supplyTerms(95, 'all7', 0)));
    expect(second.activeOffer?.id).not.toBe(first.activeOffer.id);
    expect(second.activeOffer?.supersedesId).toBe(first.activeOffer.id);
    for (const id of [first.activeOffer.id, 'nonexistent']) {
      const result = transition(S1, second, { expectedRevision: second.revision, requestId: 'stale', action: accept(id) });
      expect(result.ok).toBe(false); expect(result.state).toBe(second);
      if (!result.ok) expect(result.errors[0]?.code).toBe('STALE_OFFER');
    }
    expect(second.events.some(event => event.payload.type === 'offer_closed' && event.payload.reason === 'replaced')).toBe(true);
  });
  it('player counteroffer must reference the exact active offer', () => {
    const state = play(S1, [offer(supplyTerms(90, 'all7', 0))]);
    if (!state.activeOffer) throw new Error('Expected offer');
    const counter: CanonicalAction = { ...offer(supplyTerms(95, 'all7', 0)), kind: 'counter_offer', targetOfferId: state.activeOffer.id };
    expect(step(S1, state, counter).turnNumber).toBe(2);
    counter.targetOfferId = 'wrong';
    expect(transition(S1, state, { expectedRevision: 1, requestId: 'bad-counter', action: counter }).ok).toBe(false);
  });
  it('last-turn explicit player and opponent walkaways take precedence over round_limit', () => {
    const player = play(S1, [...Array.from({ length: 7 }, () => clarification()), walkAway()]);
    expect(player).toMatchObject({ terminalReason: 'player_walkaway', turnNumber: 8 });
    const opponent = play(S1, [pressure(), pressure(), pressure(), ...Array.from({ length: 4 }, () => clarification()), pressure()]);
    expect(opponent).toMatchObject({ terminalReason: 'opponent_walkaway', turnNumber: 8 });
    for (const state of [player, opponent]) expect(state.events.some(event => event.payload.type === 'round_limit')).toBe(false);
  });
  it('terminal state rejects subsequent actions without mutation or extra evidence', () => {
    const state = play(S1, [walkAway()]);
    const result = transition(S1, state, { expectedRevision: 1, requestId: 'after-terminal', action: question('logistics') });
    expect(result.ok).toBe(false); expect(result.state).toBe(state);
    if (!result.ok) expect(result.errors[0]?.code).toBe('TERMINAL_SESSION');
  });
  it('invalid shape/domain/partial offers never consume a turn; impossible full offers do', () => {
    const state = initial(S1);
    const valid = offer(supplyTerms(95, 'all7', 0));
    const invalid: unknown[] = [
      { ...valid, unexpected: true }, { ...valid, terms: valid.terms.slice(1) },
      { ...valid, terms: supplyTerms(97, 'all7', 0) }, { ...valid, terms: [valid.terms[0], valid.terms[0], valid.terms[2]] },
      { ...valid, tone: 'magically_good' }, question('unknown-topic'), argumentUnknown(), accept('absent'),
    ];
    for (const action of invalid) {
      const result = transition(S1, state, { expectedRevision: 0, requestId: 'invalid', action });
      expect(result.ok).toBe(false); expect(result.state).toBe(state);
    }
    expect(step(S1, state, offer(supplyTerms(95, 'all14', 0)))).toMatchObject({ turnNumber: 1, outcome: null });
  });
  it('no acceptable counteroffer gives a deterministic reason and does not invent terms', () => {
    const scenario = structuredClone(S1);
    scenario.participants[1].authority.allowedValues.push({ id: 'delivery-authority', issueId: 'DELIVERY', valueIds: ['all7'], reasonCode: 'ONLY_ALL7', explanationFactId: 'launch-bound' });
    scenario.participants[1].authority.allowedValues.push({ id: 'prepay-authority', issueId: 'PREPAY', valueIds: ['0'], reasonCode: 'ONLY_ZERO', explanationFactId: 'launch-bound' });
    const state = play(scenario, [offer(supplyTerms(90, 'all7', 0))]);
    expect(state.activeOffer).toBeNull();
    expect(state.events.some(event => event.payload.type === 'counteroffer_unavailable' && event.payload.reasonCode === 'NO_ACCEPTABLE_CANDIDATE')).toBe(true);
  });
});

function argumentUnknown(): CanonicalAction { return { ...clarification(), kind: 'argument', argumentId: 'not-a-known-binding' }; }

describe('bounded counteroffer proof', () => {
  it.each([S1, S2])('every accepted $templateId package obeys physical, authority and reservation bounds', scenario => {
    for (const entry of enumeratePackages(scenario)) for (const trust of [0, 100]) {
      const start = initial(scenario); start.trust = trust; start.progressCredits = 5; start.groundedArgumentIds = scenario.arguments.map(binding => binding.id);
      const state = step(scenario, start, offer(entry.terms));
      if (state.terminalReason === 'agreed') {
        expect(evaluateConstraints(scenario, entry.terms).feasible).toBe(true);
        expect(evaluateAuthority(scenario, 'opponent', entry.terms, 'accept').feasible).toBe(true);
        expect(evaluateUtility(scenario, 'opponent', entry.terms)).toBeGreaterThanOrEqual(scenario.participants[1].reservation);
      }
    }
  });
  it('nominal distance is 0/1 while ordered distance counts domain positions', () => {
    expect(packageDistance(S1, supplyTerms(90, 'all7', 0), supplyTerms(115, 'all14', 50))).toBe(8);
    expect(packageDistance(S2, workloadTerms('core', 2, 0, 0), workloadTerms('full', 5, 1, 1))).toBe(4);
  });
  it('equal distance and utility resolve by canonical catalog index, including per-candidate discounts', () => {
    const state = initial(S2); state.progressCredits = 1; state.resourceAuthorizations = ['helper-authorization'];
    const candidate = selectCounteroffer(S2, state, workloadTerms('core', 2, 1, 0));
    expect(candidate).toMatchObject({ index: 3, distance: 1, opponentUtility: 46 });
    expect(candidate?.terms).toEqual(workloadTerms('core', 2, 1, 1));
  });
  it.each([S1, S2])('every $templateId package: candidate validity and lexicographic optimality over bounded policy states', scenario => {
    const catalog = enumeratePackages(scenario);
    for (const difficulty of ['beginner', 'normal', 'advanced'] as const) for (const trust of [0, 60, 100]) for (const credits of [0, 5]) {
      const configured = structuredClone(scenario); configured.policy.difficulty = difficulty;
      const state = initial(configured); state.trust = trust; state.progressCredits = credits;
      state.groundedArgumentIds = scenario.arguments.map(binding => binding.id);
      state.resourceAuthorizations = scenario.participants[1].authority.resources.map(resource => resource.id);
      const eligible = catalog.filter(entry => evaluateConstraints(configured, entry.terms).feasible && evaluateAuthority(configured, 'opponent', entry.terms, 'propose', state.resourceAuthorizations).feasible && evaluateUtility(configured, 'opponent', entry.terms) >= aspiration(configured, state, entry.terms));
      for (const proposed of catalog) {
        const selected = selectCounteroffer(configured, state, proposed.terms);
        expect(selectCounteroffer(configured, state, proposed.terms)).toEqual(selected);
        if (!eligible.length) { expect(selected).toBeNull(); continue; }
        if (!selected) throw new Error('Candidate missing');
        expect(eligible.some(entry => entry.index === selected.index)).toBe(true);
        for (const other of eligible) {
          const distance = packageDistance(configured, proposed.terms, other.terms);
          const utility = evaluateUtility(configured, 'opponent', other.terms);
          expect(distance).toBeGreaterThanOrEqual(selected.distance);
          if (distance === selected.distance) {
            expect(utility).toBeLessThanOrEqual(selected.opponentUtility);
            if (utility === selected.opponentUtility) expect(other.index).toBeGreaterThanOrEqual(selected.index);
          }
        }
      }
    }
  });
});
