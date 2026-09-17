import { z } from 'zod';
import { IdSchema, LabelSchema, PredicateSchema, TextSchema } from '@arena/contracts';
import type { PublicProjection, ScenarioDefinition } from '@arena/contracts';
import { PublicProjectionSchema, PublicScenarioSchema } from '@arena/contracts';

export const InterpretationContextSchema = z.strictObject({
  revision: z.int().min(0).max(8), turnNumber: z.int().min(0).max(8),
  player: z.strictObject({ roleId: IdSchema, label: LabelSchema, briefing: TextSchema }),
  publicBrief: TextSchema, issues: PublicScenarioSchema.shape.issues, topics: PublicScenarioSchema.shape.topics,
  knownFacts: PublicProjectionSchema.shape.knownFacts,
  acknowledgementFactIds: z.array(IdSchema).max(24),
  availableArguments: z.array(z.strictObject({ claimId: IdSchema, label: LabelSchema,
    supportingFactIds: z.array(IdSchema).min(1).max(2), condition: PredicateSchema })).max(6),
  activeOffer: PublicProjectionSchema.shape.activeOffer,
});
export type InterpretationContext = z.infer<typeof InterpretationContextSchema>;

// Server-only allowlist. Raw definitions and full player projections never reach the adapter.
export function interpretationContext(p: PublicProjection, definition: ScenarioDefinition): InterpretationContext {
  return InterpretationContextSchema.parse({
    revision: p.revision, turnNumber: p.turnNumber,
    player: { roleId: p.scenario.player.roleId, label: p.scenario.player.label, briefing: p.scenario.player.privateBrief },
    publicBrief: p.scenario.publicBrief, issues: p.scenario.issues, topics: p.scenario.topics,
    knownFacts: p.knownFacts, acknowledgementFactIds: p.acknowledgementFactIds,
    availableArguments: definition.arguments.filter(a => p.availableArguments.some(allowed => allowed.id === a.id)
      && a.factIds.every(id => p.knownFacts.some(f => f.id === id)))
      .map(a => ({ claimId: a.id, label: a.label, supportingFactIds: a.factIds, condition: a.condition })),
    activeOffer: p.activeOffer,
  });
}
