import type { NegotiationState, Package, ScenarioDefinition } from '@arena/contracts';
import { evaluateAuthority } from './authority.ts';
import { evaluateConstraints } from './constraints.ts';
import { enumeratePackages, packageDistance } from './enumerate.ts';
import type { CatalogEntry } from './enumerate.ts';
import { aspiration } from './policy.ts';
import { evaluateUtility } from './utility.ts';

export type CounterofferCandidate = CatalogEntry & { distance: number; opponentUtility: number; aspiration: number };
export function selectCounteroffer(scenario: ScenarioDefinition, state: NegotiationState, proposed: Package): CounterofferCandidate | null {
  const candidates: CounterofferCandidate[] = [];
  for (const entry of enumeratePackages(scenario)) {
    if (!evaluateConstraints(scenario, entry.terms).feasible || !evaluateAuthority(scenario, 'opponent', entry.terms, 'propose', state.resourceAuthorizations).feasible) continue;
    const utility = evaluateUtility(scenario, 'opponent', entry.terms);
    const threshold = aspiration(scenario, state, entry.terms);
    if (utility >= threshold) candidates.push({ ...entry, distance: packageDistance(scenario, proposed, entry.terms), opponentUtility: utility, aspiration: threshold });
  }
  candidates.sort((a, b) => a.distance - b.distance || b.opponentUtility - a.opponentUtility || a.index - b.index);
  return candidates[0] ?? null;
}
