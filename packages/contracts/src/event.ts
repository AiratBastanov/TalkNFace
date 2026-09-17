import { z } from 'zod';
import { GeneratedIdSchema, IdSchema, PackageSchema, PartySchema, UtilitySchema } from './common.ts';
import { CanonicalActionSchema } from './action.ts';
import { OutcomeSchema } from './outcome.ts';

export const OfferSchema = z.strictObject({
  id: GeneratedIdSchema, proposer: PartySchema, terms: PackageSchema, turnNumber: z.int().min(1).max(8), supersedesId: GeneratedIdSchema.nullable(),
});
const rejected = { offerId: GeneratedIdSchema, ruleIds: z.array(IdSchema).max(12), reasonCodes: z.array(IdSchema).max(12) };
export const EventPayloadSchema = z.discriminatedUnion('type', [
  z.strictObject({ type: z.literal('action_played'), requestId: IdSchema, action: CanonicalActionSchema }),
  z.strictObject({ type: z.literal('topic_asked'), topicId: IdSchema, first: z.boolean() }),
  z.strictObject({ type: z.literal('fact_disclosed'), factId: IdSchema, via: z.enum(['question', 'constraint_explanation', 'opponent_commitment']) }),
  z.strictObject({ type: z.literal('fact_acknowledged'), factId: IdSchema, first: z.boolean() }),
  z.strictObject({ type: z.literal('grounded_argument_applied'), argumentId: IdSchema, first: z.boolean() }),
  z.strictObject({ type: z.literal('damaging_tone'), effect: z.enum(['accusation', 'threat', 'contradiction']) }),
  z.strictObject({ type: z.literal('social_state_changed'), trustBefore: z.int().min(0).max(100), trustAfter: z.int().min(0).max(100), tensionBefore: z.int().min(0).max(100), tensionAfter: z.int().min(0).max(100) }),
  z.strictObject({ type: z.literal('tension_warning') }),
  z.strictObject({ type: z.literal('tension_repaired'), factId: IdSchema }),
  z.strictObject({ type: z.literal('progress_credit_earned'), key: GeneratedIdSchema, total: z.int().min(1).max(5) }),
  z.strictObject({ type: z.literal('resource_authorized'), resourceId: IdSchema }),
  z.strictObject({ type: z.literal('offer_proposed'), offer: OfferSchema }),
  z.strictObject({ type: z.literal('offer_rejected_physical'), ...rejected }),
  z.strictObject({ type: z.literal('offer_rejected_authority'), ...rejected }),
  z.strictObject({ type: z.literal('offer_rejected_aspiration'), offerId: GeneratedIdSchema, utility: UtilitySchema, aspiration: z.int().min(-100).max(220) }),
  z.strictObject({ type: z.literal('counteroffer_created'), offer: OfferSchema }),
  z.strictObject({ type: z.literal('counteroffer_unavailable'), reasonCode: z.literal('NO_ACCEPTABLE_CANDIDATE') }),
  z.strictObject({ type: z.literal('offer_closed'), offerId: GeneratedIdSchema, reason: z.enum(['replaced', 'accepted', 'session_terminated']) }),
  z.strictObject({ type: z.literal('active_offer_accepted'), offerId: GeneratedIdSchema }),
  z.strictObject({ type: z.literal('agreement_reached'), outcome: OutcomeSchema }),
  z.strictObject({ type: z.literal('player_walkaway') }),
  z.strictObject({ type: z.literal('opponent_walkaway') }),
  z.strictObject({ type: z.literal('round_limit') }),
]);
export const DomainEventSchema = z.strictObject({
  id: GeneratedIdSchema, sequence: z.int().min(1).max(512), turnNumber: z.int().min(1).max(8), payload: EventPayloadSchema,
});
export type Offer = z.infer<typeof OfferSchema>;
export type EventPayload = z.infer<typeof EventPayloadSchema>;
export type DomainEvent = z.infer<typeof DomainEventSchema>;
