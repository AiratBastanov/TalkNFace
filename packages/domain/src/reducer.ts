import { CommandSchema, NegotiationStateSchema, ScenarioDefinitionSchema, SessionIdentitySchema, assertNever } from '@arena/contracts';
import type { CanonicalAction, DomainError, DomainEvent, EventPayload, NegotiationState, Offer, PublicProjection, ScenarioDefinition, SessionIdentity, TerminalReason } from '@arena/contracts';
import { validateActionContext } from './action-validation.ts';
import { evaluateAuthority, grantedResources } from './authority.ts';
import { evaluateConstraints } from './constraints.ts';
import { commitmentDisclosures, questionDisclosures } from './disclosure.ts';
import { normalizePackage, packageKey, required } from './enumerate.ts';
import { selectCounteroffer } from './offers.ts';
import { classifyOutcome } from './outcomes.ts';
import { aspiration, INITIAL_SOCIAL, qualifiesConditionalExchange, socialEffect } from './policy.ts';
import { projectPlayer } from './projection.ts';
import { evaluateUtility, participant } from './utility.ts';

/** Use a semantically validated immutable definition. IDs come from the caller, never a clock or RNG. */
export function createInitialState(scenario: ScenarioDefinition, identity: SessionIdentity): NegotiationState {
  ScenarioDefinitionSchema.parse(scenario);
  SessionIdentitySchema.parse(identity);
  const player = participant(scenario, 'player');
  return NegotiationStateSchema.parse({
    ...identity, configHash: scenario.configFingerprint, engineVersion: 'deterministic-core-v1', rubricVersion: scenario.evaluation.rubricVersion,
    revision: 0, phase: 'briefing', turnNumber: 0, maxTurns: scenario.policy.maxTurns,
    ...INITIAL_SOCIAL[scenario.policy.tone], warning: false,
    knownFactIds: scenario.facts.filter(fact => fact.visibility === 'public' || fact.ownerId === player.id).map(fact => fact.id),
    earnedEventKeys: [], progressCredits: 0, groundedArgumentIds: [], resourceAuthorizations: [], activeOffer: null, lastUserOffer: null, agreementOffer: null,
    terminalReason: null, outcome: null, events: [],
  });
}
export type TransitionResult =
  | { ok: true; state: NegotiationState; events: DomainEvent[]; public: PublicProjection }
  | { ok: false; state: NegotiationState; errors: DomainError[] };

