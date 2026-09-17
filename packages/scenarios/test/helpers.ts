import type { CanonicalAction, NegotiationState, ScenarioDefinition } from '@arena/contracts';
import { createInitialState, transition } from '@arena/domain';

export function initial(scenario: ScenarioDefinition): NegotiationState { return createInitialState(scenario, { sessionId: 'test-session', scenarioVersionId: 'reference-v1' }); }
export function step(scenario: ScenarioDefinition, state: NegotiationState, action: CanonicalAction): NegotiationState {
  const result = transition(scenario, state, { expectedRevision: state.revision, requestId: `request-${state.revision}`, action });
  if (!result.ok) throw new Error(JSON.stringify(result.errors));
  return result.state;
}
export function play(scenario: ScenarioDefinition, actions: readonly CanonicalAction[], start = initial(scenario)): NegotiationState {
  return actions.reduce((state, action) => step(scenario, state, action), start);
}
export function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === 'object') { for (const child of Object.values(value)) deepFreeze(child); Object.freeze(value); }
  return value;
}
