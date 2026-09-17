import type { CanonicalAction, DomainError, NegotiationState, ScenarioDefinition } from '@arena/contracts';
import { evaluateAuthority } from './authority.ts';
import { evaluateConstraints } from './constraints.ts';
import { normalizePackage } from './enumerate.ts';

export function validateActionReferences(scenario: ScenarioDefinition, knownFactIds: readonly string[], action: CanonicalAction): DomainError[] {
  const errors: DomainError[] = [];
  const error = (code: string, path: string, ref: string | null, message: string) => errors.push({ code, path, ref, message });
  if (action.kind === 'question') {
    for (const id of [action.primaryTopicId, action.secondaryTopicId]) if (id !== null && !scenario.topics.some(topic => topic.id === id)) error('UNKNOWN_TOPIC', '/action', id, 'Unknown public topic.');
    if (action.primaryTopicId === action.secondaryTopicId) error('DUPLICATE_TOPIC', '/action/secondaryTopicId', action.secondaryTopicId, 'Topics must differ.');
  }
  if (action.acknowledgementFactId !== null && (!knownFactIds.includes(action.acknowledgementFactId) || !scenario.acknowledgementTargets.some(target => target.factId === action.acknowledgementFactId))) error('UNAVAILABLE_ACKNOWLEDGEMENT', '/action/acknowledgementFactId', null, 'Acknowledgement requires an available known fact.');
  if (action.argumentId !== null) {
    const binding = scenario.arguments.find(item => item.id === action.argumentId);
    if (!binding || !binding.factIds.every(id => knownFactIds.includes(id))) error('UNAVAILABLE_ARGUMENT', '/action/argumentId', null, 'Argument requires evidence known before this turn.');
  }
  if (action.contradictsFactId !== null && !knownFactIds.includes(action.contradictsFactId)) error('UNAVAILABLE_FACT', '/action/contradictsFactId', null, 'Contradiction must reference an established fact.');
  if (action.kind === 'offer' || action.kind === 'counter_offer') {
    const normalized = normalizePackage(scenario, action.terms);
    if (!normalized.ok) errors.push(...normalized.errors);
    for (const [index, term] of action.conditionalOn.entries()) {
      if (!action.terms.some(item => item.issueId === term.issueId && item.valueId === term.valueId)) error('CONDITION_NOT_IN_PACKAGE', `/action/conditionalOn/${index}`, term.issueId, 'Reciprocal condition must be present in the complete offer.');
      if (action.conditionalOn.slice(0, index).some(item => item.issueId === term.issueId)) error('DUPLICATE_CONDITION', `/action/conditionalOn/${index}`, term.issueId, 'Conditional issue must occur once.');
    }
  }
  for (const [index, ref] of action.evidenceRefs.entries()) {
    if (ref.span !== null && ref.span.start >= ref.span.end) error('INVALID_SPAN', `/action/evidenceRefs/${index}/span`, ref.id, 'UTF-16 start must precede end.');
    if (action.evidenceRefs.slice(0, index).some(item => item.id === ref.id)) error('DUPLICATE_EVIDENCE', `/action/evidenceRefs/${index}`, ref.id, 'Evidence IDs must be unique.');
  }
  return errors;
}
export function validateActionContext(scenario: ScenarioDefinition, state: NegotiationState, action: CanonicalAction): DomainError[] {
  const errors = validateActionReferences(scenario, state.knownFactIds, action);
  if (action.kind === 'accept' || action.kind === 'counter_offer') {
    const id = action.kind === 'accept' ? action.offerId : action.targetOfferId;
    if (!state.activeOffer || state.activeOffer.id !== id) errors.push({ code: 'STALE_OFFER', path: '/action', ref: null, message: 'The exact active opponent offer is required.' });
    else if (action.kind === 'accept' && (!evaluateConstraints(scenario, state.activeOffer.terms).feasible || !evaluateAuthority(scenario, 'player', state.activeOffer.terms, 'accept').feasible || !evaluateAuthority(scenario, 'opponent', state.activeOffer.terms, 'accept').feasible)) errors.push({ code: 'INVALID_COMMITMENT', path: '/action/offerId', ref: null, message: 'The commitment violates an absolute bound.' });
  }
  return errors;
}
