import { PreparationInputSchema, PreparationSchema, ComparisonSchema } from '@arena/contracts/feedback';
import type { FeedbackReport } from '@arena/contracts/feedback';
import { createInitialState, enumeratePackages, evaluateUtility, participant } from '@arena/domain';
import { ApiError, corruptState } from '../api-error.ts';
import { ArenaRepository, hashBody } from '../repositories/arena-repository.ts';
import { evaluateFeedback } from './evaluator.ts';
import { loadFeedbackRecords, readPreparation } from './records.ts';
import { mutual } from './predicates.ts';

export function compareReports(current: FeedbackReport, predecessor: FeedbackReport) {
  const compatible = current.configHash === predecessor.configHash && current.definitionHash === predecessor.definitionHash
    && current.rubricVersion === predecessor.rubricVersion && current.evaluatorVersion === predecessor.evaluatorVersion
    && current.scenarioRubricVersion === predecessor.scenarioRubricVersion;
  const currentChecks = current.dimensions.flatMap(d => d.checks), oldChecks = predecessor.dimensions.flatMap(d => d.checks);
  const shared = currentChecks.flatMap(c => {
    const old = oldChecks.find(o => o.id === c.id);
    return compatible && old && [c, old].every(x => x.evidenceSufficiency === 'sufficient' && x.applicability === 'applicable')
      ? [{ id: c.id, label: c.label, before: old.status, after: c.status }] : [];
  });
  const excluded = currentChecks.filter(c => !shared.some(x => x.id === c.id)).map(c => c.label);
  return ComparisonSchema.parse({
    comparable: compatible && shared.length > 0,
    reason: !compatible ? 'Версии сценария, правил или вычислителя различаются. Оценки процесса несопоставимы.'
      : !shared.length ? 'Нет общих наблюдаемых применимых проверок.'
        : excluded.length ? 'Показаны только общие наблюдаемые проверки. Возможности или полнота доказательств различаются; общие баллы не вычитаются.'
          : 'Показаны одинаковые проверки двух попыток. Это наблюдения в учебной модели, а не измерение роста навыка.',
    currentSessionId: current.sessionId, predecessorSessionId: predecessor.sessionId,
    currentRevision: current.terminalRevision, predecessorRevision: predecessor.terminalRevision,
    currentOutcome: current.outcome, predecessorOutcome: predecessor.outcome, sharedChecks: shared, excludedChecks: excluded,
  });
}
export class FeedbackService {
  readonly repository: ArenaRepository;
  constructor(repository: ArenaRepository) { this.repository = repository; }
  preparation(id: string) {
    return this.repository.read(() => { this.repository.session(id); return { record: readPreparation(this.repository, id) }; });
  }
  savePreparation(id: string, input: unknown) {
    const parsed = PreparationInputSchema.safeParse(input);
    if (!parsed.success) throw new ApiError(400, 'INVALID_REQUEST', 'Выберите цель и явно подтвердите свою альтернативу.');
    return this.repository.immediate(() => {
      const row = this.repository.session(id), version = this.repository.version(row.scenario_version_id);
      const s = this.repository.definition(version), state = this.repository.state(row, s), player = participant(s, 'player'), choice = parsed.data;
      if (state.revision !== 0) throw new ApiError(409, 'STALE_REVISION', 'Подготовку можно записать только до первого хода.', state.revision);
      if (choice.ownBoundary !== player.batna.utility) throw new ApiError(422, 'DOMAIN_REJECTED', 'Подтвердите свою альтернативу из брифинга этой версии.');
      const threshold = choice.goal === 'target' ? player.target : player.batna.utility;
      const initial = createInitialState(s, { sessionId: id, scenarioVersionId: version.id });
      if (!enumeratePackages(s).some(c => mutual(s, initial, c.terms) && evaluateUtility(s, 'player', c.terms) >= threshold)) {
        throw new ApiError(422, 'DOMAIN_REJECTED', 'Выбранная цель недостижима в допустимых условиях этой версии.');
      }
      const record = PreparationSchema.parse({ sessionId: id, scenarioVersionId: version.id, version: 'preparation-v1',
        recordedRevision: 0, goal: choice.goal, ownBoundary: choice.ownBoundary,
        acknowledgedAlternative: true, selectedThreshold: threshold });
      const old = readPreparation(this.repository, id);
      if (old) {
        if (hashBody(old) !== hashBody(record)) throw new ApiError(409, 'IDEMPOTENCY_CONFLICT', 'Подготовка уже зафиксирована. Для другого выбора создайте новую попытку.');
        return { record: old };
      }
      this.repository.db.prepare('INSERT INTO session_preparation VALUES (?, ?)').run(id, JSON.stringify(record));
      return { record };
    });
  }
  report(id: string, revision: number) {
    return this.repository.read(() => evaluateFeedback(loadFeedbackRecords(this.repository, id, revision)));
  }
  comparison(id: string, revision: number, predecessorId: string) {
    return this.repository.read(() => {
      const row = this.repository.session(id);
      if (row.replay_of !== predecessorId || id === predecessorId) throw new ApiError(422, 'DOMAIN_REJECTED', 'Сравнение доступно только с непосредственной исходной попыткой.');
      const previous = this.repository.session(predecessorId);
      if (!previous.terminal_at) return corruptState();
      return compareReports(evaluateFeedback(loadFeedbackRecords(this.repository, id, revision)),
        evaluateFeedback(loadFeedbackRecords(this.repository, predecessorId, previous.revision)));
    });
  }
}
