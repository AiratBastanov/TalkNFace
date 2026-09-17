import { z } from 'zod';
import { EvidenceRefSchema, GeneratedIdSchema, IdSchema, PackageSchema, TermSchema } from './common.ts';

const social = {
  tone: z.enum(['neutral', 'respectful_firm', 'accusatory', 'threat']),
  acknowledgementFactId: IdSchema.nullable(),
  argumentId: IdSchema.nullable(),
  contradictsFactId: IdSchema.nullable(),
  evidenceRefs: z.array(EvidenceRefSchema).max(4),
};
export const CanonicalActionSchema = z.discriminatedUnion('kind', [
  z.strictObject({ ...social, kind: z.literal('question'), primaryTopicId: IdSchema, secondaryTopicId: IdSchema.nullable() }),
  z.strictObject({ ...social, kind: z.literal('acknowledge'), acknowledgementFactId: IdSchema }),
  z.strictObject({ ...social, kind: z.literal('argument'), argumentId: IdSchema }),
  z.strictObject({ ...social, kind: z.literal('offer'), terms: PackageSchema, conditionalOn: z.array(TermSchema).max(2) }),
  z.strictObject({ ...social, kind: z.literal('counter_offer'), terms: PackageSchema, conditionalOn: z.array(TermSchema).max(2), targetOfferId: GeneratedIdSchema }),
  z.strictObject({ ...social, kind: z.literal('accept'), offerId: GeneratedIdSchema }),
  z.strictObject({ ...social, kind: z.literal('pressure') }),
  z.strictObject({ ...social, kind: z.literal('walk_away') }),
  // A clarification without a new factual binding has no invented economic reward.
  z.strictObject({ ...social, kind: z.literal('clarification') }),
]);
export const CommandSchema = z.strictObject({
  requestId: IdSchema, expectedRevision: z.int().min(0), action: CanonicalActionSchema,
});
export type CanonicalAction = z.infer<typeof CanonicalActionSchema>;
export type Command = z.infer<typeof CommandSchema>;
