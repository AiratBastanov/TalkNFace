import { z } from 'zod';
import { IdSchema, IntegerSchema, LabelSchema, PartySchema, PredicateSchema, TermSchema, TextSchema, UtilitySchema } from './common.ts';
import { CanonicalActionSchema } from './action.ts';

export const IssueSchema = z.strictObject({
  id: IdSchema, label: LabelSchema, unit: LabelSchema, ordered: z.boolean(),
  values: z.array(z.strictObject({ id: IdSchema, label: LabelSchema, quantity: IntegerSchema.nullable() })).min(2).max(6),
});
// Bounds apply to final utility, not each signed contribution (e.g. a price cost of −115).
const contribution = z.int().min(-10000).max(10000);
const unary = z.strictObject({ issueId: IdSchema, cells: z.array(z.strictObject({ valueId: IdSchema, utility: contribution })).min(2).max(6) });
export const UtilityModelSchema = z.strictObject({
  base: contribution,
  unary: z.array(unary).min(2).max(4),
  pairs: z.array(z.strictObject({
    issueIds: z.tuple([IdSchema, IdSchema]),
    cells: z.array(z.strictObject({ valueIds: z.tuple([IdSchema, IdSchema]), utility: contribution })).min(4).max(36),
  })).max(2),
});
const explained = { id: IdSchema, reasonCode: IdSchema, explanationFactId: IdSchema };
export const ConstraintSchema = z.discriminatedUnion('kind', [
  z.strictObject({ ...explained, kind: z.literal('allowed_values'), issueId: IdSchema, valueIds: z.array(IdSchema).min(1).max(6) }),
  z.strictObject({ ...explained, kind: z.literal('forbid_combination'), terms: z.array(TermSchema).min(1).max(4) }),
  z.strictObject({ ...explained, kind: z.literal('linear_lte'), bound: z.int().min(-10000).max(10000),
    contributions: z.array(z.strictObject({ issueId: IdSchema,
      cells: z.array(z.strictObject({ valueId: IdSchema, amount: z.int().min(-10000).max(10000) })).min(2).max(6),
    })).min(1).max(4),
  }),
]);
export const AuthoritySchema = z.strictObject({
  allowedValues: z.array(z.strictObject({ ...explained, issueId: IdSchema, valueIds: z.array(IdSchema).min(1).max(6) })).max(4),
  resources: z.array(z.strictObject({
    ...explained, requiredWhen: PredicateSchema, grantWhen: PredicateSchema, proposalRequiresAuthorization: z.boolean(),
  })).max(4),
});
export const ParticipantSchema = z.strictObject({
  id: IdSchema, party: PartySchema, label: LabelSchema, roleId: IdSchema, privateBrief: TextSchema, initialPosition: TextSchema,
  goals: z.array(z.strictObject({ id: IdSchema, text: TextSchema, issueIds: z.array(IdSchema).min(1).max(4) })).min(1).max(3),
  interests: z.array(z.strictObject({ id: IdSchema, text: TextSchema, issueIds: z.array(IdSchema).min(1).max(4), visibility: z.enum(['public', 'hidden']) })).min(1).max(3),
  target: UtilitySchema, reservation: UtilitySchema,
  batna: z.strictObject({ description: TextSchema, utility: UtilitySchema }),
  utility: UtilityModelSchema, authority: AuthoritySchema,
});
export const DisclosureRuleSchema = z.discriminatedUnion('kind', [
  z.strictObject({ kind: z.literal('question'), topicId: IdSchema, gate: z.enum(['trust', 'always']) }),
  z.strictObject({ kind: z.literal('opponent_commitment_contains'), condition: PredicateSchema }),
  z.strictObject({ kind: z.literal('constraint_explanation'), constraintId: IdSchema }),
]);
export const FactSchema = z.strictObject({
  id: IdSchema, ownerId: IdSchema, text: TextSchema, visibility: z.enum(['public', 'hidden']),
  kind: z.enum(['interest', 'constraint', 'resource', 'authority', 'context']),
  topicId: IdSchema, interestId: IdSchema.nullable(), issueIds: z.array(IdSchema).min(1).max(4), relatedFactIds: z.array(IdSchema).max(6),
  disclosure: z.array(DisclosureRuleSchema).max(4),
});
export const ArgumentSchema = z.strictObject({
  id: IdSchema, label: LabelSchema, factIds: z.array(IdSchema).min(1).max(2), interestId: IdSchema.nullable(), condition: PredicateSchema,
});
export const ScenarioDefinitionSchema = z.strictObject({
  schemaVersion: z.literal(1), templateId: IdSchema.nullable(), title: LabelSchema, sphere: LabelSchema, topic: LabelSchema,
  provenance: z.enum(['reference', 'ai_generated']), configFingerprint: IdSchema,
  publicBrief: TextSchema, participants: z.tuple([ParticipantSchema, ParticipantSchema]),
  issues: z.array(IssueSchema).min(2).max(4), constraints: z.array(ConstraintSchema).max(8), facts: z.array(FactSchema).min(2).max(24),
  topics: z.array(z.strictObject({ id: IdSchema, label: LabelSchema, issueIds: z.array(IdSchema).min(1).max(4) })).min(2).max(6),
  arguments: z.array(ArgumentSchema).min(2).max(6),
  acknowledgementTargets: z.array(z.strictObject({ factId: IdSchema, countsAsConstraint: z.boolean() })).max(24),
  policy: z.strictObject({ difficulty: z.enum(['beginner', 'normal', 'advanced']), tone: z.enum(['neutral', 'friendly', 'skeptical']),
    maxTurns: z.literal(8), policyVersion: z.literal('training-policy-v1') }),
  evaluation: z.strictObject({ rubricVersion: IdSchema, goalIds: z.array(IdSchema).max(6), interestIds: z.array(IdSchema).max(6), constraintIds: z.array(IdSchema).max(8) }),
  validation: z.strictObject({ witnessTraces: z.array(z.strictObject({ id: IdSchema, actions: z.array(CanonicalActionSchema).min(1).max(8) })).max(3) }),
});
export type ScenarioDefinition = z.infer<typeof ScenarioDefinitionSchema>;
export type Issue = z.infer<typeof IssueSchema>;
export type Participant = z.infer<typeof ParticipantSchema>;
export type Constraint = z.infer<typeof ConstraintSchema>;
export type Fact = z.infer<typeof FactSchema>;
export type ArgumentBinding = z.infer<typeof ArgumentSchema>;
