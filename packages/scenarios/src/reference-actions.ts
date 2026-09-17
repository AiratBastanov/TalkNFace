import type { CanonicalAction, Package } from '@arena/contracts';

type ActionOf<K extends CanonicalAction['kind']> = Extract<CanonicalAction, { kind: K }>;
const social = () => ({ tone: 'neutral' as const, acknowledgementFactId: null, argumentId: null, contradictsFactId: null, evidenceRefs: [] });
export function question(primaryTopicId: string, tone: CanonicalAction['tone'] = 'neutral'): ActionOf<'question'> {
  return { ...social(), kind: 'question', primaryTopicId, secondaryTopicId: null, tone };
}
export function acknowledge(acknowledgementFactId: string): ActionOf<'acknowledge'> { return { ...social(), kind: 'acknowledge', acknowledgementFactId }; }
export function argument(argumentId: string): ActionOf<'argument'> { return { ...social(), kind: 'argument', argumentId }; }
export function offer(terms: Package, conditionalOn: Package = []): ActionOf<'offer'> { return { ...social(), kind: 'offer', terms, conditionalOn }; }
export function accept(offerId: string): ActionOf<'accept'> { return { ...social(), kind: 'accept', offerId }; }
export function pressure(tone: CanonicalAction['tone'] = 'threat'): ActionOf<'pressure'> { return { ...social(), kind: 'pressure', tone }; }
export function walkAway(): ActionOf<'walk_away'> { return { ...social(), kind: 'walk_away' }; }
export function clarification(): ActionOf<'clarification'> { return { ...social(), kind: 'clarification' }; }
export function supplyTerms(price: number, delivery: 'all7' | 'split40at7_rest14' | 'all14', prepay: number): Package {
  return [{ issueId: 'PRICE', valueId: String(price) }, { issueId: 'DELIVERY', valueId: delivery }, { issueId: 'PREPAY', valueId: String(prepay) }];
}
export function workloadTerms(scope: 'core' | 'full', deadline: number, help: number, defer: number): Package {
  return [{ issueId: 'SCOPE', valueId: scope }, { issueId: 'DEADLINE', valueId: String(deadline) }, { issueId: 'HELP', valueId: String(help) }, { issueId: 'DEFER_REPORT', valueId: String(defer) }];
}
