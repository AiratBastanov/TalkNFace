import type { Offer, Outcome, ScenarioDefinition, TerminalReason } from '@arena/contracts';
import { evaluateUtility, participant } from './utility.ts';
import { evaluateAuthority } from './authority.ts';
import { evaluateConstraints } from './constraints.ts';

export function classifyOutcome(scenario: ScenarioDefinition, terminalReason: TerminalReason, agreement: Offer | null): Outcome {
  const player = participant(scenario, 'player');
  const opponent = participant(scenario, 'opponent');
  if (terminalReason === 'agreed' && agreement === null) throw new Error('Agreement requires a package');
  if (terminalReason !== 'agreed' && agreement !== null) throw new Error('No-deal outcome cannot carry an agreement');
  if (agreement && (!evaluateConstraints(scenario, agreement.terms).feasible || !evaluateAuthority(scenario, 'player', agreement.terms, 'accept').feasible || !evaluateAuthority(scenario, 'opponent', agreement.terms, 'accept').feasible)) throw new Error('Agreement violates absolute feasibility or authority');
  const playerUtility = agreement ? evaluateUtility(scenario, 'player', agreement.terms) : null;
  const opponentUtility = agreement ? evaluateUtility(scenario, 'opponent', agreement.terms) : null;
  if (opponentUtility !== null && opponentUtility < opponent.reservation) throw new Error('Agreement below opponent reservation');
  const family = playerUtility === null ? 'NO_AGREEMENT' : playerUtility < player.reservation ? 'POOR_AGREEMENT' : playerUtility >= player.target ? 'MUTUAL_GAIN' : 'ACCEPTABLE_PARTIAL';
  return { family, terminalReason, offerId: agreement?.id ?? null, playerUtility, opponentUtility, playerBatna: player.batna.utility, opponentBatna: opponent.batna.utility, playerTarget: player.target };
}
