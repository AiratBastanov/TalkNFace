// Evaluation-only materialization. Never import this module into training or the app.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { z } from 'zod';
import { PlayerMoveInterpretationSchema } from '../../packages/contracts/src/g3.ts';
import { S1 } from '../../packages/scenarios/src/s1-supply-launch.ts';
import { S2 } from '../../packages/scenarios/src/s2-workload-urgent.ts';

const out = new URL('../../evals/local-qwen/', import.meta.url);
mkdirSync(out, { recursive: true });
const sourcePath = 'docs/02_MASTER_IMPLEMENTATION_PLAN.md';
const source = readFileSync(sourcePath, 'utf8');
const rows = source.split('\n').filter(line => /^\| A(?:0[1-9]|1[0-6]) \|/.test(line));
if (rows.length !== 16) throw new Error('Expected exactly the frozen A01–A16 rows');
const term = (issueId, valueId) => ({ issueId, valueId });
const supply = (p, d, a) => [term('PRICE', p), term('DELIVERY', d), term('PREPAY', a)];
const activeId = 'eval-s1-opponent-offer-r2';
const defaults = {
  schemaVersion: 1, tone: 'neutral', primaryTopicId: null, secondaryTopicId: null,
  factIds: [], argument: null, acknowledgementFactId: null, offerDraft: null,
  targetOfferId: null, needsClarification: false, clarification: null,
};
const labels = [
  { intent: 'ask_question', primaryTopicId: 'logistics' },
  { intent: 'probe_interest', primaryTopicId: 'payment' },
  { intent: 'argument', primaryTopicId: 'payment', factIds: ['cashflow-need'],
    argument: { claimId: 'cashflow-argument', supportingFactIds: ['cashflow-need'], evidenceSpan: '$valid_claim_span' } },
  { intent: 'offer', offerDraft: { terms: supply('95', 'split40at7_rest14', '50'), conditionalOn: null } },
  { intent: 'objection', offerDraft: { terms: [term('PREPAY', '0')], conditionalOn: null },
    needsClarification: true, clarification: '$nonempty_clarification' },
  { intent: 'counter_offer', offerDraft: { terms: supply('105', 'all7', '50'), conditionalOn: null }, targetOfferId: activeId },
  { intent: 'concession', offerDraft: { terms: supply('100', 'split40at7_rest14', '50'), conditionalOn: [term('DELIVERY', 'split40at7_rest14')] } },
  { intent: 'pressure', tone: 'threat' },
  { intent: 'objection', tone: 'respectful_firm' },
  { intent: 'empathy', primaryTopicId: 'capacity-topic', factIds: ['capacity-bound'], acknowledgementFactId: 'capacity-bound' },
  { intent: 'objection', primaryTopicId: 'capacity-topic', secondaryTopicId: 'resources' },
  { intent: 'clarification', primaryTopicId: 'logistics' },
  { intent: 'reveal_information', factIds: ['player-batna'] },
  { intent: 'close_attempt', targetOfferId: activeId },
  { intent: 'walk_away' },
  { intent: 'clarification', needsClarification: true, clarification: '$nonempty_clarification' },
];
const cases = rows.map((row, i) => {
  const [id, condition, authoritativeExpected] = row.split('|').slice(1, 4).map(x => x.trim());
  const text = condition.match(/«(.*?)»/u)?.[1];
  if (!text) throw new Error(`Missing verbatim input: ${id}`);
  const s = ['A10', 'A11'].includes(id) ? S2 : S1;
  const knownFacts = s.facts.filter(f => f.visibility === 'public' || (id === 'A03' && f.id === 'cashflow-need'))
    .map(({ id, text, topicId }) => ({ id, text, topicId }));
  if (id === 'A13') knownFacts.push({ id: 'player-batna', text: S1.participants.find(p => p.party === 'player').privateBrief.split('Альтернатива: ')[1], topicId: null });
  const availableArguments = s.arguments.filter(a => a.factIds.every(f => knownFacts.some(k => k.id === f)))
    .map(a => ({ claimId: a.id, label: a.label, supportingFactIds: a.factIds, condition: a.condition }));
  const publicContext = {
    scenarioId: s.templateId, publicBrief: s.publicBrief,
    issues: s.issues.map(({ id, label, unit, values }) => ({ id, label, unit, values: values.map(({ id, label }) => ({ id, label })) })),
    topics: s.topics, knownFacts,
    acknowledgementFactIds: s.acknowledgementTargets.map(x => x.factId).filter(f => knownFacts.some(k => k.id === f)),
    availableArguments,
    activeOffer: ['A06', 'A14'].includes(id) ? { id: activeId, proposer: 'opponent', terms: supply('110', 'all7', '50') } : null,
  };
  const expected = { ...structuredClone(defaults), ...labels[i], evidenceSpans: '$valid_input_spans' };
  const critical = ['A01', 'A04', 'A05', 'A06', 'A07', 'A09', 'A11', 'A12', 'A13', 'A14', 'A15', 'A16'].includes(id);
  return {
    id, text, source: { path: sourcePath, line: source.split('\n').indexOf(row) + 1, condition, expected: authoritativeExpected },
    publicContext, expected,
    // Unspecified topic details are not new gold labels: permitted alternatives are frozen before inference.
    allowedAlternatives: ['A04', 'A05', 'A06', 'A07', 'A09', 'A13'].includes(id)
      ? { primaryTopicId: [null, ...s.topics.map(t => t.id)], secondaryTopicId: [null, ...s.topics.map(t => t.id)] }
      : id === 'A11' ? { primaryTopicId: ['capacity-topic', 'resources'], secondaryTopicId: [null, 'resources', 'capacity-topic'], factIds: [[], ['capacity-bound']] } : {},
    critical, criticalFields: critical ? ['intent', 'offerDraft', 'targetOfferId', 'needsClarification', ...(id === 'A09' ? ['tone'] : [])] : [],
    ambiguity: id === 'A05', negationSensitive: ['A05', 'A09', 'A11', 'A15'].includes(id),
    confirmationRequiredByFutureApplication: ['A04', 'A06', 'A07', 'A14', 'A15'].includes(id),
  };
});
const artifact = {
  schemaVersion: 1, purpose: 'HOLDOUT_EVAL_ONLY', training_allowed: false,
  sourceSha256: createHash('sha256').update(readFileSync(sourcePath)).digest('hex'),
  provenance: 'Exact Russian utterances and expected semantic constraints from frozen planning rows; public catalogs from unchanged S1/S2. No external dataset material.',
  materializationDecisions: [
    'A05 has no named primary intent in its authoritative row. Objection is fixed before inference because the utterance rejects a price and discusses alternatives; clarification is separately mandatory.',
    'A10/A11 require S2 catalogs. A11 primary resources/capacity-topic are both explicitly consistent with the row; optional capacity fact reference is accepted.',
    'A13 uses the eval-only public fact ID player-batna for the explicitly known player BATNA from S1 buyer briefing. This does not add a scenario fact or expose opponent information.',
    'A14 does not specify active terms/ID. The fixture uses the same concrete current opponent offer as A06: 110/all7/50. Only exact current ID is accepted.',
    'A03 binds cashflow-argument with its supplied PREPAY=50 predicate. The contract has no standalone argument-predicate output field; no extra offer is expected.',
    'Unspecified topics in compound price/package cases allow existing context topic IDs or null; no alternative primary intents are accepted.',
    'FULL_EXPECTED_STRUCTURE_MATCH checks every contract field against this frozen semantic oracle. Term/fact ordering is immaterial; evidence offsets must identify valid input spans and cover the argument claim. Clarification wording is not exact-string gold.',
    'A05 clarification must mention the price or the alternatives 95/100. A16 must safely clarify/refuse with no economic draft. All other cases expect no model clarification request.',
  ], cases,
};
writeFileSync(new URL('a01-a16.json', out), JSON.stringify(artifact, null, 2) + '\n');
writeFileSync(new URL('interpretation.schema.json', out), JSON.stringify(z.toJSONSchema(PlayerMoveInterpretationSchema), null, 2) + '\n');
console.log('Materialized 16 verbatim holdout cases and the existing interpretation schema.');
