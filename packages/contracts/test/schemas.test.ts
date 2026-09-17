import { expect, it } from 'vitest';
import { z } from 'zod';
import { CanonicalActionSchema, CommandSchema, DomainEventSchema, NegotiationStateSchema, OutcomeSchema, PublicProjectionSchema, ScenarioDefinitionSchema } from '../src/index.ts';
import { S1, question } from '../../scenarios/src/index.ts';

it('domain schemas export to JSON Schema without executable conversions', () => {
  for (const schema of [ScenarioDefinitionSchema, CanonicalActionSchema, CommandSchema, DomainEventSchema, NegotiationStateSchema, OutcomeSchema, PublicProjectionSchema]) {
    const json = z.toJSONSchema(schema);
    expect(JSON.stringify(json)).toContain('additionalProperties');
  }
  expect(z.toJSONSchema(ScenarioDefinitionSchema).additionalProperties).toBe(false);
});
it('schema round trip preserves every explicit data field and rejects unknown nested properties', () => {
  const data: unknown = JSON.parse(JSON.stringify(S1));
  expect(ScenarioDefinitionSchema.parse(data)).toEqual(S1);
  expect(CanonicalActionSchema.safeParse({ ...question('logistics'), prompt: 'out of scope' }).success).toBe(false);
  const altered = structuredClone(S1);
  Object.assign(altered.issues[0]!.values[0]!, { expression: 'return 1;' });
  expect(ScenarioDefinitionSchema.safeParse(altered).success).toBe(false);
});
