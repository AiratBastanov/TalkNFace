import { z } from 'zod';
import { CanonicalActionSchema } from './action.ts';
import { BasicResultSchema, ResourceIdSchema } from './g2.ts';

// Additive application contract. No domain, G2/G3 or training-imported changes.
const digest = z.string().regex(/^[a-f0-9]{64}$/);
const revision = z.int().min(0).max(8);
export const PreparationInputSchema = z.strictObject({
  expectedRevision: z.literal(0), goal: z.enum(['target', 'batna']),
  ownBoundary: z.number().finite(), acknowledgedAlternative: z.literal(true),
});
export const PreparationSchema = PreparationInputSchema.omit({ expectedRevision: true }).extend({
  sessionId: ResourceIdSchema, scenarioVersionId: ResourceIdSchema, version: z.literal('preparation-v1'),
  recordedRevision: z.literal(0), selectedThreshold: z.number().finite(),
});
export const PreparationViewSchema = z.strictObject({ record: PreparationSchema.nullable() });
export type Preparation = z.infer<typeof PreparationSchema>;
export const FeedbackQuerySchema = z.strictObject({ revision: z.coerce.number().int().min(1).max(8) });
export const ComparisonQuerySchema = FeedbackQuerySchema.extend({ predecessorId: ResourceIdSchema });
export const CheckStatusSchema = z.enum(['passed', 'failed', 'not_applicable', 'unobservable']);
export const EvidenceSchema = z.strictObject({
  id: z.string(), sessionId: ResourceIdSchema, scenarioVersionId: ResourceIdSchema, terminalRevision: revision,
  turnNumber: revision, requestId: ResourceIdSchema.nullable(), eventId: z.string().nullable(),
  kind: z.enum(['guided_action', 'structured_event', 'window', 'preparation']), description: z.string(),
  quote: z.strictObject({ speaker: z.enum(['player', 'opponent']), text: z.string(), start: z.int().min(0), end: z.int().min(0) }).nullable(),
  window: z.strictObject({ from: revision, to: revision }).nullable(),
});
export type FeedbackEvidence = z.infer<typeof EvidenceSchema>;
export const CheckSchema = z.strictObject({
  id: z.string(), label: z.string(), status: CheckStatusSchema,
  applicability: z.enum(['applicable', 'inapplicable', 'unknown']),
  evidenceSufficiency: z.enum(['sufficient', 'missing']), explanation: z.string(), evidenceIds: z.array(z.string()).min(1),
});
export type FeedbackCheck = z.infer<typeof CheckSchema>;
const DimensionSchema = z.strictObject({
  id: z.string(), label: z.string(), weight: z.number(), applicable: z.int(), passed: z.int(),
  score: z.number().min(0).max(100).nullable(), checks: z.array(CheckSchema).length(2),
});
export const SuggestionSchema = z.strictObject({
  checkId: z.string(), evidenceIds: z.array(z.string()).min(1), focus: z.string(),
  proposedWording: z.string(), action: CanonicalActionSchema.nullable(), priorRevision: revision,
  validation: z.enum(['prior_state', 'next_preparation']), disclaimer: z.string(),
});
export const FeedbackReportSchema = z.strictObject({
  sessionId: ResourceIdSchema, scenarioVersionId: ResourceIdSchema, terminalRevision: revision,
  configHash: z.string(), definitionHash: digest, scenarioRubricVersion: z.string(),
  rubricVersion: z.string(), evaluatorVersion: z.string(), evidenceDigest: digest,
  computation: z.literal('derived_on_read'), mode: z.literal('saved_guided_actions'),
  outcome: BasicResultSchema, preparation: PreparationSchema.nullable(),
  dimensions: z.array(DimensionSchema).length(6), evidence: z.array(EvidenceSchema),
  overall: z.strictObject({
    score: z.number().min(0).max(100).nullable(), applicableChecks: z.int(), progressCredits: z.int(),
    missingChecks: z.array(z.string()), progressEvidenceIds: z.array(z.string()), explanation: z.string(),
  }), suggestions: z.array(SuggestionSchema).max(1),
});
export type FeedbackReport = z.infer<typeof FeedbackReportSchema>;
export const ComparisonSchema = z.strictObject({
  comparable: z.boolean(), reason: z.string(), currentSessionId: ResourceIdSchema, predecessorSessionId: ResourceIdSchema,
  currentRevision: revision, predecessorRevision: revision,
  currentOutcome: BasicResultSchema, predecessorOutcome: BasicResultSchema,
  sharedChecks: z.array(z.strictObject({ id: z.string(), label: z.string(), before: CheckStatusSchema, after: CheckStatusSchema })),
  excludedChecks: z.array(z.string()),
});
export type FeedbackComparison = z.infer<typeof ComparisonSchema>;
