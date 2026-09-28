import { CanonicalActionSchema } from '@arena/contracts';
import type { CanonicalAction, NegotiationState, Package, ScenarioDefinition } from '@arena/contracts';
import { evaluateAuthority, evaluateConstraints, evaluateUtility, matchesPredicate, normalizePackage, participant, validateActionContext } from '@arena/domain';

export function feasible(s: ScenarioDefinition, before: NegotiationState, terms: Package): boolean {
  return normalizePackage(s, terms).ok && evaluateConstraints(s, terms).feasible
    && evaluateAuthority(s, 'player', terms, 'propose', before.resourceAuthorizations).feasible
    && evaluateAuthority(s, 'opponent', terms, 'accept', before.resourceAuthorizations).feasible;
}
export function mutual(s: ScenarioDefinition, before: NegotiationState, terms: Package): boolean {
  return feasible(s, before, terms) && ['player', 'opponent'].every(party =>
    evaluateUtility(s, party as 'player' | 'opponent', terms) >= participant(s, party as 'player' | 'opponent').batna.utility);
}
export function pareto(s: ScenarioDefinition, previous: Package, terms: Package): boolean {
  const a = evaluateUtility(s, 'player', terms) - evaluateUtility(s, 'player', previous);
  const b = evaluateUtility(s, 'opponent', terms) - evaluateUtility(s, 'opponent', previous);
  return a >= 0 && b >= 0 && (a > 0 || b > 0);
}
export function usesFact(s: ScenarioDefinition, factId: string, terms: Package): boolean {
  if (s.arguments.some(a => a.factIds.includes(factId) && matchesPredicate(terms, a.condition))) return true;
  const constraints = s.constraints.filter(c => c.explanationFactId === factId);
  if (constraints.length && constraints.every(c => !evaluateConstraints(s, terms).violations.some(v => v.ruleId === c.id))) return true;
  return s.participants.some(p => {
    const rules = [...p.authority.allowedValues, ...p.authority.resources].filter(r => r.explanationFactId === factId);
    return rules.length > 0 && rules.some(r => !('requiredWhen' in r) || matchesPredicate(terms, r.requiredWhen)) && rules.every(r => !evaluateAuthority(s, p.party, terms, 'accept').violations.some(v => v.ruleId === r.id));
  });
}
export const neutral = () => ({ tone: 'neutral' as const, acknowledgementFactId: null, argumentId: null, contradictsFactId: null, evidenceRefs: [] });
export function validateSuggestion(s: ScenarioDefinition, before: NegotiationState, input: unknown): CanonicalAction | null {
  const parsed = CanonicalActionSchema.safeParse(input);
  if (!parsed.success || before.terminalReason || before.turnNumber >= before.maxTurns) return null;
  const action = parsed.data;
  if (validateActionContext(s, before, action).length) return null;
  if ((action.kind === 'offer' || action.kind === 'counter_offer') && !feasible(s, before, action.terms)) return null;
  return action;
}
