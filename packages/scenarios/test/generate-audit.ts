import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import type { CanonicalAction, ScenarioDefinition } from '@arena/contracts';
import { argumentDiscount, aspiration, createInitialState, evaluateAuthority, evaluateConstraints, transition, validateScenario } from '@arena/domain';
import { S1, S2, argument, offer, question, supplyTerms, workloadTerms } from '../src/index.ts';
import { GOLDENS } from './goldens.ts';

function replay(scenario: ScenarioDefinition, id: string, actions: CanonicalAction[]) {
  let state = createInitialState(scenario, { sessionId: `audit-${id}`, scenarioVersionId: 'reference-v1' });
  const steps = [];
  for (const action of actions) {
    const result = transition(scenario, state, { expectedRevision: state.revision, requestId: `action-${state.revision + 1}`, action });
    if (!result.ok) throw new Error(JSON.stringify(result.errors));
    state = result.state;
    const terms = action.kind === 'offer' || action.kind === 'counter_offer' ? action.terms : state.activeOffer?.terms ?? null;
    steps.push({ turn: state.turnNumber, action, trust: state.trust, tension: state.tension, credits: state.progressCredits,
      discount: terms ? argumentDiscount(scenario, state, terms) : null, aspiration: terms ? aspiration(scenario, state, terms) : null,
      activeOffer: state.activeOffer, events: result.events });
  }
  const terms = state.agreementOffer?.terms ?? state.lastUserOffer?.terms ?? null;
  return {
    summary: { phase: state.phase, turn: state.turnNumber, trust: state.trust, tension: state.tension, credits: state.progressCredits,
      discount: terms ? argumentDiscount(scenario, state, terms) : null, aspiration: terms ? aspiration(scenario, state, terms) : null,
      terms: state.agreementOffer?.terms ?? null, outcome: state.outcome },
    steps,
  };
}
const models = [S1, S2].map(scenario => {
  const validation = validateScenario(scenario);
  assert.equal(validation.valid, true, JSON.stringify(validation.errors));
  return { templateId: scenario.templateId, schemaVersion: scenario.schemaVersion, configFingerprint: scenario.configFingerprint, coverage: validation.coverage };
});
const goldenTraces = GOLDENS.map(fixture => {
  const actual = replay(fixture.scenario, fixture.id, fixture.actions);
  assert.deepEqual(actual, replay(fixture.scenario, fixture.id, fixture.actions));
  return { id: fixture.id, deterministicReplay: true, ...actual };
});
const prefix = S1.validation.witnessTraces[0]!.actions.slice(0, 3);
const causalPairs = {
  W1: { respectful: replay(S1, 'W1-open', [question('logistics', 'respectful_firm')]), accusatory: replay(S1, 'W1-accusatory', [question('logistics', 'accusatory')]) },
  A1: { withoutArgument: replay(S1, 'A1-without', [...prefix, offer(supplyTerms(90, 'split40at7_rest14', 50))]), withArgument: replay(S1, 'A1-with', [...prefix, argument('logistics-argument'), offer(supplyTerms(90, 'split40at7_rest14', 50))]) },
};
const accountManager = structuredClone(S1);
accountManager.participants[1].roleId = 'account-manager';
accountManager.participants[1].authority.allowedValues[0]!.valueIds = ['100', '105', '110', '115'];
const examples = {
  s1Physical: evaluateConstraints(S1, supplyTerms(95, 'all14', 50)),
  s2Physical: evaluateConstraints(S2, workloadTerms('full', 2, 0, 0)),
  s1Authority: evaluateAuthority(accountManager, 'opponent', supplyTerms(95, 'split40at7_rest14', 50), 'accept'),
  s2ProposalAuthority: evaluateAuthority(S2, 'opponent', workloadTerms('core', 2, 1, 1), 'propose'),
  s1Aspiration: replay(S1, 's1-aspiration', [offer(supplyTerms(90, 'all7', 0))]),
  s2Aspiration: replay(S2, 's2-aspiration', [offer(workloadTerms('core', 2, 1, 0))]),
};
const directory = new URL('../../../docs/gates/evidence/', import.meta.url);
mkdirSync(directory, { recursive: true });
writeFileSync(new URL('G1_MODEL_AUDIT.json', directory), JSON.stringify({ formatVersion: 1, engineVersion: 'deterministic-core-v1', models, goldenTraces, causalPairs, examples }, null, 2) + '\n', 'utf8');
console.log(JSON.stringify({ result: 'PASS', models: models.map(model => ({ id: model.templateId, raw: model.coverage?.raw, feasible: model.coverage?.physicallyFeasible, rational: model.coverage?.individuallyRational, target: model.coverage?.playerTargetReaching, poor: model.coverage?.poorAgreements })), goldenReplays: goldenTraces.length, artifact: 'docs/gates/evidence/G1_MODEL_AUDIT.json' }));
