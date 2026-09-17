import { z } from 'zod';
import { GeneratedIdSchema, IdSchema } from './common.ts';
import { DomainEventSchema, OfferSchema } from './event.ts';
import { OutcomeSchema, TerminalReasonSchema } from './outcome.ts';

export const PhaseSchema = z.enum(['briefing', 'exploring', 'bargaining', 'agreed', 'player_walkaway', 'opponent_walkaway', 'round_limit']);
export const SessionIdentitySchema = z.strictObject({ sessionId: IdSchema, scenarioVersionId: IdSchema });
export const NegotiationStateSchema = z.strictObject({
  ...SessionIdentitySchema.shape, configHash: IdSchema, engineVersion: z.literal('deterministic-core-v1'), rubricVersion: IdSchema,
  revision: z.int().min(0).max(8), phase: PhaseSchema, turnNumber: z.int().min(0).max(8), maxTurns: z.literal(8),
  trust: z.int().min(0).max(100), tension: z.int().min(0).max(100), warning: z.boolean(),
  knownFactIds: z.array(IdSchema).max(24), earnedEventKeys: z.array(GeneratedIdSchema).max(128), progressCredits: z.int().min(0).max(5),
  groundedArgumentIds: z.array(IdSchema).max(6), resourceAuthorizations: z.array(IdSchema).max(8),
  activeOffer: OfferSchema.nullable(), lastUserOffer: OfferSchema.nullable(), agreementOffer: OfferSchema.nullable(),
  terminalReason: TerminalReasonSchema.nullable(), outcome: OutcomeSchema.nullable(), events: z.array(DomainEventSchema).max(512),
});
export type NegotiationState = z.infer<typeof NegotiationStateSchema>;
export type SessionIdentity = z.infer<typeof SessionIdentitySchema>;
