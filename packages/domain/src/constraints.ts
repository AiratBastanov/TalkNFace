import { assertNever } from '@arena/contracts';
import type { Constraint, Package, ScenarioDefinition } from '@arena/contracts';
import { required, valueOf } from './enumerate.ts';

export type RuleViolation = { ruleId: string; reasonCode: string; explanationFactId: string };
export type Feasibility = { feasible: boolean; violations: RuleViolation[] };
export function satisfiesConstraint(constraint: Constraint, terms: Package): boolean {
  switch (constraint.kind) {
    case 'allowed_values': return constraint.valueIds.includes(valueOf(terms, constraint.issueId));
    case 'forbid_combination': return !constraint.terms.every(term => valueOf(terms, term.issueId) === term.valueId);
    case 'linear_lte': return constraint.contributions.reduce((sum, table) => sum + required(table.cells.find(cell => cell.valueId === valueOf(terms, table.issueId)), 'missing constraint cell').amount, 0) <= constraint.bound;
    default: return assertNever(constraint);
  }
}
export function evaluateConstraints(scenario: ScenarioDefinition, terms: Package): Feasibility {
  const violations = scenario.constraints.filter(rule => !satisfiesConstraint(rule, terms)).map(rule => ({ ruleId: rule.id, reasonCode: rule.reasonCode, explanationFactId: rule.explanationFactId }));
  return { feasible: violations.length === 0, violations };
}
