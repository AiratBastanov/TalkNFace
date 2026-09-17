import { z } from 'zod';
import { IdSchema, LabelSchema, TextSchema, UtilitySchema } from './common.ts';
import { IssueSchema } from './scenario.ts';
import { OfferSchema } from './event.ts';
import { PhaseSchema } from './session.ts';
import { OutcomeFamilySchema, TerminalReasonSchema } from './outcome.ts';

export const PublicScenarioSchema = z.strictObject({
  title: LabelSchema, sphere: LabelSchema, topic: LabelSchema, publicBrief: TextSchema,
  player: z.strictObject({ id: IdSchema, label: LabelSchema, roleId: IdSchema, privateBrief: TextSchema, initialPosition: TextSchema,
    goals: z.array(z.strictObject({ id: IdSchema, text: TextSchema })).min(1).max(3),
    target: UtilitySchema, reservation: UtilitySchema, batna: z.strictObject({ description: TextSchema, utility: UtilitySchema }) }),
  opponent: z.strictObject({ label: LabelSchema, roleId: IdSchema, initialPosition: TextSchema }),
  issues: z.array(IssueSchema).min(2).max(4), topics: z.array(z.strictObject({ id: IdSchema, label: LabelSchema })).min(2).max(6),
});
export const PublicProjectionSchema = z.strictObject({
  sessionId: IdSchema, revision: z.int().min(0).max(8), phase: PhaseSchema, turnNumber: z.int().min(0).max(8), maxTurns: z.literal(8),
  scenario: PublicScenarioSchema, knownFacts: z.array(z.strictObject({ id: IdSchema, text: TextSchema })).max(24),
  availableArguments: z.array(z.strictObject({ id: IdSchema, label: LabelSchema })).max(6),
  acknowledgementFactIds: z.array(IdSchema).max(24), activeOffer: OfferSchema.nullable(), lastUserOffer: OfferSchema.nullable(), agreementOffer: OfferSchema.nullable(),
  stance: z.enum(['calm', 'strained', 'warning', 'closed']),
  outcome: z.strictObject({ family: OutcomeFamilySchema, terminalReason: TerminalReasonSchema, playerUtility: UtilitySchema.nullable(), playerBatna: UtilitySchema, playerTarget: UtilitySchema }).nullable(),
});
export type PublicProjection = z.infer<typeof PublicProjectionSchema>;
