import type { Package, Participant, Party, ScenarioDefinition } from '@arena/contracts';
import { required, valueOf } from './enumerate.ts';

export function participant(scenario: ScenarioDefinition, party: Party): Participant {
  return required(scenario.participants.find(item => item.party === party), `missing participant ${party}`);
}
export function evaluateUtility(scenario: ScenarioDefinition, party: Party, terms: Package): number {
  const model = participant(scenario, party).utility;
  let total = model.base;
  for (const table of model.unary) total += required(table.cells.find(cell => cell.valueId === valueOf(terms, table.issueId)), 'missing unary cell').utility;
  for (const table of model.pairs) total += required(table.cells.find(cell => cell.valueIds[0] === valueOf(terms, table.issueIds[0]) && cell.valueIds[1] === valueOf(terms, table.issueIds[1])), 'missing pair cell').utility;
  if (!Number.isSafeInteger(total)) throw new Error('Unsafe simulation utility');
  return total;
}
