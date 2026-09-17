import { PackageSchema, assertNever } from '@arena/contracts';
import type { DomainError, Package, PackagePredicate, ScenarioDefinition } from '@arena/contracts';

export type CatalogEntry = { index: number; terms: Package; key: string };
export function required<T>(value: T | undefined, description: string): T {
  if (value === undefined) throw new Error(`Invalid validated domain: ${description}`);
  return value;
}
export function valueOf(terms: Package, issueId: string): string {
  return required(terms.find(term => term.issueId === issueId), `missing issue ${issueId}`).valueId;
}
export function normalizePackage(scenario: ScenarioDefinition, input: unknown):
  { ok: true; terms: Package } | { ok: false; errors: DomainError[] } {
  const parsed = PackageSchema.safeParse(input);
  if (!parsed.success) return { ok: false, errors: [{ code: 'PACKAGE_SHAPE', path: '/terms', ref: null, message: 'Expected a complete package of issue/value IDs.' }] };
  const errors: DomainError[] = [];
  const terms = parsed.data;
  if (terms.length !== scenario.issues.length) errors.push({ code: 'PACKAGE_COVERAGE', path: '/terms', ref: null, message: 'Each issue must occur exactly once.' });
  for (const [i, term] of terms.entries()) {
    const issue = scenario.issues.find(item => item.id === term.issueId);
    if (!issue || !issue.values.some(value => value.id === term.valueId)) errors.push({ code: 'OUT_OF_DOMAIN', path: `/terms/${i}`, ref: term.issueId, message: 'Unknown issue or value.' });
    if (terms.filter(item => item.issueId === term.issueId).length !== 1) errors.push({ code: 'DUPLICATE_TERM', path: `/terms/${i}`, ref: term.issueId, message: 'Issue must occur once.' });
  }
  for (const issue of scenario.issues) if (!terms.some(term => term.issueId === issue.id)) errors.push({ code: 'MISSING_TERM', path: '/terms', ref: issue.id, message: 'Required issue is absent.' });
  if (errors.length) return { ok: false, errors };
  return { ok: true, terms: scenario.issues.map(issue => ({ issueId: issue.id, valueId: valueOf(terms, issue.id) })) };
}
export function packageKey(scenario: ScenarioDefinition, terms: Package): string {
  const normalized = normalizePackage(scenario, terms);
  if (!normalized.ok) throw new Error('Invalid package');
  return JSON.stringify(normalized.terms.map(term => [term.issueId, term.valueId]));
}
export function enumeratePackages(scenario: ScenarioDefinition): CatalogEntry[] {
  let rows: Package[] = [[]];
  for (const issue of scenario.issues) rows = rows.flatMap(prefix => issue.values.map(value => [...prefix, { issueId: issue.id, valueId: value.id }]));
  if (rows.length > 1296) throw new Error('Package catalog exceeds the bounded model');
  return rows.map((terms, index) => ({ index, terms, key: packageKey(scenario, terms) }));
}
export function matchesPredicate(terms: Package, predicate: PackagePredicate): boolean {
  return predicate.every(item => {
    const value = valueOf(terms, item.issueId);
    switch (item.kind) {
      case 'eq': return value === item.valueId;
      case 'in': return item.valueIds.includes(value);
      default: return assertNever(item);
    }
  });
}
export function packageDistance(scenario: ScenarioDefinition, left: Package, right: Package): number {
  return scenario.issues.reduce((total, issue) => {
    const a = issue.values.findIndex(value => value.id === valueOf(left, issue.id));
    const b = issue.values.findIndex(value => value.id === valueOf(right, issue.id));
    if (a < 0 || b < 0) throw new Error('Out-of-domain distance');
    return total + (issue.ordered ? Math.abs(a - b) : Number(a !== b));
  }, 0);
}
