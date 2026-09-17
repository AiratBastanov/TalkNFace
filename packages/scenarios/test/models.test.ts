import { describe, expect, it } from 'vitest';
import type { ScenarioDefinition } from '@arena/contracts';
import { auditModel, enumeratePackages, evaluateAuthority, evaluateConstraints, evaluateUtility, normalizePackage, packageKey, validateScenario } from '@arena/domain';
import { S1, S2, supplyTerms, workloadTerms } from '../src/index.ts';

describe('reference arithmetic and full enumeration', () => {
  it.each([S1, S2])('$templateId strict schema, semantics and executable witnesses', scenario => {
    const validation = validateScenario(scenario);
    expect(validation.errors).toEqual([]);
    expect(validation.valid).toBe(true);
    expect(validation.coverage?.individuallyRational).toBeGreaterThanOrEqual(2);
    expect(validation.coverage?.playerTargetReaching).toBeGreaterThan(0);
    expect(validation.coverage?.poorAgreements).toBeGreaterThan(0);
  });
  it.each([
    [95, 'split40at7_rest14', 50, 64, 27], [100, 'split40at7_rest14', 30, 62, 20], [105, 'all7', 50, 59, 21], [110, 'all7', 50, 54, 26], [90, 'all7', 0, 80, -14],
  ] as const)('S1 %i/%s/%i gives %i/%i', (price, delivery, prepay, buyer, supplier) => {
    const terms = supplyTerms(price, delivery, prepay);
    expect(evaluateUtility(S1, 'player', terms)).toBe(buyer);
    expect(evaluateUtility(S1, 'opponent', terms)).toBe(supplier);
  });
  it.each([
    ['full', 2, 1, 1, 47, 30, true], ['core', 2, 1, 0, 32, 36, true], ['full', 5, 0, 1, 35, 28, true], ['full', 2, 0, 0, 65, 8, false], ['core', 5, 0, 0, 20, 34, true],
  ] as const)('S2 %s/%i/%i/%i gives %i/%i; feasible=%s', (scope, days, help, defer, manager, employee, feasible) => {
    const terms = workloadTerms(scope, days, help, defer);
    expect(evaluateUtility(S2, 'player', terms)).toBe(manager);
    expect(evaluateUtility(S2, 'opponent', terms)).toBe(employee);
    expect(evaluateConstraints(S2, terms).feasible).toBe(feasible);
  });
  it('S1 has exactly 54 raw packages and the three documented rational Pareto packages', () => {
    const audit = auditModel(S1);
    expect(audit.raw).toBe(54);
    expect(audit.physicallyFeasible).toBe(36);
    expect(audit.pareto.map(row => [row.terms, row.playerUtility, row.opponentUtility])).toEqual([
      [supplyTerms(90, 'split40at7_rest14', 50), 69, 22], [supplyTerms(95, 'split40at7_rest14', 50), 64, 27], [supplyTerms(100, 'split40at7_rest14', 50), 59, 32],
    ]);
    expect(audit.packages[0]?.terms).toEqual(supplyTerms(90, 'all7', 0));
    expect(audit.packages[53]?.terms).toEqual(supplyTerms(115, 'all14', 50));
  });
  it('S2 has exactly 16 raw packages, 11 feasible and 6 mutually rational', () => {
    expect(auditModel(S2)).toMatchObject({ raw: 16, physicallyFeasible: 11, individuallyRational: 6, playerTargetReaching: 1, poorAgreements: 5 });
  });
  it.each([S1, S2])('independent arithmetic oracle over every $templateId package', scenario => {
    for (const row of enumeratePackages(scenario)) {
      const values = row.terms.map(term => term.valueId);
      let expectedPlayer: number; let expectedOpponent: number; let expectedFeasible: boolean;
      if (scenario === S1) {
        const [price, delivery, prepay] = values;
        expectedPlayer = 170 - Number(price) - (delivery === 'all7' ? 0 : delivery === 'all14' ? 20 : 5) - (prepay === '0' ? 0 : prepay === '30' ? 3 : 6);
        expectedOpponent = Number(price) - 80 - (delivery === 'all7' ? 24 : delivery === 'all14' ? 0 : 8) + (prepay === '0' ? 0 : prepay === '30' ? 8 : 20);
        expectedFeasible = delivery !== 'all14';
      } else {
        const [scope, days, help, defer] = values;
        const work = scope === 'core' ? 8 : 16;
        expectedPlayer = (scope === 'core' ? 20 : 45) + (days === '2' ? 20 : 0) - 8 * Number(help) - 10 * Number(defer);
        expectedOpponent = 50 - 2 * Math.max(work - 6 * Number(help), 0) + 10 * Number(defer) - (days === '2' ? 10 : 0);
        expectedFeasible = work <= 2 * Number(days) + 6 * Number(help) + 6 * Number(defer);
      }
      expect(evaluateUtility(scenario, 'player', row.terms)).toBe(expectedPlayer);
      expect(evaluateUtility(scenario, 'opponent', row.terms)).toBe(expectedOpponent);
      expect(Number.isSafeInteger(expectedPlayer) && Number.isSafeInteger(expectedOpponent)).toBe(true);
      expect(evaluateConstraints(scenario, row.terms).feasible).toBe(expectedFeasible);
      expect(evaluateConstraints(scenario, row.terms)).toEqual(evaluateConstraints(scenario, row.terms));
      expect(evaluateAuthority(scenario, 'opponent', row.terms, 'accept')).toEqual(evaluateAuthority(scenario, 'opponent', row.terms, 'accept'));
    }
  });
  it('catalog indices are contiguous; normalization ignores term/object insertion order', () => {
    const catalog = enumeratePackages(S1);
    expect(catalog.map(entry => entry.index)).toEqual(Array.from({ length: 54 }, (_, i) => i));
    const terms = supplyTerms(95, 'split40at7_rest14', 50);
    const reversed = [...terms].reverse().map(term => ({ valueId: term.valueId, issueId: term.issueId }));
    expect(normalizePackage(S1, reversed)).toEqual({ ok: true, terms });
    expect(packageKey(S1, reversed)).toBe(packageKey(S1, terms));
  });
  it('the generic enumerator reaches the 1296-package maximum in canonical order', () => {
    const scenario: ScenarioDefinition = structuredClone(S1);
    scenario.issues = Array.from({ length: 4 }, (_, i) => ({ id: `issue${i}`, label: 'Issue', unit: 'units', ordered: true, values: Array.from({ length: 6 }, (_, j) => ({ id: `v${j}`, label: String(j), quantity: j })) }));
    const catalog = enumeratePackages(scenario);
    expect(catalog).toHaveLength(1296);
    expect(new Set(catalog.map(row => row.key)).size).toBe(1296);
    expect(catalog[1295]?.terms.map(term => term.valueId)).toEqual(['v5', 'v5', 'v5', 'v5']);
  });
});
