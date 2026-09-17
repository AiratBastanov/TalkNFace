import type { Package, Party, ScenarioDefinition } from '@arena/contracts';
import type { Feasibility } from './constraints.ts';
import { matchesPredicate, valueOf } from './enumerate.ts';
import { participant } from './utility.ts';

export function evaluateAuthority(scenario: ScenarioDefinition, party: Party, terms: Package, purpose: 'accept' | 'propose', authorizations: readonly string[] = []): Feasibility {
  const authority = participant(scenario, party).authority;
  const violations = authority.allowedValues.filter(rule => !rule.valueIds.includes(valueOf(terms, rule.issueId)))
    .map(rule => ({ ruleId: rule.id, reasonCode: rule.reasonCode, explanationFactId: rule.explanationFactId }));
  for (const rule of authority.resources) if (purpose === 'propose' && rule.proposalRequiresAuthorization && matchesPredicate(terms, rule.requiredWhen) && !authorizations.includes(rule.id)) {
    violations.push({ ruleId: rule.id, reasonCode: rule.reasonCode, explanationFactId: rule.explanationFactId });
  }
  return { feasible: violations.length === 0, violations };
}
export function grantedResources(scenario: ScenarioDefinition, terms: Package): string[] {
  return participant(scenario, 'opponent').authority.resources.filter(rule => matchesPredicate(terms, rule.grantWhen)).map(rule => rule.id);
}
