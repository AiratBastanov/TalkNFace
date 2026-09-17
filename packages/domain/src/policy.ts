import type { CanonicalAction, EventPayload, NegotiationState, Package, ScenarioDefinition } from '@arena/contracts';
import { matchesPredicate, required, valueOf } from './enumerate.ts';
import { evaluateUtility, participant } from './utility.ts';

// Frozen pedagogical policy, not an empirical model of human behaviour.
export const POLICY = {
  beginner: { premium: 8, disclosureThreshold: 35 },
  normal: { premium: 15, disclosureThreshold: 45 },
  advanced: { premium: 20, disclosureThreshold: 55 },
} as const;
export const INITIAL_SOCIAL = { neutral: { trust: 50, tension: 20 }, friendly: { trust: 60, tension: 10 }, skeptical: { trust: 40, tension: 30 } } as const;
export function argumentDiscount(scenario: ScenarioDefinition, state: NegotiationState, terms: Package): number {
  return Math.min(4, 2 * scenario.arguments.filter(binding => binding.interestId !== null && state.groundedArgumentIds.includes(binding.id) && matchesPredicate(terms, binding.condition)).length);
}
export function aspiration(scenario: ScenarioDefinition, state: NegotiationState, terms: Package): number {
  const reservation = participant(scenario, 'opponent').reservation;
  return Math.max(reservation, reservation + POLICY[scenario.policy.difficulty].premium - 2 * state.progressCredits - argumentDiscount(scenario, state, terms) - Math.floor(Math.max(state.trust - 50, 0) / 10));
}
export type SocialEffect = { trust: number; tension: number; warning: boolean; damaging: boolean; opponentWalkaway: boolean; earnedKeys: string[]; groundedIds: string[]; progressKeys: string[]; events: EventPayload[] };
export function socialEffect(scenario: ScenarioDefinition, before: NegotiationState, action: CanonicalAction): SocialEffect {
  const result: SocialEffect = { trust: before.trust, tension: before.tension, warning: before.warning, damaging: false, opponentWalkaway: false, earnedKeys: [], groundedIds: [], progressKeys: [], events: [] };
  const effect = action.tone === 'threat' ? 'threat' : action.contradictsFactId !== null ? 'contradiction' : action.tone === 'accusatory' ? 'accusation' : null;
  result.damaging = effect !== null;
  let trustGain = 0;
  const fresh = (key: string) => !before.earnedEventKeys.includes(key);
  if (action.kind === 'question') {
    const key = `question:${action.primaryTopicId}`;
    const first = fresh(key);
    result.events.push({ type: 'topic_asked', topicId: action.primaryTopicId, first });
    if (first) { result.earnedKeys.push(key); if (!result.damaging) trustGain += 4; }
  }
  if (!result.damaging) {
    if (action.acknowledgementFactId !== null) {
      const factId = action.acknowledgementFactId;
      const key = `ack:${factId}`;
      const first = fresh(key);
      result.events.push({ type: 'fact_acknowledged', factId, first });
      if (first) {
        trustGain += 6;
        result.tension -= scenario.policy.tone === 'skeptical' ? 2 : 4;
        result.earnedKeys.push(key);
        if (scenario.acknowledgementTargets.some(target => target.factId === factId && target.countsAsConstraint)) {
          result.progressKeys.push(`credit:${key}`);
          if (before.warning) { result.warning = false; result.events.push({ type: 'tension_repaired', factId }); }
        }
      }
    }
    if (action.argumentId !== null) {
      const binding = required(scenario.arguments.find(item => item.id === action.argumentId), 'argument');
      const key = `argument:${binding.id}`;
      const first = fresh(key);
      result.events.push({ type: 'grounded_argument_applied', argumentId: binding.id, first });
      if (first) {
        trustGain += 4;
        result.earnedKeys.push(key);
        if (binding.interestId !== null) { result.groundedIds.push(binding.id); result.progressKeys.push(`credit:${key}`); }
      }
    }
    result.trust += Math.min(6, trustGain);
  } else if (effect !== null) {
    result.events.push({ type: 'damaging_tone', effect });
    result.trust -= effect === 'threat' ? 15 : effect === 'contradiction' ? 10 : 8;
    result.tension += effect === 'threat' ? 20 : effect === 'accusation' ? 10 : 0;
    result.opponentWalkaway = before.warning;
  }
  result.trust = Math.max(0, Math.min(100, result.trust));
  result.tension = Math.max(0, Math.min(100, result.tension));
  const repaired = result.events.some(event => event.type === 'tension_repaired');
  if (result.tension >= 80 && !result.warning && !repaired) { result.warning = true; result.events.push({ type: 'tension_warning' }); }
  result.events.push({ type: 'social_state_changed', trustBefore: before.trust, trustAfter: result.trust, tensionBefore: before.tension, tensionAfter: result.tension });
  return result;
}
export function qualifiesConditionalExchange(scenario: ScenarioDefinition, before: NegotiationState, terms: Package, conditionalOn: Package): boolean {
  const previous = before.lastUserOffer?.terms;
  if (!previous || conditionalOn.length === 0 || evaluateUtility(scenario, 'opponent', terms) <= evaluateUtility(scenario, 'opponent', previous)) return false;
  // Isolate the requested improvement, and prove the reciprocal change is on another issue.
  return conditionalOn.some(condition => {
    if (valueOf(previous, condition.issueId) === condition.valueId) return false;
    const requested = previous.map(term => term.issueId === condition.issueId ? { ...condition } : { ...term });
    const otherChanges = terms.map(term => term.issueId === condition.issueId ? required(previous.find(old => old.issueId === term.issueId), 'conditional issue') : term);
    return evaluateUtility(scenario, 'player', requested) > evaluateUtility(scenario, 'player', previous)
      && evaluateUtility(scenario, 'opponent', otherChanges) > evaluateUtility(scenario, 'opponent', previous);
  });
}
