import { z } from 'zod';
import { GeneratedIdSchema, UtilitySchema } from './common.ts';

export const TerminalReasonSchema = z.enum(['agreed', 'player_walkaway', 'opponent_walkaway', 'round_limit']);
export const OutcomeFamilySchema = z.enum(['MUTUAL_GAIN', 'ACCEPTABLE_PARTIAL', 'POOR_AGREEMENT', 'NO_AGREEMENT']);
export const OutcomeSchema = z.strictObject({
  family: OutcomeFamilySchema, terminalReason: TerminalReasonSchema, offerId: GeneratedIdSchema.nullable(),
  playerUtility: UtilitySchema.nullable(), opponentUtility: UtilitySchema.nullable(),
  playerBatna: UtilitySchema, opponentBatna: UtilitySchema, playerTarget: UtilitySchema,
});
export type TerminalReason = z.infer<typeof TerminalReasonSchema>;
export type Outcome = z.infer<typeof OutcomeSchema>;
