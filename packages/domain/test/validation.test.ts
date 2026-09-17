import { describe, expect, it } from 'vitest';
import type { ScenarioDefinition } from '@arena/contracts';
import { evaluateConstraints, normalizePackage, projectValidationForPlayer, validateScenario } from '../src/index.ts';
import { S1, S2, argument, question, supplyTerms } from '../../scenarios/src/index.ts';

describe('strict schema and separate semantic validation', () => {
  const malformed: [string, unknown][] = [
    ['unknown root key', { ...S1, execute: 'arbitrary expression' }],
    ['unknown policy key', { ...S1, policy: { ...S1.policy, trustBonus: 100 } }],
    ['function', { ...S1, title: () => 'not data' }],
    ['Date', { ...S1, title: new Date(0) }],
    ['Map', { ...S1, topics: new Map() }],
    ['Set', { ...S1, facts: new Set() }],
    ['one participant', { ...S1, participants: [S1.participants[0]] }],
    ['one issue', { ...S1, issues: [S1.issues[0]] }],
    ['five issues', { ...S1, issues: [...S1.issues, ...S1.issues] }],
    ['NaN', { ...S1, participants: [{ ...S1.participants[0], target: NaN }, S1.participants[1]] }],
    ['Infinity', { ...S1, participants: [{ ...S1.participants[0], target: Infinity }, S1.participants[1]] }],
    ['fraction', { ...S1, participants: [{ ...S1.participants[0], target: 62.5 }, S1.participants[1]] }],
    ['unsafe integer', { ...S1, participants: [{ ...S1.participants[0], utility: { ...S1.participants[0].utility, base: Number.MAX_SAFE_INTEGER + 1 } }, S1.participants[1]] }],
    ['BigInt', { ...S1, participants: [{ ...S1.participants[0], target: 62n }, S1.participants[1]] }],
    ['arbitrary constraint', { ...S1, constraints: [{ kind: 'javascript', expression: 'return true;' }] }],
    ['wrong maxTurns', { ...S1, policy: { ...S1.policy, maxTurns: 9 } }],
  ];
  it.each(malformed)('rejects %s at the runtime boundary', (_name, input) => {
    const result = validateScenario(input);
    expect(result.valid).toBe(false); expect(result.coverage).toBeNull();
    expect(result.errors.every(error => error.code === 'SCHEMA_INVALID')).toBe(true);
    expect(projectValidationForPlayer(result)).toEqual({ available: false, reasonCode: 'SCENARIO_UNAVAILABLE' });
  });
  const invalid: [string, (scenario: ScenarioDefinition) => void, string][] = [
    ['duplicate issue', s => { s.issues[1]!.id = s.issues[0]!.id; }, 'DUPLICATE_ID'],
    ['duplicate value', s => { s.issues[0]!.values[1]!.id = s.issues[0]!.values[0]!.id; }, 'DUPLICATE_ID'],
    ['duplicate participant', s => { s.participants[1].id = s.participants[0].id; }, 'DUPLICATE_ID'],
    ['wrong party order', s => { s.participants[1].party = 'player'; }, 'PARTICIPANT_ROLES'],
    ['missing utility table', s => { s.participants[0].utility.unary.pop(); }, 'MISSING_UTILITY_TABLE'],
    ['missing utility cell', s => { s.participants[0].utility.unary[0]!.cells.pop(); }, 'MISSING_CELL'],
    ['undefined utility value', s => { s.participants[0].utility.unary[0]!.cells[0]!.valueId = 'not-defined'; }, 'UNKNOWN_REFERENCE'],
    ['unknown issue reference', s => { s.participants[0].goals[0]!.issueIds = ['absent']; }, 'UNKNOWN_REFERENCE'],
    ['mismatched BATNA', s => { s.participants[1].batna.utility = 21; }, 'BATNA_RESERVATION_MISMATCH'],
    ['target below reservation', s => { s.participants[0].target = 54; }, 'TARGET_BELOW_RESERVATION'],
    ['target impossible', s => { s.participants[0].target = 200; }, 'UNREACHABLE_TARGET'],
    ['utility out of range', s => { s.participants[0].utility.base = 9000; }, 'UTILITY_RANGE'],
    ['utility spread too narrow', s => { for (const table of s.participants[0].utility.unary) for (const cell of table.cells) cell.utility = 0; }, 'UTILITY_SPREAD'],
    ['unknown authority value', s => { s.participants[1].authority.allowedValues[0]!.valueIds = ['97']; }, 'UNKNOWN_REFERENCE'],
    ['unknown fact owner', s => { s.facts[1]!.ownerId = 'absent'; }, 'UNKNOWN_REFERENCE'],
    ['unknown argument fact', s => { s.arguments[0]!.factIds = ['absent']; }, 'UNKNOWN_REFERENCE'],
    ['ungrounded interest argument', s => { s.arguments[0]!.factIds = ['cashflow-need']; }, 'UNGROUNDED_INTEREST'],
    ['argument unrelated to its interest', s => { s.arguments[0]!.condition = [{ kind: 'eq', issueId: 'PREPAY', valueId: '50' }]; }, 'ARGUMENT_BINDING_MISMATCH'],
    ['commitment cannot disclose motivation', s => { s.facts[1]!.disclosure.push({ kind: 'opponent_commitment_contains', condition: [{ kind: 'eq', issueId: 'DELIVERY', valueId: 'split40at7_rest14' }] }); }, 'COMMITMENT_DISCLOSURE_NOT_RESOURCE'],
    ['unrelated explanation trigger', s => { s.facts[1]!.disclosure.push({ kind: 'constraint_explanation', constraintId: 'launch' }); }, 'EXPLANATION_BINDING_MISMATCH'],
    ['undisclosable hidden fact', s => { s.facts[1]!.disclosure = []; }, 'UNDISCLOSABLE_FACT'],
    ['trust-locked authority explanation', s => { s.facts[3]!.disclosure = [{ kind: 'question', topicId: 'authority', gate: 'trust' }]; }, 'LOCKED_EXPLANATION'],
    ['hidden explanation without trigger', s => { s.facts[3]!.disclosure = [{ kind: 'question', topicId: 'authority', gate: 'always' }]; }, 'UNEXPLAINABLE_CONSTRAINT'],
    ['unknown witness topic', s => { s.validation.witnessTraces[0]!.actions[0] = question('missing-topic'); }, 'UNKNOWN_TOPIC'],
    ['witness uses future evidence', s => { s.validation.witnessTraces[0]!.actions[0] = argument('logistics-argument'); }, 'UNAVAILABLE_ARGUMENT'],
    ['duplicate witness actions', s => { s.validation.witnessTraces[1]!.actions = structuredClone(s.validation.witnessTraces[0]!.actions); }, 'DUPLICATE_ID'],
    ['conflicting constraints', s => { s.constraints.push({ kind: 'allowed_values', id: 'only-late', issueId: 'DELIVERY', valueIds: ['all14'], reasonCode: 'ONLY_LATE', explanationFactId: 'launch-bound' }); }, 'NO_FEASIBLE_PACKAGE'],
    ['empty rational agreement set', s => { s.participants[1].reservation = 100; s.participants[1].batna.utility = 100; s.participants[1].target = 100; }, 'INSUFFICIENT_RATIONAL_PACKAGES'],
  ];
  it.each(invalid)('semantic error: %s', (_name, change, code) => {
    const scenario = structuredClone(S1); change(scenario);
    const first = validateScenario(scenario); const second = validateScenario(scenario);
    expect(first.valid).toBe(false); expect(first.errors.some(error => error.code === code)).toBe(true);
    expect(first).toEqual(second);
    expect(first.errors.every(error => error.path.startsWith('/') && error.message.length > 0)).toBe(true);
  });
  it('pair interactions require complete and unique Cartesian coverage', () => {
    const scenario = structuredClone(S2);
    const table = scenario.participants[1].utility.pairs[0]!;
    table.cells[3] = structuredClone(table.cells[0]!);
    const result = validateScenario(scenario);
    expect(result.errors.some(error => error.code === 'MISSING_PAIR_CELL')).toBe(true);
    expect(result.errors.some(error => error.code === 'DUPLICATE_ID')).toBe(true);
  });
  it('linear constraints also require complete contribution lookups', () => {
    const scenario = structuredClone(S2);
    const rule = scenario.constraints[0]!;
    if (rule.kind !== 'linear_lte') throw new Error('Expected capacity');
    rule.contributions[0]!.cells[1]!.valueId = 'core';
    expect(validateScenario(scenario).errors.some(error => error.code === 'MISSING_CELL')).toBe(true);
  });
  it('all three constraint types work from data; generic forbid_combination has precise reason IDs', () => {
    const scenario = structuredClone(S1);
    scenario.constraints.push({ id: 'no-rush-without-prepay', kind: 'forbid_combination', terms: [{ issueId: 'DELIVERY', valueId: 'all7' }, { issueId: 'PREPAY', valueId: '0' }], reasonCode: 'RUSH_REQUIRES_PREPAY', explanationFactId: 'launch-bound' });
    const impossible = evaluateConstraints(scenario, supplyTerms(115, 'all7', 0));
    expect(impossible).toEqual({ feasible: false, violations: [{ ruleId: 'no-rush-without-prepay', reasonCode: 'RUSH_REQUIRES_PREPAY', explanationFactId: 'launch-bound' }] });
    expect(evaluateConstraints(scenario, supplyTerms(115, 'all7', 30)).feasible).toBe(true);
    expect(evaluateConstraints(scenario, supplyTerms(115, 'all14', 30)).violations[0]?.ruleId).toBe('launch');
  });
  it('out-of-domain, duplicate or partial packages fail normalization without rounding', () => {
    expect(normalizePackage(S1, supplyTerms(97, 'all7', 30)).ok).toBe(false);
    expect(normalizePackage(S1, supplyTerms(95, 'all7', 30).slice(0, 2)).ok).toBe(false);
    expect(normalizePackage(S1, [...supplyTerms(95, 'all7', 30), { issueId: 'unknown', valueId: 'x' }]).ok).toBe(false);
  });
});
