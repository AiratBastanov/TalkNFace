import { z } from 'zod';
import { CanonicalActionSchema } from './action.ts';
import { IdSchema, TermSchema } from './common.ts';
import { ResourceIdSchema } from './g2.ts';

export const INTERPRETATION_SCHEMA_VERSION = 1;
export const SpanSchema = z.strictObject({ start: z.int().min(0).max(1999), end: z.int().min(1).max(2000) });
export const PlayerMoveInterpretationSchema = z.strictObject({
  schemaVersion: z.literal(INTERPRETATION_SCHEMA_VERSION),
  intent: z.enum(['ask_question', 'probe_interest', 'argument', 'offer', 'concession', 'counter_offer',
    'pressure', 'empathy', 'objection', 'clarification', 'reveal_information', 'close_attempt', 'walk_away']),
  tone: z.enum(['neutral', 'respectful_firm', 'accusatory', 'threat']),
  primaryTopicId: IdSchema.nullable(), secondaryTopicId: IdSchema.nullable(),
  factIds: z.array(IdSchema).max(2),
  argument: z.strictObject({ claimId: IdSchema, supportingFactIds: z.array(IdSchema).min(1).max(2), evidenceSpan: SpanSchema }).nullable(),
  acknowledgementFactId: IdSchema.nullable(),
  // Empty/partial packages are drafts only; semantic validation requires clarification.
  offerDraft: z.strictObject({ terms: z.array(TermSchema).max(4), conditionalOn: z.array(TermSchema).min(1).max(2).nullable() }).nullable(),
  targetOfferId: z.string().min(1).max(160).nullable(),
  evidenceSpans: z.array(SpanSchema).min(1).max(4),
  needsClarification: z.boolean(), clarification: z.string().min(1).max(240).nullable(),
});
export type PlayerMoveInterpretation = z.infer<typeof PlayerMoveInterpretationSchema>;
export const InterpretRequestSchema = z.strictObject({
  text: z.string().min(1).max(2000).refine(text => text.trim().length > 0),
  expectedRevision: z.int().min(0).max(8), requestId: ResourceIdSchema,
});
export type InterpretRequest = z.infer<typeof InterpretRequestSchema>;
export const UsageSchema = z.strictObject({ inputTokens: z.int().min(0), outputTokens: z.int().min(0), reasoningTokens: z.int().min(0) });
export const InterpretationMetadataSchema = z.strictObject({
  provider: z.enum(['openai', 'fake', 'none']), model: z.enum(['gpt-6-astra', 'fake', 'none']),
  promptVersion: z.string().max(64), promptHash: z.string().regex(/^[a-f0-9]{64}$/), schemaVersion: z.literal(1),
  latencyMs: z.int().min(0), attempts: z.int().min(0).max(2), usage: UsageSchema.nullable(),
});
export const AIStatusSchema = z.strictObject({
  mode: z.enum(['AI_INTERPRETATION', 'GUIDED']),
  availability: z.enum(['ready', 'unverified', 'not_configured', 'cooldown', 'budget_exhausted']),
});
export const InterpretResponseSchema = z.strictObject({
  requestId: ResourceIdSchema, expectedRevision: z.int().min(0).max(8),
  status: z.enum(['draft', 'clarification', 'unavailable']),
  interpretation: PlayerMoveInterpretationSchema.nullable(), action: CanonicalActionSchema.nullable(),
  summary: z.string().max(6000).nullable(), confirmationRequired: z.boolean(),
  message: z.string().min(1).max(240),
  failureCode: z.enum(['NOT_CONFIGURED', 'TIMEOUT', 'CANCELLED', 'NETWORK', 'RATE_LIMITED', 'PROVIDER_ERROR',
    'PROVIDER_ACCESS', 'REFUSAL', 'INCOMPLETE', 'INVALID_OUTPUT', 'INVALID_SEMANTICS', 'BUSY', 'COOLDOWN', 'BUDGET_EXHAUSTED']).nullable(),
  metadata: InterpretationMetadataSchema,
});
export type InterpretResponse = z.infer<typeof InterpretResponseSchema>;
export type AIStatus = z.infer<typeof AIStatusSchema>;
export type AIFailureCode = NonNullable<InterpretResponse['failureCode']>;
