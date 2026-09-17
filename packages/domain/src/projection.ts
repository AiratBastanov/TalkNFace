import { NegotiationStateSchema, PublicProjectionSchema } from '@arena/contracts';
import type { NegotiationState, PublicProjection, ScenarioDefinition } from '@arena/contracts';
import { participant } from './utility.ts';

export function projectPlayer(scenario: ScenarioDefinition, state: NegotiationState): PublicProjection {
  const player = participant(scenario, 'player');
  const opponent = participant(scenario, 'opponent');
  // Explicit allowlist. Never spread a scenario, participant, fact, event or private outcome.
  return PublicProjectionSchema.parse({
    sessionId: state.sessionId, revision: state.revision, phase: state.phase, turnNumber: state.turnNumber, maxTurns: state.maxTurns,
    scenario: {
      title: scenario.title, sphere: scenario.sphere, topic: scenario.topic, publicBrief: scenario.publicBrief,
      player: { id: player.id, label: player.label, roleId: player.roleId, privateBrief: player.privateBrief, initialPosition: player.initialPosition,
        goals: player.goals.map(goal => ({ id: goal.id, text: goal.text })), target: player.target, reservation: player.reservation,
        batna: { description: player.batna.description, utility: player.batna.utility } },
      opponent: { label: opponent.label, roleId: opponent.roleId, initialPosition: opponent.initialPosition },
      issues: scenario.issues.map(issue => ({ id: issue.id, label: issue.label, unit: issue.unit, ordered: issue.ordered, values: issue.values.map(value => ({ id: value.id, label: value.label, quantity: value.quantity })) })),
      topics: scenario.topics.map(topic => ({ id: topic.id, label: topic.label })),
    },
    knownFacts: scenario.facts.filter(fact => state.knownFactIds.includes(fact.id)).map(fact => ({ id: fact.id, text: fact.text })),
    availableArguments: scenario.arguments.filter(binding => binding.factIds.every(id => state.knownFactIds.includes(id))).map(binding => ({ id: binding.id, label: binding.label })),
    acknowledgementFactIds: scenario.acknowledgementTargets.filter(target => state.knownFactIds.includes(target.factId)).map(target => target.factId),
    activeOffer: state.activeOffer, lastUserOffer: state.lastUserOffer, agreementOffer: state.agreementOffer,
    stance: state.terminalReason ? 'closed' : state.warning ? 'warning' : state.tension >= 50 ? 'strained' : 'calm',
    outcome: state.outcome ? { family: state.outcome.family, terminalReason: state.outcome.terminalReason, playerUtility: state.outcome.playerUtility, playerBatna: state.outcome.playerBatna, playerTarget: state.outcome.playerTarget } : null,
  });
}
/** Trusted server/evidence use only; never a player DTO. Parsing makes an independent copy. */
export function projectPrivateState(state: NegotiationState): NegotiationState { return NegotiationStateSchema.parse(state); }
