import { CanonicalActionSchema, DomainEventSchema, NegotiationStateSchema } from '@arena/contracts';
import type { CanonicalAction, DomainEvent, NegotiationState, ScenarioDefinition } from '@arena/contracts';
import { PreparationSchema } from '@arena/contracts/feedback';
import type { Preparation } from '@arena/contracts/feedback';
import { classifyOutcome, createInitialState, projectPlayer, socialEffect } from '@arena/domain';
import type { PublicTurn } from '@arena/contracts/g2';
import { ApiError, corruptState } from '../api-error.ts';
import { ArenaRepository, hashBody, readPublicResponse } from '../repositories/arena-repository.ts';

export type RecordedTurn = {
  before: NegotiationState; after: NegotiationState; action: CanonicalAction;
  events: DomainEvent[]; publicTurn: PublicTurn;
};
export function readPreparation(repo: ArenaRepository, id: string): Preparation | null {
  const row = repo.db.prepare<[string], { record_json: string }>('SELECT record_json FROM session_preparation WHERE session_id = ?').get(id);
  if (!row) return null;
  try {
    const p = PreparationSchema.parse(JSON.parse(row.record_json));
    if (p.sessionId !== id || p.scenarioVersionId !== repo.session(id).scenario_version_id) return corruptState();
    return p;
  } catch { return corruptState(); }
}
export function loadFeedbackRecords(repo: ArenaRepository, id: string, revision: number) {
  const row = repo.session(id), version = repo.version(row.scenario_version_id), scenario = repo.definition(version);
  const terminal = repo.state(row, scenario);
  if (!terminal.outcome) throw new ApiError(409, 'SESSION_NOT_TERMINAL', 'Сначала завершите попытку.');
  if (terminal.revision !== revision) throw new ApiError(409, 'STALE_REVISION', 'Запрошена другая редакция попытки.', terminal.revision);
  const rows = repo.turns(id), turns: RecordedTurn[] = [], transcript: PublicTurn[] = [];
  let before = createInitialState(scenario, { sessionId: id, scenarioVersionId: version.id });
  let completeEvents = true;
  const offers = new Set<string>();
  try {
    if (rows.length !== terminal.revision) return corruptState();
    for (const [index, saved] of rows.entries()) {
      const n = index + 1;
      const action = CanonicalActionSchema.parse(JSON.parse(saved.action_json));
      const events = DomainEventSchema.array().parse(JSON.parse(saved.events_json));
      const after = NegotiationStateSchema.parse(JSON.parse(saved.state_after_json));
      const response = readPublicResponse(saved.public_response_json), publicTurn = response.transcript.at(-1);
      if (!publicTurn || saved.session_id !== id || saved.turn_number !== n || after.sessionId !== id
        || after.scenarioVersionId !== version.id || after.revision !== n || after.turnNumber !== n
        || after.configHash !== terminal.configHash || after.rubricVersion !== terminal.rubricVersion
        || after.engineVersion !== terminal.engineVersion || publicTurn.turnNumber !== n
        || publicTurn.requestId !== saved.request_id || response.scenarioVersionId !== version.id
        || response.replayOf !== row.replay_of
        || hashBody(response.projection) !== hashBody(projectPlayer(scenario, after))
        || hashBody(response.transcript) !== hashBody([...transcript, publicTurn])
        || hashBody(after.events) !== hashBody([...before.events, ...events])) return corruptState();
      for (const [offset, e] of events.entries()) {
        const sequence = before.events.length + offset + 1;
        if (e.id !== `${id}:event:${sequence}` || e.sequence !== sequence || e.turnNumber !== n) return corruptState();
        const p = e.payload;
        if (p.type === 'action_played' && (p.requestId !== saved.request_id || hashBody(p.action) !== hashBody(action))) return corruptState();
        if (p.type === 'offer_proposed' || p.type === 'counteroffer_created') {
          const party = p.type === 'offer_proposed' ? 'player' : 'opponent';
          if (p.offer.id !== `${id}:offer:${n}:${party}` || p.offer.turnNumber !== n || p.offer.proposer !== party) return corruptState();
          offers.add(p.offer.id);
        } else if ('offerId' in p && !offers.has(p.offerId)) return corruptState();
        if ('factId' in p && (!scenario.facts.some(f => f.id === p.factId) || !after.knownFactIds.includes(p.factId))) return corruptState();
      }
      if (publicTurn.observations.some(o => o.turnNumber !== n || !events.some(e => e.id === o.eventId))) return corruptState();
      const count = (type: DomainEvent['payload']['type']) => events.filter(e => e.payload.type === type).length;
      const newFacts = after.knownFactIds.filter(f => !before.knownFactIds.includes(f));
      completeEvents &&= count('action_played') === 1 && count('social_state_changed') === 1
        && newFacts.every(f => events.some(e => e.payload.type === 'fact_disclosed' && e.payload.factId === f))
        && after.progressCredits - before.progressCredits === count('progress_credit_earned')
        // Verify instrumentation against existing domain predicates; never synthesize missing scored events.
        && socialEffect(scenario, before, action).events.every(payload => events.some(e => hashBody(e.payload) === hashBody(payload)))
        && (after.lastUserOffer?.turnNumber !== n || events.some(e => e.payload.type === 'offer_proposed' && hashBody(e.payload.offer) === hashBody(after.lastUserOffer)))
        && (after.activeOffer?.turnNumber !== n || events.some(e => e.payload.type === 'counteroffer_created' && hashBody(e.payload.offer) === hashBody(after.activeOffer)));
      const accepted = after.events.flatMap(e => e.payload.type === 'progress_credit_earned' ? [e.payload] : []);
      completeEvents &&= new Set(accepted.map(e => e.key)).size === after.progressCredits
        && accepted.every((e, i) => e.total === i + 1);
      turns.push({ before, after, action, events, publicTurn }); transcript.push(publicTurn); before = after;
    }
    if (hashBody(before) !== hashBody(terminal)) return corruptState();
    const outcome = readPublicResponse(rows.at(-1)!.public_response_json).result;
    if (!outcome) return corruptState();
    const expected = projectPlayer(scenario, terminal).outcome!;
    if (hashBody(terminal.outcome) !== hashBody(classifyOutcome(scenario, terminal.terminalReason!, terminal.agreementOffer))
      || outcome.family !== expected.family || outcome.terminalReason !== expected.terminalReason
      || outcome.playerUtility !== expected.playerUtility || outcome.playerBatna !== expected.playerBatna
      || outcome.playerTarget !== expected.playerTarget || hashBody(outcome.agreementOffer) !== hashBody(terminal.agreementOffer)
      || hashBody(outcome.observations) !== hashBody(transcript.flatMap(t => t.observations))) return corruptState();
    const preparation = readPreparation(repo, id);
    if (preparation && !validPreparation(scenario, preparation)) return corruptState();
    return { row, version, scenario, terminal, turns, transcript, completeEvents, outcome, preparation,
      evidenceDigest: hashBody({ version: version.definition_hash, terminal, preparation,
        turns: rows.map(t => ({ requestId: t.request_id, action: t.action_json, events: t.events_json,
          state: t.state_after_json, response: t.public_response_json })) }) };
  } catch (error) { if (error instanceof ApiError) throw error; return corruptState(); }
}
export type FeedbackRecords = ReturnType<typeof loadFeedbackRecords>;
export function validPreparation(scenario: ScenarioDefinition, p: Preparation): boolean {
  const player = scenario.participants.find(x => x.party === 'player')!;
  return p.selectedThreshold === (p.goal === 'target' ? player.target : player.batna.utility)
    && p.ownBoundary === player.batna.utility && p.acknowledgedAlternative;
}

/** Repository convention: zero-based UTF-16 offsets; never bisect a surrogate pair. */
export function savedSpan(text: string, start: number, end: number): string {
  const splits = (i: number) => i > 0 && i < text.length
    && /[\uD800-\uDBFF]/.test(text[i - 1]!) && /[\uDC00-\uDFFF]/.test(text[i]!);
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start || end > text.length || splits(start) || splits(end)) {
    throw new Error('Invalid saved UTF-16 span');
  }
  return text.slice(start, end);
}
