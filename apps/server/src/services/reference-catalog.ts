import type { ScenarioDefinition } from '@arena/contracts';
import { S1, S2 } from '@arena/scenarios';
import { ApiError } from '../api-error.ts';

const references: Readonly<Record<string, ScenarioDefinition>> = Object.freeze({ s1: S1, s2: S2 });
export function referenceDefinition(key: string): ScenarioDefinition {
  if (!Object.hasOwn(references, key)) throw new ApiError(404, 'NOT_FOUND', 'Эталонный сценарий не найден.');
  return references[key]!;
}
export const referenceDefinitions = () => Object.values(references);
