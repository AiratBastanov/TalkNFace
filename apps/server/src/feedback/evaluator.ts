import type { CanonicalAction, DomainEvent, Package } from '@arena/contracts';
import { FeedbackReportSchema } from '@arena/contracts/feedback';
import type { FeedbackCheck, FeedbackEvidence, FeedbackReport } from '@arena/contracts/feedback';
import { enumeratePackages, evaluateAuthority, evaluateConstraints, evaluateUtility, participant, projectPlayer, qualifiesConditionalExchange } from '@arena/domain';
import { renderPlayer } from '../presentation/renderers.ts';
import type { FeedbackRecords, RecordedTurn } from './records.ts';
import { savedSpan } from './records.ts';
import { feasible, mutual, neutral, pareto, usesFact, validateSuggestion } from './predicates.ts';

export const RUBRIC_VERSION = 'app-guided-rubric-v1';
export const EVALUATOR_VERSION = 'app-evidence-v1';
const dimensions = [
  { id: 'preparation', label: 'Подготовка', weight: 15 },
  { id: 'interests', label: 'Интересы и слушание', weight: 25 },
  { id: 'argument', label: 'Аргументация и возражения', weight: 20 },
  { id: 'value', label: 'Создание ценности', weight: 15 },
  { id: 'concession', label: 'Управление уступками', weight: 15 },
  { id: 'relationship', label: 'Отношения', weight: 10 },
];
const round = (n: number) => Math.round(n * 100) / 100;
type Status = FeedbackCheck['status'];
const ownOffer = (t: RecordedTurn) => t.events.find(e => e.payload.type === 'offer_proposed');
function actionTerms(t: RecordedTurn): Package | null {
  return t.action.kind === 'offer' || t.action.kind === 'counter_offer' ? t.action.terms
    : t.action.kind === 'accept' && t.before.activeOffer?.id === t.action.offerId ? t.before.activeOffer.terms : null;
}
export function evaluateFeedback(r: FeedbackRecords): FeedbackReport {
  const { scenario: s, terminal, turns } = r;
  const evidence: FeedbackEvidence[] = [], checks: FeedbackCheck[] = [];
  const identity = { sessionId: terminal.sessionId, scenarioVersionId: terminal.scenarioVersionId, terminalRevision: terminal.revision };
  function eventRef(e: DomainEvent, description: string): string {
    const id = e.id;
    if (evidence.some(x => x.id === id)) return id;
    const t = turns[e.turnNumber - 1]!;
    const isAction = ['action_played', 'offer_proposed', 'fact_acknowledged', 'grounded_argument_applied', 'damaging_tone'].includes(e.payload.type);
    const text = isAction ? t.publicTurn.playerText : null;
    evidence.push({ ...identity, id, turnNumber: e.turnNumber, requestId: t.publicTurn.requestId, eventId: e.id,
      kind: isAction ? 'guided_action' : 'structured_event', description,
      quote: text ? { speaker: 'player', text: savedSpan(text, 0, text.length), start: 0, end: text.length } : null, window: null });
    return id;
  }
  function actionRef(t: RecordedTurn, description: string): string {
    const e = t.events.find(x => x.payload.type === 'action_played');
    if (e) return eventRef(e, description);
    const id = `${terminal.sessionId}:turn:${t.after.turnNumber}`;
    if (!evidence.some(x => x.id === id)) evidence.push({ ...identity, id, turnNumber: t.after.turnNumber,
      requestId: t.publicTurn.requestId, eventId: null, kind: 'guided_action', description,
      quote: { speaker: 'player', text: savedSpan(t.publicTurn.playerText, 0, t.publicTurn.playerText.length), start: 0, end: t.publicTurn.playerText.length }, window: null });
    return id;
  }
  function windowRef(key: string, description: string, from = 1, to = terminal.turnNumber): string {
    const id = `${terminal.sessionId}:window:${key}`;
    evidence.push({ ...identity, id, turnNumber: from, requestId: from ? turns[from - 1]!.publicTurn.requestId : null,
      eventId: null, kind: from === 0 ? 'preparation' : 'window', description, quote: null, window: { from, to } });
    return id;
  }
  function add(id: string, label: string, status: Status, explanation: string, evidenceIds: string[]) {
    if (!id.startsWith('preparation.') && !r.completeEvents) {
      status = 'unobservable'; explanation = 'Неполная историческая запись событий: нельзя доказать действие или его отсутствие.';
    }
    checks.push({ id, label, status, applicability: status === 'not_applicable' ? 'inapplicable'
      : status === 'unobservable' ? (id.startsWith('preparation.') ? 'applicable' : 'unknown') : 'applicable',
      evidenceSufficiency: status === 'unobservable' ? 'missing' : 'sufficient', explanation, evidenceIds });
  }
  const prep = windowRef('preparation', r.preparation
    ? 'Отдельная подтверждённая запись подготовки до хода 1, версия preparation-v1.'
    : 'Проверена отдельная запись подготовки до хода 1: отсутствует. Значения из брифинга не являются выбором игрока.', 0, 0);
  add('preparation.goal', 'Явно выбрана достижимая цель', r.preparation ? 'passed' : 'unobservable',
    r.preparation ? `До первого хода выбрана достижимая учебная полезность не менее ${r.preparation.selectedThreshold}.`
      : 'До первого хода не сохранён явный выбор цели. Подготовку по умолчанию не засчитываем.', [prep]);
  add('preparation.boundary', 'До старта зафиксирована своя альтернатива', r.preparation ? 'passed' : 'unobservable',
    r.preparation ? `Подтверждена своя альтернатива с полезностью ${r.preparation.ownBoundary}.`
      : 'Явного подтверждения своей альтернативы до старта нет в записи.', [prep]);

  const all = turns.flatMap(t => t.events), opponent = participant(s, 'opponent');
  const discovery = all.find(e => e.payload.type === 'fact_disclosed' && s.facts.some(f =>
    e.payload.type === 'fact_disclosed' && f.id === e.payload.factId && f.visibility === 'hidden' && f.ownerId === opponent.id && f.interestId !== null));
  add('interests.discovery', 'Выявлен частный интерес', discovery ? 'passed' : 'failed',
    discovery ? 'Утверждённый поток раскрыл относящийся к переговорам частный интерес.'
      : 'Возможность задать вопрос была; раскрытия частного интереса в записи нет.',
    [discovery ? eventRef(discovery, 'Сохранено раскрытие относящегося к переговорам интереса.')
      : windowRef('discovery', 'Проверены все действия и раскрытия; вопросы были доступны с хода 1.')]);

  const ackEvents = all.filter(e => e.payload.type === 'fact_acknowledged' && e.payload.first);
  let used: { ack: DomainEvent; turn: RecordedTurn } | undefined;
  for (const ack of ackEvents) {
    if (ack.payload.type !== 'fact_acknowledged') continue;
    const factId = ack.payload.factId;
    const t = turns.find(t => {
      const terms = actionTerms(t);
      return t.after.turnNumber >= ack.turnNumber && terms && feasible(s, t.before, terms) && usesFact(s, factId, terms);
    });
    if (t) { used = { ack, turn: t }; break; }
  }
  add('interests.use', 'Признанный факт использован в условиях', used ? 'passed' : 'failed',
    used ? 'Сохранённое признание конкретного факта связано с выполнимыми условиями через правило сценария.'
      : 'Не найдена связка «признанный факт → выполнимый пакет, учитывающий именно этот факт».',
    used ? [eventRef(used.ack, 'Сохранено признание конкретного факта.'), actionRef(used.turn, 'Сохранённое действие реализует условие признанного факта.')]
      : [windowRef('use', 'Проверены признания и последующие предложения/принятия; известный публичный факт был доступен с начала.')]);

  const argument = all.find(e => {
    if (e.payload.type !== 'grounded_argument_applied' || !e.payload.first) return false;
    const id = e.payload.argumentId, binding = s.arguments.find(a => a.id === id);
    return binding && binding.condition.length > 0 && binding.factIds.every(f => turns[e.turnNumber - 1]!.before.knownFactIds.includes(f));
  });
  add('argument.grounded', 'Довод привязан к объективному условию', argument ? 'passed' : 'failed',
    argument ? 'Записан довод с известными на тот момент фактами и объективным условием.'
      : 'Доступная цепочка «узнать факт → привести связанный довод» не завершена.',
    [argument ? eventRef(argument, 'Сохранено применение довода по известному факту.')
      : windowRef('argument', 'Проверены события доводов и доступность их фактов в снимках до каждого хода.')]);

  const objections = all.filter(e => ['offer_rejected_physical', 'offer_rejected_authority', 'offer_rejected_aspiration'].includes(e.payload.type)
    && turns[e.turnNumber - 1]!.after.terminalReason === null);
  let response: { objection: DomainEvent; turn: RecordedTurn } | undefined;
  for (const objection of objections) {
    const rejected = turns[objection.turnNumber - 1]!;
    const oldTerms = actionTerms(rejected)!;
    const t = turns.find(t => {
      const terms = actionTerms(t), p = objection.payload;
      if (t.after.turnNumber <= objection.turnNumber || !terms || !feasible(s, t.before, terms)) return false;
      if (p.type === 'offer_rejected_physical') return p.ruleIds.every(id => !evaluateConstraints(s, terms).violations.some(v => v.ruleId === id));
      if (p.type === 'offer_rejected_authority') return p.ruleIds.every(id => !['player', 'opponent'].some(party =>
        evaluateAuthority(s, party as 'player' | 'opponent', terms, party === 'player' ? 'propose' : 'accept', t.before.resourceAuthorizations).violations.some(v => v.ruleId === id)));
      if (p.type !== 'offer_rejected_aspiration') return false;
      const issued = rejected.events.find(e => e.payload.type === 'counteroffer_created');
      return (t.action.kind === 'accept' && issued?.payload.type === 'counteroffer_created' && t.action.offerId === issued.payload.offer.id)
        || evaluateUtility(s, 'opponent', terms) > evaluateUtility(s, 'opponent', oldTerms);
    });
    if (t) { response = { objection, turn: t }; break; }
  }
  add('argument.objection', 'Дан содержательный ответ на возникшее возражение',
    response ? 'passed' : objections.length ? 'failed' : 'not_applicable',
    response ? 'Последующее действие устраняет конкретное ограничение или отвечает на отклонённые условия.'
      : objections.length ? 'После возражения оставался ход, но содержательного ответа по его причине не найдено.'
        : 'Не было записанного возражения с доступным последующим ходом.',
    response ? [eventRef(response.objection, 'Конкретное отклонённое предложение.'), actionRef(response.turn, 'Сохранённый содержательный ответ на это отклонение.')]
      : [windowRef('objection', 'Проверены отклонения предложений и оставшиеся после них ходы.')]);

  const offered = turns.filter(t => ownOffer(t));
  const mutualTurn = offered.find(t => mutual(s, t.before, actionTerms(t)!));
  add('value.mutual', 'Предложен взаимно приемлемый выполнимый пакет', mutualTurn ? 'passed' : 'failed',
    mutualTurn ? 'Предложенный пакет проходит физические ограничения, полномочия и обе границы альтернатив. Итоговая сделка для этого зачёта не нужна.'
      : 'Такого собственного предложения в записи нет. Принятие чужого пакета само по себе не является предложением.',
    [mutualTurn ? actionRef(mutualTurn, 'Сохранённое собственное предложение прошло проверку взаимной приемлемости.')
      : windowRef('mutual', 'Проверены собственные предложения; возможность предложить пакет была с начала.')]);

  const catalog = enumeratePackages(s);
  const afterOwn = turns.filter(t => t.before.lastUserOffer);
  const paretoOpportunity = afterOwn.find(t => catalog.some(c => feasible(s, t.before, c.terms) && pareto(s, t.before.lastUserOffer!.terms, c.terms)));
  const paretoTurn = offered.find(t => t.before.lastUserOffer && feasible(s, t.before, actionTerms(t)!) && pareto(s, t.before.lastUserOffer.terms, actionTerms(t)!));
  const pairRefs = (t: RecordedTurn, description: string) => [
    actionRef(turns[t.before.lastUserOffer!.turnNumber - 1]!, 'Предшествующее собственное предложение.'), actionRef(t, description)];
  add('value.pareto', 'Новый пакет улучшает одну сторону без потерь другой',
    paretoTurn ? 'passed' : paretoOpportunity ? 'failed' : 'not_applicable',
    paretoTurn ? 'Сравнение с непосредственно предшествующей собственной офертой подтверждает улучшение.'
      : paretoOpportunity ? 'После собственной оферты было доступно улучшение без потерь другой стороны, но оно не записано.'
        : 'После собственной оферты не было хода с объективно доступным улучшением без потерь.',
    paretoTurn ? pairRefs(paretoTurn, 'Сохранено улучшение относительно предыдущей собственной оферты.')
      : [windowRef('pareto', 'Проверены окна после собственных оферт и ограниченный каталог допустимых пакетов.')]);

  const reciprocalOpportunity = afterOwn.find(t => catalog.some(c => feasible(s, t.before, c.terms)
    && c.terms.some(term => qualifiesConditionalExchange(s, t.before, c.terms, [term]))));
  const reciprocal = offered.find(t => (t.action.kind === 'offer' || t.action.kind === 'counter_offer')
    && feasible(s, t.before, t.action.terms) && qualifiesConditionalExchange(s, t.before, t.action.terms, t.action.conditionalOn));
  add('concession.reciprocal', 'Уступка связана с реальным встречным условием',
    reciprocal ? 'passed' : reciprocalOpportunity ? 'failed' : 'not_applicable',
    reciprocal ? 'Записанное встречное условие проходит доменную проверку реального обмена по разным условиям.'
      : reciprocalOpportunity ? 'Реальный условный обмен был доступен после собственной оферты; записанного обмена нет.'
        : 'Не было последующего хода с доступным реальным условным обменом.',
    reciprocal ? pairRefs(reciprocal, 'Сохранено предложение с проверенным встречным условием.')
      : [windowRef('reciprocal', 'Проверены предыдущие собственные оферты, доступные пакеты и сохранённые встречные условия.')]);

  const solution = (t: RecordedTurn) => {
    const own = t.before.lastUserOffer, active = t.before.activeOffer;
    return own && mutual(s, t.before, own.terms) ? own : active && mutual(s, t.before, active.terms) ? active : null;
  };
  const available = turns.filter(t => solution(t));
  const waste = available.find(t => {
    const terms = actionTerms(t), prior = solution(t)!;
    const conditional = (t.action.kind === 'offer' || t.action.kind === 'counter_offer') && qualifiesConditionalExchange(s, t.before, t.action.terms, t.action.conditionalOn);
    return terms && !conditional && evaluateUtility(s, 'player', terms) < evaluateUtility(s, 'player', prior.terms)
      && evaluateUtility(s, 'opponent', terms) <= evaluateUtility(s, 'opponent', prior.terms);
  });
  add('concession.discipline', 'После доступного решения нет бесполезного ухудшения',
    waste ? 'failed' : available.length ? 'passed' : 'not_applicable',
    waste ? 'После доступного решения безусловно ухудшена своя полезность без улучшения полезности другой стороны.'
      : available.length ? 'В проверенных ходах после доступного решения такого безусловного ухудшения нет.'
        : 'Не было записанного приемлемого решения с последующим ходом для игрока.',
    waste ? [actionRef(turns[solution(waste)!.turnNumber - 1]!, 'Ход, на котором появилось доступное решение.'), actionRef(waste, 'Сохранено безусловное ухудшение после доступного решения.')]
      : [windowRef('discipline', 'Проверены последующие решения после собственных взаимно приемлемых пакетов и действующих встречных предложений.',
        available[0]?.after.turnNumber ?? 1)]);

  const damaging = all.find(e => e.payload.type === 'damaging_tone');
  add('relationship.pressure', 'Нет повреждающего личного давления', damaging ? 'failed' : 'passed',
    damaging ? 'Движок записал личное давление, обвинение или отрицание установленного факта; это не оценка личности.'
      : 'В сохранённых действиях нет событий повреждающего давления. Отдельный вежливый ярлык баллов не добавляет.',
    [damaging ? eventRef(damaging, 'Структурное событие повреждающего действия в guided-режиме.')
      : windowRef('pressure', 'Проверены все сохранённые события повреждающего давления.')]);
  const tensions = turns.filter(t => t.after.terminalReason === null && t.events.some(e =>
    e.payload.type === 'tension_warning' || (e.payload.type === 'social_state_changed' && e.payload.tensionAfter > e.payload.tensionBefore)));
  let repairStatus: Status = tensions.length ? 'failed' : 'not_applicable';
  let repairRefs: string[] = [];
  if (tensions.length) {
    // All recorded causes with an available response window must be accounted for.
    let missingCause = false, unresolved = false;
    for (const t of tensions) {
      const repair = all.find(e => e.turnNumber > t.after.turnNumber && e.payload.type === 'tension_repaired');
      if (!repair) { unresolved = true; continue; }
      if (repair.payload.type !== 'tension_repaired' || t.action.contradictsFactId === null || repair.payload.factId !== t.action.contradictsFactId) missingCause = true;
      repairRefs.push(actionRef(t, 'Сохранённое действие, после которого возросло напряжение.'), eventRef(repair, 'Домен записал снятие предупреждения; причинная связь проверяется отдельно.'));
    }
    repairStatus = unresolved ? 'failed' : missingCause ? 'unobservable' : 'passed';
  }
  if (!repairRefs.length) repairRefs = [windowRef('repair', 'Проверены причины роста напряжения, оставшиеся ходы и события снятия предупреждения.')];
  add('relationship.repair', 'После напряжения исправлена его конкретная причина', repairStatus,
    repairStatus === 'passed' ? 'Признан именно факт, отрицание которого было записано на ходе возникновения напряжения.'
      : repairStatus === 'unobservable' ? 'Снятие предупреждения записано, но связи с конкретной причиной напряжения в данных нет.'
        : repairStatus === 'failed' ? 'После записанного напряжения был доступен ход, но причинное исправление не записано.'
          : 'Не было записанного роста напряжения с последующим доступным ходом.', repairRefs);

  const progressEvents = all.filter(e => e.payload.type === 'progress_credit_earned');
  const credits = new Set(progressEvents.flatMap(e => e.payload.type === 'progress_credit_earned' ? [e.payload.key] : [])).size;
  const applicable = checks.filter(c => c.applicability === 'applicable').length;
  const missing = checks.filter(c => c.status === 'unobservable').map(c => c.id);
  const dimensionResults = dimensions.map(d => {
    const list = checks.filter(c => c.id.startsWith(d.id + '.'));
    const count = list.filter(c => c.applicability === 'applicable').length, passed = list.filter(c => c.status === 'passed').length;
    return { ...d, applicable: count, passed, score: count && !list.some(c => c.status === 'unobservable') ? 100 * passed / count : null, checks: list };
  });
  const included = dimensionResults.filter(d => d.score !== null);
  const sufficient = r.completeEvents && missing.length === 0 && applicable >= 6 && credits >= 3;
  const overall = {
    score: sufficient ? round(included.reduce((sum, d) => sum + d.score! * d.weight, 0) / included.reduce((sum, d) => sum + d.weight, 0)) : null,
    applicableChecks: applicable, progressCredits: credits, missingChecks: missing,
    progressEvidenceIds: progressEvents.map(e => eventRef(e, 'Сохранён один принятый зачёт прогресса; повторные факты и действия не умножают его.')),
    explanation: sufficient ? 'Учебная оценка записанного процесса; полезность сделки в неё не входит.'
      : 'Недостаточно наблюдений: нужны не менее 6 применимых проверок, 3 принятых зачётов прогресса и доказательства по всем обязательным проверкам.',
  };
  const report: FeedbackReport = { ...identity, configHash: terminal.configHash, definitionHash: r.version.definition_hash,
    scenarioRubricVersion: terminal.rubricVersion, rubricVersion: RUBRIC_VERSION, evaluatorVersion: EVALUATOR_VERSION,
    evidenceDigest: r.evidenceDigest, computation: 'derived_on_read', mode: 'saved_guided_actions', outcome: r.outcome,
    preparation: r.preparation, dimensions: dimensionResults.map(d => ({ ...d, score: d.score === null ? null : round(d.score) })),
    evidence, overall, suggestions: [] };
  const failed = (id: string) => checks.find(c => c.id === id && c.status === 'failed');
  function suggest(id: string, t: RecordedTurn, candidate: CanonicalAction, focus: string) {
    const check = failed(id), action = validateSuggestion(s, t.before, candidate);
    if (!check || !action || report.suggestions.length) return;
    report.suggestions.push({ checkId: id, evidenceIds: check.evidenceIds, focus,
      proposedWording: renderPlayer(action, projectPlayer(s, t.before)), action, priorRevision: t.before.revision,
      validation: 'prior_state', disclaimer: 'Предложенный вариант, а не прошлая реплика. Допустимость действия не гарантирует соглашения.' });
  }
  if (damaging) suggest('relationship.pressure', turns[damaging.turnNumber - 1]!, { ...neutral(), kind: 'pressure', tone: 'respectful_firm' },
    'В следующий раз обозначьте свою альтернативу без личного давления.');
  if (failed('interests.discovery')) {
    const t = turns[0]!, topic = projectPlayer(s, t.before).scenario.topics[0];
    if (topic) suggest('interests.discovery', t, { ...neutral(), kind: 'question', primaryTopicId: topic.id, secondaryTopicId: null },
      'До выбора условий уточните одну доступную тему вопросом.');
  }
  if (failed('argument.grounded')) {
    for (const t of turns) {
      const argument = projectPlayer(s, t.before).availableArguments[0];
      if (argument) { suggest('argument.grounded', t, { ...neutral(), kind: 'argument', argumentId: argument.id },
        'Свяжите довод с фактом, который уже был известен на этом ходе.'); break; }
    }
  }
  if (failed('argument.objection')) {
    const t = turns.find(t => t.before.activeOffer && evaluateUtility(s, 'player', t.before.activeOffer.terms) >= participant(s, 'player').batna.utility);
    if (t?.before.activeOffer) suggest('argument.objection', t, { ...neutral(), kind: 'accept', offerId: t.before.activeOffer.id },
      'Рассмотрите уже полученное встречное предложение: оно доступно на этом ходе и не хуже вашей альтернативы.');
  }
  if (!report.suggestions.length && !r.preparation) report.suggestions.push({
    checkId: 'preparation.goal', evidenceIds: [prep], focus: 'В новой попытке явно сохраните цель и свою альтернативу до первого хода.',
    proposedWording: 'Выберите достижимую цель и подтвердите свою альтернативу в брифинге новой попытки.',
    action: null, priorRevision: 0, validation: 'next_preparation', disclaimer: 'Это предложение для новой попытки. Подготовка завершённой попытки не дописывается.',
  });
  return FeedbackReportSchema.parse(report);
}
