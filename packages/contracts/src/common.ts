import { z } from 'zod';

export const IdSchema = z.string().min(1).max(64).regex(/^[A-Za-z0-9][A-Za-z0-9_.:-]*$/);
export const GeneratedIdSchema = z.string().min(1).max(160);
export const IntegerSchema = z.int();
export const UtilitySchema = z.int().min(-100).max(200);
export const LabelSchema = z.string().min(1).max(120);
export const TextSchema = z.string().min(1).max(2000);
export const PartySchema = z.enum(['player', 'opponent']);
export const TermSchema = z.strictObject({ issueId: IdSchema, valueId: IdSchema });
export const PackageSchema = z.array(TermSchema).min(2).max(4);
export const PredicateSchema = z.array(z.discriminatedUnion('kind', [
  z.strictObject({ kind: z.literal('eq'), issueId: IdSchema, valueId: IdSchema }),
  z.strictObject({ kind: z.literal('in'), issueId: IdSchema, valueIds: z.array(IdSchema).min(1).max(6) }),
])).min(1).max(3);
export const DomainErrorSchema = z.strictObject({
  code: IdSchema, path: z.string().max(500), ref: IdSchema.nullable(), message: z.string().min(1).max(500),
});
// Offsets are UTF-16. A later text boundary verifies them against the referenced source.
export const EvidenceRefSchema = z.strictObject({
  id: IdSchema, sourceId: IdSchema,
  span: z.strictObject({ start: z.int().min(0).max(4000), end: z.int().min(1).max(4000) }).nullable(),
});
export type Party = z.infer<typeof PartySchema>;
export type Term = z.infer<typeof TermSchema>;
export type Package = z.infer<typeof PackageSchema>;
export type PackagePredicate = z.infer<typeof PredicateSchema>;
export type DomainError = z.infer<typeof DomainErrorSchema>;
export type EvidenceRef = z.infer<typeof EvidenceRefSchema>;

export function assertNever(value: never): never { throw new Error(`Unexpected discriminant: ${String(value)}`); }
