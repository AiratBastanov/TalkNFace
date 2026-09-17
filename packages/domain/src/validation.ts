import { ScenarioDefinitionSchema, assertNever } from '@arena/contracts';
import type { DomainError, PackagePredicate, ScenarioDefinition } from '@arena/contracts';
import { validateActionReferences } from './action-validation.ts';
import { evaluateAuthority } from './authority.ts';
import { evaluateConstraints } from './constraints.ts';
import { enumeratePackages } from './enumerate.ts';
import type { CatalogEntry } from './enumerate.ts';
import { createInitialState, transition } from './reducer.ts';
import { evaluateUtility, participant } from './utility.ts';

export type AuditedPackage = CatalogEntry & { playerUtility: number; opponentUtility: number; physicallyFeasible: boolean; authorityValid: boolean; individuallyRational: boolean; playerTargetReached: boolean };
export type CoverageSummary = { raw: number; physicallyFeasible: number; authorityValid: number; individuallyRational: number; playerTargetReaching: number; poorAgreements: number; pareto: AuditedPackage[]; packages: AuditedPackage[] };
export function auditModel(scenario: ScenarioDefinition): CoverageSummary {
  const player = participant(scenario, 'player');
  const opponent = participant(scenario, 'opponent');
  const packages = enumeratePackages(scenario).map(entry => {
    const playerUtility = evaluateUtility(scenario, 'player', entry.terms);
    const opponentUtility = evaluateUtility(scenario, 'opponent', entry.terms);
    const physicallyFeasible = evaluateConstraints(scenario, entry.terms).feasible;
    const authorityValid = evaluateAuthority(scenario, 'player', entry.terms, 'propose').feasible && evaluateAuthority(scenario, 'opponent', entry.terms, 'accept').feasible;
    const individuallyRational = physicallyFeasible && authorityValid && playerUtility >= player.reservation && opponentUtility >= opponent.reservation;
    return { ...entry, playerUtility, opponentUtility, physicallyFeasible, authorityValid, individuallyRational, playerTargetReached: individuallyRational && playerUtility >= player.target };
  });
  const rational = packages.filter(row => row.individuallyRational);
  return {
    raw: packages.length, physicallyFeasible: packages.filter(row => row.physicallyFeasible).length,
    authorityValid: packages.filter(row => row.physicallyFeasible && row.authorityValid).length,
    individuallyRational: rational.length, playerTargetReaching: packages.filter(row => row.playerTargetReached).length,
    poorAgreements: packages.filter(row => row.physicallyFeasible && row.authorityValid && row.opponentUtility >= opponent.reservation && row.playerUtility < player.reservation).length,
    pareto: rational.filter(row => !rational.some(other => other.playerUtility >= row.playerUtility && other.opponentUtility >= row.opponentUtility && (other.playerUtility > row.playerUtility || other.opponentUtility > row.opponentUtility))),
    packages,
  };
}
export type ScenarioValidation =
  | { valid: true; scenario: ScenarioDefinition; errors: []; coverage: CoverageSummary }
  | { valid: false; errors: DomainError[]; coverage: CoverageSummary | null };