export function transition(scenario: ScenarioDefinition, before: NegotiationState, input: unknown): TransitionResult {
  const fail = (code: string, message: string): TransitionResult => ({ ok: false, state: before, errors: [{ code, path: '/', ref: null, message }] });
  const command = CommandSchema.safeParse(input);
  if (!command.success) return fail('INVALID_COMMAND', 'Command shape is invalid.');
  if (command.data.expectedRevision !== before.revision) return fail('STALE_REVISION', 'Revision does not match.');
  if (!NegotiationStateSchema.safeParse(before).success || before.revision !== before.turnNumber || before.configHash !== scenario.configFingerprint || before.rubricVersion !== scenario.evaluation.rubricVersion) return fail('INVALID_STATE', 'State/version boundary is invalid.');
  if (before.terminalReason !== null || ['agreed', 'player_walkaway', 'opponent_walkaway', 'round_limit'].includes(before.phase) || before.turnNumber >= before.maxTurns) return fail('TERMINAL_SESSION', 'Terminal session cannot play another action.');
  let action: CanonicalAction = command.data.action;
  const errors = validateActionContext(scenario, before, action);
  if (errors.length) return { ok: false, state: before, errors };
  if (action.kind === 'offer' || action.kind === 'counter_offer') {
    const normalized = normalizePackage(scenario, action.terms);
    if (!normalized.ok) return { ok: false, state: before, errors: normalized.errors };
    action = { ...action, terms: normalized.terms };
  }
  const state = NegotiationStateSchema.parse(before);
  const social = socialEffect(scenario, before, action);
  state.trust = social.trust; state.tension = social.tension; state.warning = social.warning;
  state.turnNumber += 1; state.revision += 1;
  state.phase = action.kind === 'offer' || action.kind === 'counter_offer' ? 'bargaining' : 'exploring';
  state.earnedEventKeys.push(...social.earnedKeys);
  state.groundedArgumentIds.push(...social.groundedIds);
  const emitted: DomainEvent[] = [];
  const emit = (payload: EventPayload) => {
    const sequence = state.events.length + 1;
    const event = { id: `${state.sessionId}:event:${sequence}`, sequence, turnNumber: state.turnNumber, payload };
    state.events.push(event); emitted.push(event);
  };
  emit({ type: 'action_played', requestId: command.data.requestId, action });
  social.events.forEach(emit);
  const disclose = (ids: readonly string[], via: 'question' | 'constraint_explanation' | 'opponent_commitment') => {
    for (const id of ids) if (!state.knownFactIds.includes(id)) { state.knownFactIds.push(id); emit({ type: 'fact_disclosed', factId: id, via }); }
  };
  const discovered = questionDisclosures(scenario, state, action);
  disclose(discovered, 'question');
  const progressKeys = [
    ...discovered.filter(id => scenario.facts.some(fact => fact.id === id && fact.interestId !== null)).map(id => `credit:discovery:${id}`),
    ...social.progressKeys,
  ];
  const physical = !social.opponentWalkaway && (action.kind === 'offer' || action.kind === 'counter_offer') ? evaluateConstraints(scenario, action.terms) : null;
  const authority = !social.opponentWalkaway && (action.kind === 'offer' || action.kind === 'counter_offer') ? {
    violations: [...evaluateAuthority(scenario, 'player', action.terms, 'propose', before.resourceAuthorizations).violations, ...evaluateAuthority(scenario, 'opponent', action.terms, 'accept', before.resourceAuthorizations).violations],
  } : null;
  if ((action.kind === 'offer' || action.kind === 'counter_offer') && physical?.feasible && authority?.violations.length === 0) {
    const terms = action.terms;
    const previouslyOffered = before.events.some(event => event.payload.type === 'offer_proposed' && packageKey(scenario, event.payload.offer.terms) === packageKey(scenario, terms));
    if (!before.earnedEventKeys.includes('offer:feasible-seen')) {
      // The first feasible offer is a one-time opportunity, including a damaging turn.
      state.earnedEventKeys.push('offer:feasible-seen');
      if (!previouslyOffered) progressKeys.push('credit:offer:first');
    }
    if (!previouslyOffered && qualifiesConditionalExchange(scenario, before, action.terms, action.conditionalOn)) {
      const positions = (terms: typeof action.terms) => scenario.issues.map(issue => issue.values.findIndex(value => terms.some(term => term.issueId === issue.id && term.valueId === value.id))).join('.');
      progressKeys.push(`credit:exchange:${positions(required(before.lastUserOffer ?? undefined, 'previous offer').terms)}:${positions(action.terms)}`);
    }
  }
  if (!social.damaging) {
    const fresh = progressKeys.filter((key, index) => !state.earnedEventKeys.includes(key) && progressKeys.indexOf(key) === index);
    // Record all one-time opportunities, even when the per-turn cap selects only one.
    state.earnedEventKeys.push(...fresh);
    const key = fresh[0];
    if (key !== undefined && state.progressCredits < 5) { state.progressCredits += 1; emit({ type: 'progress_credit_earned', key, total: state.progressCredits }); }
  }
  const closeActive = (reason: 'replaced' | 'accepted' | 'session_terminated') => {
    if (state.activeOffer) emit({ type: 'offer_closed', offerId: state.activeOffer.id, reason });
    state.activeOffer = null;
  };
  const finish = (reason: TerminalReason, agreement: Offer | null = null) => {
    state.phase = reason; state.terminalReason = reason; state.agreementOffer = agreement;
    state.outcome = classifyOutcome(scenario, reason, agreement);
    closeActive(reason === 'agreed' ? 'accepted' : 'session_terminated');
    if (reason === 'agreed') emit({ type: 'agreement_reached', outcome: state.outcome });
    else if (reason === 'player_walkaway') emit({ type: 'player_walkaway' });
    else if (reason === 'opponent_walkaway') emit({ type: 'opponent_walkaway' });
    else emit({ type: 'round_limit' });
  };
  if (social.opponentWalkaway) finish('opponent_walkaway');
  else switch (action.kind) {
    case 'offer':
    case 'counter_offer': {
      if (evaluateAuthority(scenario, 'player', action.terms, 'propose', state.resourceAuthorizations).feasible) for (const resourceId of grantedResources(scenario, action.terms)) if (!state.resourceAuthorizations.includes(resourceId)) {
        state.resourceAuthorizations.push(resourceId); emit({ type: 'resource_authorized', resourceId });
      }
      const offer: Offer = { id: `${state.sessionId}:offer:${state.turnNumber}:player`, proposer: 'player', terms: action.terms, turnNumber: state.turnNumber, supersedesId: before.lastUserOffer?.id ?? null };
      state.lastUserOffer = offer;
      emit({ type: 'offer_proposed', offer });
      const threshold = aspiration(scenario, state, offer.terms);
      const utility = evaluateUtility(scenario, 'opponent', offer.terms);
      const physicalResult = required(physical ?? undefined, 'physical result');
      const authorityResult = required(authority ?? undefined, 'authority result');
      if (!physicalResult.feasible) {
        emit({ type: 'offer_rejected_physical', offerId: offer.id, ruleIds: physicalResult.violations.map(item => item.ruleId), reasonCodes: physicalResult.violations.map(item => item.reasonCode) });
        disclose(physicalResult.violations.map(item => item.explanationFactId), 'constraint_explanation');
      } else if (authorityResult.violations.length) {
        emit({ type: 'offer_rejected_authority', offerId: offer.id, ruleIds: authorityResult.violations.map(item => item.ruleId), reasonCodes: authorityResult.violations.map(item => item.reasonCode) });
        disclose(authorityResult.violations.map(item => item.explanationFactId), 'constraint_explanation');
      } else if (utility >= threshold) {
        disclose(commitmentDisclosures(scenario, state, offer.terms), 'opponent_commitment');
        finish('agreed', offer); break;
      } else emit({ type: 'offer_rejected_aspiration', offerId: offer.id, utility, aspiration: threshold });
      const candidate = selectCounteroffer(scenario, state, offer.terms);
      if (candidate) {
        const counter: Offer = { id: `${state.sessionId}:offer:${state.turnNumber}:opponent`, proposer: 'opponent', terms: candidate.terms, turnNumber: state.turnNumber, supersedesId: state.activeOffer?.id ?? null };
        closeActive('replaced'); state.activeOffer = counter;
        emit({ type: 'counteroffer_created', offer: counter });
        disclose(commitmentDisclosures(scenario, state, counter.terms), 'opponent_commitment');
      } else emit({ type: 'counteroffer_unavailable', reasonCode: 'NO_ACCEPTABLE_CANDIDATE' });
      break;
    }
    case 'accept': {
      const offer = required(state.activeOffer ?? undefined, 'active offer');
      // An issued commitment is binding. Current aspiration is deliberately not queried here.
      emit({ type: 'active_offer_accepted', offerId: offer.id });
      disclose(commitmentDisclosures(scenario, state, offer.terms), 'opponent_commitment');
      finish('agreed', offer); break;
    }
    case 'walk_away': finish('player_walkaway'); break;
    case 'question': case 'acknowledge': case 'argument': case 'pressure': case 'clarification': break;
    default: assertNever(action);
  }
  if (state.terminalReason === null && state.turnNumber === state.maxTurns) finish('round_limit');
  NegotiationStateSchema.parse(state);
  return { ok: true, state, events: emitted, public: projectPlayer(scenario, state) };
}
