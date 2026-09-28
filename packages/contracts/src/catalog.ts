import { z } from 'zod';
import { PublishedScenarioSchema, ReferencePreviewSchema } from './g2.ts';
import type { PublicProjection } from './projection.ts';

// Application publication metadata only. Frozen G1/G2/G3 and ML imports stay unchanged.
export const CatalogReferenceSchema = ReferencePreviewSchema.extend({
  templateId: z.union([z.enum(['S1-SUPPLY-LAUNCH', 'S2-WORKLOAD-URGENT']), z.string().regex(/^G5-S[12]-[a-f0-9]{40}$/)]),
});
export const PublishedCatalogScenarioSchema = PublishedScenarioSchema.extend({ preview: CatalogReferenceSchema });
export const ReferenceCatalogSchema = z.array(CatalogReferenceSchema).max(2);
export const PublishedCatalogSchema = z.array(PublishedCatalogScenarioSchema);
export type CatalogReference = z.infer<typeof CatalogReferenceSchema>;
export type PublishedCatalogScenario = z.infer<typeof PublishedCatalogScenarioSchema>;

type PublicIssue = PublicProjection['scenario']['issues'][number];
// Nominal choices already have complete labels (e.g. "Без помощника").
// Ordered quantities retain their units without dropping a nonnumeric label's amount.
export function formatIssueValue(issue: PublicIssue, value: PublicIssue['values'][number]): string {
  if (!issue.ordered || value.quantity === null) return value.label;
  const amount = `${value.quantity} ${issue.unit}`;
  return value.label === String(value.quantity) ? amount : `${value.label} (${amount})`;
}