/** Private authoring/domain boundary. Call projectValidationForPlayer before exposing a failure to a player. */
export function validateScenario(input: unknown): ScenarioValidation {
  const parsed = ScenarioDefinitionSchema.safeParse(input);
  if (!parsed.success) return { valid: false, coverage: null, errors: parsed.error.issues.slice(0, 128).map(issue => ({ code: 'SCHEMA_INVALID', path: '/' + issue.path.map(String).join('/'), ref: null, message: 'Field violates the strict ScenarioDefinition v1 schema.' })) };
  const scenario = parsed.data;
  const errors: DomainError[] = [];
  const add = (code: string, path: string, ref: string | null, message: string) => { if (errors.length < 128) errors.push({ code, path, ref, message }); };
  const unique = (ids: readonly string[], path: string) => ids.forEach((id, index) => { if (ids.indexOf(id) !== index) add('DUPLICATE_ID', `${path}/${index}`, id.length <= 64 ? id : null, 'IDs must be unique within their namespace.'); });
  const reference = (id: string, ids: readonly string[], path: string) => { if (!ids.includes(id)) add('UNKNOWN_REFERENCE', path, id, 'Reference does not resolve.'); };
  const issueIds = scenario.issues.map(issue => issue.id);
  const participantIds = scenario.participants.map(party => party.id);
  const goalIds = scenario.participants.flatMap(party => party.goals.map(goal => goal.id));
  const interestIds = scenario.participants.flatMap(party => party.interests.map(interest => interest.id));
  const factIds = scenario.facts.map(fact => fact.id);
  const topicIds = scenario.topics.map(topic => topic.id);
  const rules = [...scenario.constraints, ...scenario.participants.flatMap(party => [...party.authority.allowedValues, ...party.authority.resources])];
  const ruleIds = rules.map(rule => rule.id);
  unique(issueIds, '/issues'); unique(participantIds, '/participants'); unique(goalIds, '/goals'); unique(interestIds, '/interests'); unique(factIds, '/facts'); unique(topicIds, '/topics'); unique(ruleIds, '/rules');
  unique(scenario.arguments.map(binding => binding.id), '/arguments');
  unique(scenario.acknowledgementTargets.map(target => target.factId), '/acknowledgementTargets');
  unique(scenario.validation.witnessTraces.map(trace => trace.id), '/validation/witnessTraces');
  if (scenario.participants[0].party !== 'player' || scenario.participants[1].party !== 'opponent') add('PARTICIPANT_ROLES', '/participants', null, 'Participants must be player followed by opponent.');
  for (const [index, issue] of scenario.issues.entries()) unique(issue.values.map(value => value.id), `/issues/${index}/values`);
  const values = (issueId: string, ids: readonly string[], path: string, complete = false) => {
    reference(issueId, issueIds, path + '/issueId'); unique(ids, path);
    const issue = scenario.issues.find(item => item.id === issueId);
    if (!issue) return;
    for (const id of ids) reference(id, issue.values.map(value => value.id), path);
    if (complete && issue.values.some(value => !ids.includes(value.id))) add('MISSING_CELL', path, issueId, 'Lookup must cover every issue value.');
  };
  const refs = (ids: readonly string[], allowed: readonly string[], path: string) => { unique(ids, path); ids.forEach(id => reference(id, allowed, path)); };
  const predicate = (items: PackagePredicate, path: string) => {
    unique(items.map(item => item.issueId), path);
    items.forEach((item, index) => {
      switch (item.kind) {
        case 'eq': values(item.issueId, [item.valueId], `${path}/${index}`); break;
        case 'in': values(item.issueId, item.valueIds, `${path}/${index}`); break;
        default: assertNever(item);
      }
    });
  };
  for (const [p, party] of scenario.participants.entries()) {
    const path = `/participants/${p}`;
    if (party.reservation !== party.batna.utility) add('BATNA_RESERVATION_MISMATCH', path + '/reservation', party.id, 'Reservation must equal BATNA utility in v1.');
    if (party.target < party.reservation) add('TARGET_BELOW_RESERVATION', path + '/target', party.id, 'Target cannot be below reservation.');
    for (const [i, goal] of party.goals.entries()) refs(goal.issueIds, issueIds, `${path}/goals/${i}/issueIds`);
    for (const [i, interest] of party.interests.entries()) refs(interest.issueIds, issueIds, `${path}/interests/${i}/issueIds`);
    unique(party.utility.unary.map(table => table.issueId), path + '/utility/unary');
    for (const issueId of issueIds) if (!party.utility.unary.some(table => table.issueId === issueId)) add('MISSING_UTILITY_TABLE', path + '/utility/unary', issueId, 'Every issue needs a complete unary table, including zero contributions.');
    for (const [i, table] of party.utility.unary.entries()) values(table.issueId, table.cells.map(cell => cell.valueId), `${path}/utility/unary/${i}`, true);
    unique(party.utility.pairs.map(table => JSON.stringify([...table.issueIds].sort())), path + '/utility/pairs');
    for (const [i, table] of party.utility.pairs.entries()) {
      const pairPath = `${path}/utility/pairs/${i}`;
      refs(table.issueIds, issueIds, pairPath + '/issueIds');
      unique(table.cells.map(cell => JSON.stringify(cell.valueIds)), pairPath + '/cells');
      for (const [j, cell] of table.cells.entries()) { values(table.issueIds[0], [cell.valueIds[0]], `${pairPath}/cells/${j}/0`); values(table.issueIds[1], [cell.valueIds[1]], `${pairPath}/cells/${j}/1`); }
      const left = scenario.issues.find(issue => issue.id === table.issueIds[0]);
      const right = scenario.issues.find(issue => issue.id === table.issueIds[1]);
      if (left && right) for (const a of left.values) for (const b of right.values) if (!table.cells.some(cell => cell.valueIds[0] === a.id && cell.valueIds[1] === b.id)) add('MISSING_PAIR_CELL', pairPath + '/cells', party.id, 'Pair table must cover its Cartesian product.');
    }
    for (const [i, rule] of party.authority.allowedValues.entries()) values(rule.issueId, rule.valueIds, `${path}/authority/allowedValues/${i}`);
    for (const [i, rule] of party.authority.resources.entries()) { predicate(rule.requiredWhen, `${path}/authority/resources/${i}/requiredWhen`); predicate(rule.grantWhen, `${path}/authority/resources/${i}/grantWhen`); }
  }
  for (const [index, constraint] of scenario.constraints.entries()) {
    const path = `/constraints/${index}`;
    switch (constraint.kind) {
      case 'allowed_values': values(constraint.issueId, constraint.valueIds, path); break;
      case 'forbid_combination': unique(constraint.terms.map(term => term.issueId), path + '/terms'); constraint.terms.forEach(term => values(term.issueId, [term.valueId], path + '/terms')); break;
      case 'linear_lte': unique(constraint.contributions.map(table => table.issueId), path + '/contributions'); constraint.contributions.forEach((table, i) => values(table.issueId, table.cells.map(cell => cell.valueId), `${path}/contributions/${i}`, true)); break;
      default: assertNever(constraint);
    }
  }
  for (const [i, rule] of rules.entries()) {
    reference(rule.explanationFactId, factIds, `/rules/${i}/explanationFactId`);
    const fact = scenario.facts.find(item => item.id === rule.explanationFactId);
    if (fact && fact.visibility !== 'public' && !fact.disclosure.some(trigger => trigger.kind === 'constraint_explanation' && trigger.constraintId === rule.id)) add('UNEXPLAINABLE_CONSTRAINT', `/rules/${i}`, rule.id, 'A hidden explanation requires the corresponding unconditional rejection trigger.');
  }
  const hiddenCount = scenario.facts.filter(fact => fact.visibility === 'hidden').length;
  if (hiddenCount < 2 || hiddenCount > 6) add('HIDDEN_FACT_COUNT', '/facts', null, 'v1 supports 2–6 hidden facts.');
  for (const [i, fact] of scenario.facts.entries()) {
    const path = `/facts/${i}`;
    reference(fact.ownerId, participantIds, path + '/ownerId'); reference(fact.topicId, topicIds, path + '/topicId');
    refs(fact.issueIds, issueIds, path + '/issueIds'); refs(fact.relatedFactIds, factIds, path + '/relatedFactIds');
    if (fact.interestId !== null) {
      const owner = scenario.participants.find(party => party.id === fact.ownerId);
      reference(fact.interestId, owner?.interests.map(interest => interest.id) ?? [], path + '/interestId');
    }
    if (fact.visibility === 'hidden' && fact.disclosure.length === 0) add('UNDISCLOSABLE_FACT', path + '/disclosure', fact.id, 'Hidden facts need a supported disclosure rule.');
    for (const [j, trigger] of fact.disclosure.entries()) {
      const triggerPath = `${path}/disclosure/${j}`;
      switch (trigger.kind) {
        case 'question':
          reference(trigger.topicId, topicIds, triggerPath + '/topicId');
          if (trigger.topicId !== fact.topicId) add('FACT_TOPIC_MISMATCH', triggerPath, fact.id, 'Question disclosure must use the fact topic.');
          if ((fact.kind === 'constraint' || fact.kind === 'authority') && trigger.gate !== 'always') add('LOCKED_EXPLANATION', triggerPath, fact.id, 'Physical and authority explanations cannot depend on trust.');
          break;
        case 'opponent_commitment_contains':
          predicate(trigger.condition, triggerPath + '/condition');
          if (fact.kind !== 'resource') add('COMMITMENT_DISCLOSURE_NOT_RESOURCE', triggerPath, fact.id, 'Commitments disclose resource availability, not hidden motivations.');
          if (!trigger.condition.some(condition => fact.issueIds.includes(condition.issueId))) add('DISCLOSURE_BINDING_MISMATCH', triggerPath, fact.id, 'Commitment predicate must bind to this fact resource.');
          break;
        case 'constraint_explanation':
          reference(trigger.constraintId, ruleIds, triggerPath + '/constraintId');
          if (!rules.some(rule => rule.id === trigger.constraintId && rule.explanationFactId === fact.id)) add('EXPLANATION_BINDING_MISMATCH', triggerPath, fact.id, 'Explanation trigger must reference the rule explained by this fact.');
          break;
        default: assertNever(trigger);
      }
    }
  }
  for (const [i, topic] of scenario.topics.entries()) refs(topic.issueIds, issueIds, `/topics/${i}/issueIds`);
  for (const [i, binding] of scenario.arguments.entries()) {
    const path = `/arguments/${i}`;
    refs(binding.factIds, factIds, path + '/factIds'); predicate(binding.condition, path + '/condition');
    if (binding.interestId !== null) {
      reference(binding.interestId, scenario.participants[1].interests.map(interest => interest.id), path + '/interestId');
      if (!binding.factIds.some(id => scenario.facts.some(fact => fact.id === id && fact.interestId === binding.interestId))) add('UNGROUNDED_INTEREST', path, binding.id, 'Economic argument requires a fact bound to its interest.');
      const interest = scenario.participants[1].interests.find(item => item.id === binding.interestId);
      if (interest && !binding.condition.some(condition => interest.issueIds.includes(condition.issueId))) add('ARGUMENT_BINDING_MISMATCH', path, binding.id, 'Economic predicate must bind to the referenced interest.');
    }
  }
  for (const [i, target] of scenario.acknowledgementTargets.entries()) reference(target.factId, factIds, `/acknowledgementTargets/${i}/factId`);
  refs(scenario.evaluation.goalIds, goalIds, '/evaluation/goalIds'); refs(scenario.evaluation.interestIds, interestIds, '/evaluation/interestIds'); refs(scenario.evaluation.constraintIds, scenario.constraints.map(rule => rule.id), '/evaluation/constraintIds');
  for (const [i, witness] of scenario.validation.witnessTraces.entries()) for (const [j, action] of witness.actions.entries()) for (const error of validateActionReferences(scenario, factIds, action)) add(error.code, `/validation/witnessTraces/${i}/actions/${j}${error.path}`, error.ref, error.message);
  if (errors.length) return { valid: false, errors, coverage: null };
  const coverage = auditModel(scenario);
  if (coverage.physicallyFeasible === 0) add('NO_FEASIBLE_PACKAGE', '/constraints', null, 'Constraints leave no feasible package.');
  if (coverage.individuallyRational < 2) add('INSUFFICIENT_RATIONAL_PACKAGES', '/participants', null, 'At least two distinct mutually rational packages are required.');
  if (coverage.playerTargetReaching === 0) add('UNREACHABLE_TARGET', '/participants/0/target', null, 'Player target must be reachable within absolute bounds.');
  for (const party of ['player', 'opponent'] as const) {
    const utilities = coverage.packages.map(row => party === 'player' ? row.playerUtility : row.opponentUtility);
    if (utilities.some(value => !Number.isSafeInteger(value) || value < -100 || value > 200)) add('UTILITY_RANGE', '/participants', party, 'Simulation utilities must be safe integers in −100…200.');
    const feasibleUtilities = coverage.packages.filter(row => row.physicallyFeasible).map(row => party === 'player' ? row.playerUtility : row.opponentUtility);
    const spread = Math.max(...feasibleUtilities) - Math.min(...feasibleUtilities);
    if (feasibleUtilities.length && (spread < 20 || spread > 100)) add('UTILITY_SPREAD', '/participants', party, 'Utility spread on feasible packages must be 20…100.');
  }
  if (errors.length) return { valid: false, errors, coverage };
  let targetWitness = false;
  const witnessKeys = scenario.validation.witnessTraces.map(trace => JSON.stringify(trace.actions.map(action => ({ ...action, evidenceRefs: [] }))));
  unique(witnessKeys, '/validation/witnessTraces');
  if (witnessKeys.length === 1) add('WITNESS_COUNT', '/validation/witnessTraces', null, 'When provided, witnesses must include at least two paths.');
  for (const [index, witness] of scenario.validation.witnessTraces.entries()) {
    let state = createInitialState(scenario, { sessionId: 'validation', scenarioVersionId: 'validation-v1' });
    for (const [turn, action] of witness.actions.entries()) {
      const result = transition(scenario, state, { expectedRevision: state.revision, requestId: `witness-${turn}`, action });
      if (!result.ok) { for (const error of result.errors) add(error.code, `/validation/witnessTraces/${index}/actions/${turn}${error.path}`, error.ref, error.message); break; }
      state = result.state;
    }
    if (state.outcome?.family !== 'MUTUAL_GAIN' && state.outcome?.family !== 'ACCEPTABLE_PARTIAL') add('WITNESS_NOT_RATIONAL_AGREEMENT', `/validation/witnessTraces/${index}`, witness.id, 'Witness must reach a mutually rational agreement through the same engine.');
    if (state.outcome?.family === 'MUTUAL_GAIN') targetWitness = true;
  }
  if (witnessKeys.length && !targetWitness) add('WITNESS_TARGET_UNREACHED', '/validation/witnessTraces', null, 'At least one witness must reach the player target.');
  return errors.length ? { valid: false, errors, coverage } : { valid: true, scenario, errors: [], coverage };
}
export function projectValidationForPlayer(result: ScenarioValidation): { available: boolean; reasonCode: 'SCENARIO_UNAVAILABLE' | null } {
  return result.valid ? { available: true, reasonCode: null } : { available: false, reasonCode: 'SCENARIO_UNAVAILABLE' };
}
