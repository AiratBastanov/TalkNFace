import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { NegotiationStateSchema, PublicProjectionSchema } from '@arena/contracts';
import { projectPlayer, projectPrivateState, projectValidationForPlayer, validateScenario } from '../src/index.ts';
import { S1, S2, question } from '../../scenarios/src/index.ts';
import { GOLDENS } from '../../scenarios/test/goldens.ts';
import { initial, play } from '../../scenarios/test/helpers.ts';

describe('explicit public/private projection boundary', () => {
  it.each([S1, S2])('$templateId initial serialization excludes hidden facts, bindings, utility, reservation and witnesses', scenario => {
    const state = initial(scenario);
    const projection = projectPlayer(scenario, state);
    const encoded = JSON.stringify(projection);
    for (const fact of scenario.facts.filter(fact => fact.visibility === 'hidden')) { expect(encoded).not.toContain(fact.id); expect(encoded).not.toContain(fact.text); }
    for (const binding of scenario.arguments) expect(encoded).not.toContain(binding.id);
    for (const witness of scenario.validation.witnessTraces) expect(encoded).not.toContain(witness.id);
    for (const interest of scenario.participants[1].interests) { expect(encoded).not.toContain(interest.id); expect(encoded).not.toContain(interest.text); }
    for (const key of ['"trust":', '"tension":', '"progressCredits":', '"earnedEventKeys":', '"groundedArgumentIds":', '"unary":', '"pairs":', '"opponentUtility":', '"opponentBatna":', '"events":', '"configHash":', '"engineVersion":']) expect(encoded).not.toContain(key);
    expect(projection.scenario.player.batna).toEqual(scenario.participants[0].batna);
    expect(Object.keys(projection.scenario.opponent)).toEqual(['label', 'roleId', 'initialPosition']);
  });
  it('private sentinel numbers and prose never serialize, even with unknown keys attached at runtime', () => {
    const scenario = structuredClone(S1);
    scenario.participants[1].reservation = 193;
    scenario.participants[1].batna = { utility: 193, description: 'HIDDEN_BATNA_SENTINEL' };
    scenario.participants[1].privateBrief = 'HIDDEN_BRIEF_SENTINEL';
    scenario.participants[1].utility.base = 197;
    const state = initial(scenario);
    Object.assign(state, { injectedHidden: 'HIDDEN_STATE_SENTINEL' });
    const encoded = JSON.stringify(projectPlayer(scenario, state));
    for (const secret of ['193', '197', 'HIDDEN_BATNA_SENTINEL', 'HIDDEN_BRIEF_SENTINEL', 'HIDDEN_STATE_SENTINEL']) expect(encoded).not.toContain(secret);
  });
  it('revealing logistics permits only that fact and its now-grounded argument', () => {
    const projection = projectPlayer(S1, play(S1, [question('logistics')]));
    expect(projection.knownFacts.some(fact => fact.id === 'logistics-saving')).toBe(true);
    expect(projection.availableArguments.map(binding => binding.id)).toEqual(['logistics-argument']);
    expect(JSON.stringify(projection)).not.toContain('cashflow-need');
    expect(JSON.stringify(projection)).not.toContain('supplier-cashflow');
  });
  it.each(GOLDENS)('$id terminal DTO still excludes opponent metrics and internal events', fixture => {
    const projection = projectPlayer(fixture.scenario, play(fixture.scenario, fixture.actions));
    expect(PublicProjectionSchema.safeParse(projection).success).toBe(true);
    expect(JSON.stringify(projection)).not.toContain('opponentUtility');
    expect(JSON.stringify(projection)).not.toContain('opponentBatna');
    expect(JSON.stringify(projection)).not.toContain('earnedEventKeys');
  });
  it('both projections create independent nested objects; private export is explicitly runtime-validated', () => {
    const state = play(S1, [question('logistics')]);
    const publicCopy = projectPlayer(S1, state); const privateCopy = projectPrivateState(state);
    publicCopy.scenario.issues[0]!.values[0]!.label = 'changed';
    privateCopy.knownFactIds.push('not-real'); privateCopy.events[0]!.id = 'changed';
    expect(S1.issues[0]!.values[0]!.label).toBe('90');
    expect(state.knownFactIds).not.toContain('not-real'); expect(state.events[0]?.id).not.toBe('changed');
    expect(NegotiationStateSchema.safeParse(projectPrivateState(state)).success).toBe(true);
  });
  it('player validation failure exposes no private diagnostic', () => {
    const scenario = structuredClone(S1); scenario.arguments[0]!.factIds = ['PRIVATE_UNRESOLVED_REF'];
    const result = projectValidationForPlayer(validateScenario(scenario));
    expect(result).toEqual({ available: false, reasonCode: 'SCENARIO_UNAVAILABLE' });
    expect(JSON.stringify(result)).not.toContain('PRIVATE_UNRESOLVED_REF');
  });
  it('production generic code has no reference IDs, RNG, clock, database or external-service dependency', () => {
    const root = fileURLToPath(new URL('../src/', import.meta.url));
    const source = readdirSync(root).filter(name => name.endsWith('.ts')).map(name => readFileSync(root + name, 'utf8')).join('\n');
    expect(source).not.toMatch(/S1-SUPPLY|S2-WORKLOAD|scenarioId|switch\s*\(\s*templateId|Math\.random|Date\.now|node:fs|node:http|better-sqlite3|\bfetch\s*\(|\beval\s*\(/);
    const web = readFileSync(new URL('../../../apps/web/src/main.tsx', import.meta.url), 'utf8');
    expect(web).not.toMatch(/@arena\/(domain|scenarios)|privateBrief|reservation/);
  });
});
