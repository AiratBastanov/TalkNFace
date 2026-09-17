import { z } from 'zod';
import { CommandSchema } from './action.ts';
import { GeneratedIdSchema, IdSchema, TextSchema, UtilitySchema } from './common.ts';
import { PublicProjectionSchema, PublicScenarioSchema } from './projection.ts';
import { OfferSchema } from './event.ts';
import { OutcomeFamilySchema, TerminalReasonSchema } from './outcome.ts';

// G2 HTTP contracts extend, rather than change, the frozen G1 domain contracts.
export const ResourceIdSchema = z.uuid();
export const SessionParamsSchema = z.strictObject({ sessionId: ResourceIdSchema });
export const EmptyBodySchema = z.strictObject({});
export const CreateSessionSchema = z.strictObject({ scenarioVersionId: ResourceIdSchema });
export const PlayTurnSchema = CommandSchema.extend({ requestId: ResourceIdSchema });
export const ApiErrorSchema = z.strictObject({
  code: z.enum(['INVALID_REQUEST', 'NOT_FOUND', 'STALE_REVISION', 'IDEMPOTENCY_CONFLICT',
    'DOMAIN_REJECTED', 'SESSION_TERMINAL', 'SESSION_NOT_TERMINAL', 'CORRUPT_STATE', 'INTERNAL_ERROR']),
  message: z.string().min(1).max(500), currentRevision: z.int().min(0).max(8).optional(),
});
export type ApiErrorBody = z.infer<typeof ApiErrorSchema>;
export type PlayTurnRequest = z.infer<typeof PlayTurnSchema>;

export const ReferencePreviewSchema = z.strictObject({
  templateId: z.literal('S1-SUPPLY-LAUNCH'), scenario: PublicScenarioSchema,
  difficulty: z.enum(['beginner', 'normal', 'advanced']), tone: z.enum(['neutral', 'friendly', 'skeptical']),
  maxTurns: z.literal(8), publicFacts: PublicProjectionSchema.shape.knownFacts,
});
export const PublishedScenarioSchema = z.strictObject({
  id: ResourceIdSchema, definitionHash: z.string().regex(/^[a-f0-9]{64}$/),
  schemaVersion: z.literal(1), engineVersion: z.literal('deterministic-core-v1'), rubricVersion: IdSchema,
  configFingerprint: IdSchema, createdAt: z.iso.datetime(), publishedAt: z.iso.datetime(), preview: ReferencePreviewSchema,
});
export const ReferenceListSchema = z.array(ReferencePreviewSchema).max(1);
export const ScenarioListSchema = z.array(PublishedScenarioSchema);
export type ReferencePreview = z.infer<typeof ReferencePreviewSchema>;
export type PublishedScenario = z.infer<typeof PublishedScenarioSchema>;

export const ObservationSchema = z.strictObject({
  eventId: GeneratedIdSchema, turnNumber: z.int().min(1).max(8),
  ruleId: z.enum(['FACT_DISCLOSED', 'FACT_ACKNOWLEDGED', 'GROUNDED_ARGUMENT', 'REPEATED_QUESTION',
    'DAMAGING_TONE', 'PHYSICAL_REJECTION', 'AUTHORITY_REJECTION', 'POSITION_REJECTION', 'COUNTEROFFER',
    'TENSION_WARNING', 'TENSION_REPAIRED', 'AGREEMENT', 'BELOW_OWN_BATNA',
    'PLAYER_WALKAWAY', 'OPPONENT_WALKAWAY', 'ROUND_LIMIT']),
  text: TextSchema,
});
export const PublicTurnSchema = z.strictObject({
  turnNumber: z.int().min(1).max(8), requestId: ResourceIdSchema,
  playerText: z.string().min(1).max(6000), opponentText: z.string().min(1).max(6000),
  observations: z.array(ObservationSchema).max(64),
});
export const BasicResultSchema = z.strictObject({
  family: OutcomeFamilySchema, terminalReason: TerminalReasonSchema, headline: TextSchema,
  terminalExplanation: TextSchema, goals: z.array(TextSchema).min(1).max(3),
  targetReached: z.boolean(), batnaComparison: z.enum(['above', 'equal', 'below', 'not_exercised']),
  playerUtility: UtilitySchema.nullable(), playerBatna: UtilitySchema, playerTarget: UtilitySchema,
  agreementOffer: OfferSchema.nullable(), observations: z.array(ObservationSchema).max(512),
});
export const GuidedActionsSchema = z.strictObject({
  kinds: z.array(z.enum(['question', 'acknowledge', 'argument', 'offer', 'accept', 'pressure', 'walk_away'])).max(7),
  questionTones: z.array(z.enum(['neutral', 'respectful_firm', 'accusatory'])).max(3),
  pressureTones: z.array(z.enum(['respectful_firm', 'accusatory', 'threat'])).max(3),
});
export const SessionViewSchema = z.strictObject({
  mode: z.literal('DEMO_FALLBACK'), scenarioVersionId: ResourceIdSchema, replayOf: ResourceIdSchema.nullable(),
  projection: PublicProjectionSchema, actions: GuidedActionsSchema,
  transcript: z.array(PublicTurnSchema).max(8), result: BasicResultSchema.nullable(),
});
export type Observation = z.infer<typeof ObservationSchema>;
export type PublicTurn = z.infer<typeof PublicTurnSchema>;
export type BasicResult = z.infer<typeof BasicResultSchema>;
export type GuidedActions = z.infer<typeof GuidedActionsSchema>;
export type SessionView = z.infer<typeof SessionViewSchema>;
