import type { CanonicalAction, NegotiationState, Package, ScenarioDefinition } from '@arena/contracts';
import { matchesPredicate } from './enumerate.ts';
import { POLICY } from './policy.ts';

export function questionDisclosures(scenario: ScenarioDefinition, state: NegotiationState, action: CanonicalAction): string[] {
  if (action.kind !== 'question') return [];
  return scenario.facts.filter(fact => !state.knownFactIds.includes(fact.id) && fact.disclosure.some(rule => rule.kind === 'question' && rule.topicId === action.primaryTopicId && (rule.gate === 'always' || state.trust >= POLICY[scenario.policy.difficulty].disclosureThreshold))).map(fact => fact.id);
}
export function commitmentDisclosures(scenario: ScenarioDefinition, state: NegotiationState, terms: Package): string[] {
  return scenario.facts.filter(fact => !state.knownFactIds.includes(fact.id) && fact.disclosure.some(rule => rule.kind === 'opponent_commitment_contains' && matchesPredicate(terms, rule.condition))).map(fact => fact.id);
}
