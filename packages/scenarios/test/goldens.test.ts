import { describe, expect, it } from 'vitest';
import { NegotiationStateSchema, PublicProjectionSchema } from '@arena/contracts';
import { argumentDiscount, aspiration, projectPlayer, transition } from '@arena/domain';
import { S1, S2, argument, offer, question, supplyTerms, workloadTerms } from '../src/index.ts';
import { GOLDENS } from './goldens.ts';
import { deepFreeze, initial, play, step } from './helpers.ts';

describe('Frozen deterministic golden traces', () => {
  it.each(GOLDENS)('$id matches all planned consequences', fixture => {
    const scenario = deepFreeze(structuredClone(fixture.scenario));
    const start = deepFreeze(initial(scenario));
    const actions = deepFreeze(structuredClone(fixture.actions));
    const state = play(scenario, actions, start);
    const expected = fixture.expected;
    expect(state.phase).toBe(expected.phase);
    expect(state.terminalReason).toBe(expected.phase);
    expect(state.turnNumber).toBe(expected.turns);
    expect(state.revision).toBe(expected.turns);
    expect(state.outcome?.family).toBe(expected.family);
    expect(state.agreementOffer?.terms ?? null).toEqual(expected.terms);
    expect(state.outcome?.playerUtility === null ? null : [state.outcome?.playerUtility, state.outcome?.opponentUtility]).toEqual(expected.utilities);
    if (expected.trust !== undefined) expect(state.trust).toBe(expected.trust);
    if (expected.credits !== undefined) expect(state.progressCredits).toBe(expected.credits);
    if (expected.terms && expected.discount !== undefined) expect(argumentDiscount(scenario, state, expected.terms)).toBe(expected.discount);
    if (expected.terms && expected.aspiration !== undefined) expect(aspiration(scenario, state, expected.terms)).toBe(expected.aspiration);
    for (const type of expected.events) expect(state.events.some(event => event.payload.type === type)).toBe(true);
    expect(NegotiationStateSchema.safeParse(state).success).toBe(true);
    expect(PublicProjectionSchema.safeParse(projectPlayer(scenario, state)).success).toBe(true);
    expect(JSON.stringify(play(scenario, actions, initial(scenario)))).toBe(JSON.stringify(state));
    expect(start.turnNumber).toBe(0);
  });
  it('all four outcome families exist in each reference', () => {
    for (const scenario of [S1, S2]) expect(new Set(GOLDENS.filter(trace => trace.scenario === scenario).map(trace => play(scenario, trace.actions).outcome?.family)).size).toBe(4);
  });
  it('GS3 warning occurs at tension 80 on the third threat; next threat walks away', () => {
    const fixture = GOLDENS.find(trace => trace.id === 'GS3');
    if (!fixture) throw new Error('Missing fixture');
    const warned = play(S1, fixture.actions.slice(0, 4));
    expect(warned).toMatchObject({ tension: 80, warning: true, terminalReason: null });
    const final = step(S1, warned, fixture.actions[4]!);
    expect(final.terminalReason).toBe('opponent_walkaway');
  });
  it('GT5 resource disclosure from an issued counteroffer cannot be farmed as discovery', () => {
    const first = play(S2, [offer(workloadTerms('core', 2, 1, 0))]);
    expect(first.activeOffer?.terms).toEqual(workloadTerms('core', 2, 1, 1));
    expect(first.knownFactIds).toEqual(expect.arrayContaining(['helper-available', 'report-deferrable']));
    expect(first.progressCredits).toBe(1);
    const queried = step(S2, first, question('resources'));
    expect(queried.trust).toBe(54);
    expect(queried.progressCredits).toBe(1);
  });
  it('W1 canonical tone causes the planned causal divergence, without NLU', () => {
    const open = play(S1, [question('logistics', 'respectful_firm')]);
    const accusation = play(S1, [question('logistics', 'accusatory')]);
    expect(open).toMatchObject({ trust: 54, tension: 20, progressCredits: 1 });
    expect(open.knownFactIds).toContain('logistics-saving');
    expect(accusation).toMatchObject({ trust: 42, tension: 30, progressCredits: 0 });
    expect(accusation.knownFactIds).not.toContain('logistics-saving');
  });
  it('A1 equal offer terms: a grounded logistics argument changes rejection into acceptance', () => {
    const prefix = S1.validation.witnessTraces[0]!.actions.slice(0, 3);
    const terms = supplyTerms(90, 'split40at7_rest14', 50);
    const without = play(S1, [...prefix, offer(terms)]);
    const withArgument = play(S1, [...prefix, argument('logistics-argument'), offer(terms)]);
    expect(without).toMatchObject({ trust: 64, progressCredits: 4, terminalReason: null });
    expect(aspiration(S1, without, terms)).toBe(26);
    expect(without.events.some(event => event.payload.type === 'offer_rejected_aspiration')).toBe(true);
    expect(withArgument).toMatchObject({ trust: 68, progressCredits: 5, terminalReason: 'agreed' });
    expect(aspiration(S1, withArgument, terms)).toBe(22);
    expect(without.lastUserOffer?.terms).toEqual(withArgument.lastUserOffer?.terms);
  });
  it('rejected/stale revisions preserve the entire state and cannot consume a turn', () => {
    const state = play(S1, [question('logistics')]);
    const result = transition(S1, deepFreeze(state), { expectedRevision: 0, requestId: 'stale', action: question('payment') });
    expect(result.ok).toBe(false);
    expect(result.state).toBe(state);
    if (!result.ok) expect(result.errors[0]?.code).toBe('STALE_REVISION');
  });
});
