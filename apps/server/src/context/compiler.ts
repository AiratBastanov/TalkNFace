import type { CanonicalAction, Package, ScenarioDefinition } from '@arena/contracts';
import { SettingsSchema, CONTROLS } from '@arena/contracts/context-config';
import type { Settings, CandidateValidation, SettingField } from '@arena/contracts/context-config';
import { S1, S2 } from '@arena/scenarios';
import { createInitialState, transition, validateScenario, matchesPredicate, packageKey } from '@arena/domain';
import { hashBody } from '../repositories/arena-repository.ts';
import { referencePreview } from '../services/session-service.ts';
import { renderTurn, guidedActions } from '../presentation/renderers.ts';
import { projectPlayer } from '@arena/domain';

export const COMPILER_VERSION = 'context-reference-v1';
export const VALIDATION_POLICY = 'context-witness-v1';
export const APPROVAL_VERSION = COMPILER_VERSION + '/' + VALIDATION_POLICY;
// A finite catalog and two fixed preparation strategies, never a dialogue-tree search.
export const LIMITS = { packages: 1296, templates: 2, offersPerTemplate: 64, turns: 8 } as const;
type Issue = CandidateValidation['issues'][number];
type Compiled = { definition: ScenarioDefinition | null; validation: Omit<CandidateValidation, 'revision' | 'settingsHash'> };
const issue = (message: string, fields: SettingField[] = ['topic', 'opponentRole', 'opponentGoals']): Issue => ({ fields, message });
const envelope = (issues: Issue[], definition: ScenarioDefinition | null = null): Compiled => ({
  definition, validation: {
    status: definition ? 'valid' : 'invalid', compilerVersion: APPROVAL_VERSION,
    candidateHash: definition ? hashBody(definition) : null, issues,
    summary: definition
      ? 'Проверены ограничения, полномочия и два разных приемлемых пути через игровой движок; один достигает полной цели. Выход без соглашения доступен. Проверьте брифинг перед публикацией.'
      : 'Публикация недоступна. Измените указанные настройки и повторите проверку; ваш выбор сохранён.',
    preview: definition ? referencePreview(definition) : null,
  },
});
const action = (kind: 'question' | 'acknowledge' | 'argument' | 'offer' | 'walk_away', value?: string | Package): CanonicalAction => {
  const common = { tone: 'neutral' as const, acknowledgementFactId: null, argumentId: null, contradictsFactId: null, evidenceRefs: [] };
  switch (kind) {
    case 'question': return { ...common, kind, primaryTopicId: value as string, secondaryTopicId: null };
    case 'acknowledge': return { ...common, kind, acknowledgementFactId: value as string };
    case 'argument': return { ...common, kind, argumentId: value as string };
    case 'offer': return { ...common, kind, terms: value as Package, conditionalOn: [] };
    case 'walk_away': return { ...common, kind };
  }
};

export function deriveDefinition(settings: Settings): ScenarioDefinition {
  const base = settings.sphere === 'supply' ? S1 : S2;
  const d = structuredClone(base);
  d.validation.witnessTraces = [];
  const fingerprint = hashBody({ settings, baseHash: hashBody(base), compilerVersion: COMPILER_VERSION,
    validationPolicy: VALIDATION_POLICY, engine: 'deterministic-core-v1', policy: base.policy.policyVersion });
  d.configFingerprint = fingerprint;
  d.templateId = 'G5-' + (settings.sphere === 'supply' ? 'S1-' : 'S2-') + fingerprint.slice(0, 40);
  d.policy.difficulty = settings.difficulty; d.policy.tone = settings.tone;
  const opponent = d.participants[1];
  if (settings.sphere === 'supply') {
    if (settings.topic === 'planned') {
      d.title = 'Плановая закупка'; d.topic = 'Плановая поставка';
      d.publicBrief = 'Плановая закупка: партию можно получить на день 7, частями или целиком на день 14. Согласуйте цену, график и предоплату. Цель и альтернатива закупщика сохраняются. Ситуация вымышлена.';
      const rule = d.constraints[0]; if (rule?.kind === 'allowed_values') rule.valueIds = ['all7', 'split40at7_rest14', 'all14'];
      d.facts.find(f => f.id === 'launch-bound')!.text = 'При плановой закупке допустима вся партия на день 14; срочный запуск не требуется.';
      d.participants[0].initialPosition = 'Нужна выполнимая плановая поставка в пределах бюджета.';
      d.participants[0].interests[0]!.text = 'Сохранить бюджет и выбрать подходящий график поставки.';
    }
    if (settings.opponentRole === 'account_manager') {
      opponent.roleId = 'account_manager'; opponent.label = 'Менеджер по работе с клиентом';
      opponent.authority.allowedValues[0]!.valueIds = ['100', '105', '110', '115'];
      d.facts.find(f => f.id === 'supplier-authority')!.text = 'Менеджер вправе согласовать цену только от 100 тысяч условных единиц.';
    }
    if (settings.opponentGoals === 'margin') {
      opponent.reservation = 22; opponent.batna.utility = 22;
      opponent.batna.description = 'Альтернативный заказ с более высокой доходностью.';
      opponent.privateBrief = 'Приоритет — доходность. Предоплата помогает меньше; альтернативный заказ даёт полезность 22.';
      opponent.goals[0]!.text = 'Сохранить доходность сделки; предоплата имеет меньшую ценность.';
      opponent.interests[1]!.text = 'Сохранить доходность, ограниченно учитывая предоплату.';
      opponent.utility.unary.find(t => t.issueId === 'PREPAY')!.cells = [
        { valueId: '0', utility: 0 }, { valueId: '30', utility: 4 }, { valueId: '50', utility: 18 },
      ];
      d.facts.find(f => f.id === 'cashflow-need')!.text = 'Предоплата помогает закупке сырья, но приоритет поставщика — доходность сделки.';
      d.arguments.find(a => a.id === 'cashflow-argument')!.label = 'Учесть ограниченную пользу предоплаты';
    }
  } else {
    if (settings.opponentRole === 'team_lead') {
      opponent.roleId = 'team_lead'; opponent.label = 'Руководитель группы';
      opponent.authority.resources[0]!.proposalRequiresAuthorization = false;
      opponent.privateBrief = 'Отчёт можно перенести. Руководитель группы вправе самостоятельно назначить доступного помощника на 6 часов.';
      d.facts.find(f => f.id === 'helper-authority')!.text = 'Руководитель группы вправе сам предложить доступного помощника на 6 часов.';
    }
    if (settings.opponentGoals === 'deliver_scope') {
      opponent.reservation = 27; opponent.batna.utility = 27;
      opponent.batna.description = 'Продолжить приоритетную ранее согласованную работу.';
      opponent.goals[0]!.text = 'Выполнить полный объём и сохранить приемлемую нагрузку.';
      opponent.privateBrief += ' Приоритет — полный объём; ранее согласованная работа оценивается в 27.';
      opponent.interests[1]!.text = 'Выполнить полный объём с доступными ресурсами.';
      for (const c of opponent.utility.pairs[0]!.cells) if (c.valueIds[0] === 'full') c.utility += 8;
      d.facts.find(f => f.id === 'helper-available')!.text = 'Подходящий помощник доступен на 6 часов; сотрудник заинтересован в выполнении полного объёма.';
    }
    if (settings.topic === 'reprioritize') {
      d.title = 'Переприоритизация работы'; d.topic = 'Переприоритизация без помощника';
      d.publicBrief = 'Нужно пересогласовать объём и срок. Доступно 2 часа в день; помощника нет, перенос отчёта можно обсудить. Срочность менее ценна, цель игрока остаётся 45. Вымышленная ситуация.';
      d.constraints.push({ id: 'no-helper', kind: 'allowed_values', issueId: 'HELP', valueIds: ['0'],
        reasonCode: 'HELP_UNAVAILABLE', explanationFactId: 'no-helper-fact' });
      d.facts.push({ id: 'no-helper-fact', ownerId: 'manager', text: 'Помощник для этой задачи недоступен.', visibility: 'public',
        kind: 'constraint', topicId: 'resources', interestId: null, issueIds: ['HELP'], relatedFactIds: [], disclosure: [] });
      d.facts.find(f => f.id === 'helper-available')!.text = 'Помощник недоступен; потребуется пересогласовать срок или объём.';
      for (const c of d.participants[0].utility.pairs[0]!.cells) if (c.valueIds[1] === '2') c.utility -= 10;
      d.evaluation.constraintIds.push('no-helper');
    }
  }
  return d;
}

function witness(d: ScenarioDefinition, terms: Package, strategy: number): CanonicalAction[] | null {
  let state = createInitialState(d, { sessionId: 'config-proof', scenarioVersionId: 'config-proof' });
  const actions: CanonicalAction[] = [];
  const play = (a: CanonicalAction) => {
    if (actions.length >= LIMITS.turns) return false;
    const before = projectPlayer(d, state);
    if (!guidedActions(before).kinds.some(kind => kind === a.kind)) return false;
    const r = transition(d, state, { requestId: 'proof-' + actions.length, expectedRevision: state.revision, action: a });
    if (!r.ok) return false;
    // Also prove generic presentation covers these actual moves and disclosures.
    renderTurn('00000000-0000-4000-8000-' + String(actions.length).padStart(12, '0'), a, r.events, before, r.public);
    state = r.state; actions.push(a); return true;
  };
  const publicFact = d.acknowledgementTargets.find(t => state.knownFactIds.includes(t.factId))!;
  const topics = strategy ? [...d.topics].reverse() : d.topics;
  if (!strategy && !play(action('acknowledge', publicFact.factId))) return null;
  for (const t of topics) if (!play(action('question', t.id))) return null;
  if (strategy && !play(action('acknowledge', publicFact.factId))) return null;
  // Revisit only unanswered disclosure opportunities after trust has risen.
  for (const t of topics) if (state.turnNumber < 6 && d.facts.some(f => f.visibility === 'hidden' && f.interestId !== null
    && f.topicId === t.id && !state.knownFactIds.includes(f.id))) {
    if (!play(action('question', t.id))) return null;
  }
  const bindings = d.arguments.filter(a => a.factIds.every(id => state.knownFactIds.includes(id)) && matchesPredicate(terms, a.condition));
  for (const a of strategy ? [...bindings].reverse() : bindings) {
    if (state.turnNumber >= 7) break;
    if (!play(action('argument', a.id))) return null;
  }
  for (const t of d.acknowledgementTargets) {
    if (state.turnNumber >= 7) break;
    if (state.knownFactIds.includes(t.factId) && !state.earnedEventKeys.includes('ack:' + t.factId)) {
      if (!play(action('acknowledge', t.factId))) return null;
    }
  }
  if (!play(action('offer', terms))) return null;
  return state.outcome && ['MUTUAL_GAIN', 'ACCEPTABLE_PARTIAL'].includes(state.outcome.family) ? actions : null;
}

export function compileSettings(input: unknown): Compiled {
  const parsed = SettingsSchema.safeParse(input);
  if (!parsed.success) return envelope([issue('Неизвестные поля или значения настроек. Используйте предложенные варианты.', ['sphere'])]);
  const settings = parsed.data;
  const problems: Issue[] = [];
  for (const control of CONTROLS) {
    if (!control.options.some(o => o.id === settings[control.field] && (!o.sphere || o.sphere === settings.sphere))) {
      problems.push(issue('Выберите «' + control.label + '» для выбранной сферы.', [control.field]));
    }
  }
  if (problems.length) return envelope(problems);
  const d = deriveDefinition(settings);
  const semantic = validateScenario(d);
  if (!semantic.valid) {
    const unreachable = semantic.errors.some(e => ['UNREACHABLE_TARGET','INSUFFICIENT_RATIONAL_PACKAGES'].includes(e.code));
    return envelope([issue(unreachable
      ? 'При этих ресурсах, полномочиях и целях нет двух приемлемых пакетов с достижимой целью игрока. Измените тему, роль или цели; значения не были исправлены.'
      : 'Данные сочетания не прошли проверку связности условий. Выберите другое сочетание; публикация остановлена.')]);
  }
  const rational = semantic.coverage.packages.filter(p => p.individuallyRational)
    .sort((a, b) => b.playerUtility - a.playerUtility || a.index - b.index);
  const used = new Set<string>();
  for (let strategy = 0; strategy < LIMITS.templates; strategy++) {
    for (const row of rational.slice(0, LIMITS.offersPerTemplate)) {
      if (used.has(row.key) || (strategy === 0 && !row.playerTargetReached)) continue;
      const actions = witness(d, row.terms, strategy);
      if (actions) { d.validation.witnessTraces.push({ id: 'configured-path-' + strategy, actions }); used.add(packageKey(d, row.terms)); break; }
    }
  }
  if (d.validation.witnessTraces.length !== 2) return envelope([issue(
    'Не удалось подтвердить два разных приемлемых пути за 8 ходов, включая полную цель. Попробуйте меньшую сложность, другой тон, роль или цели.',
    ['difficulty', 'tone', 'opponentRole', 'opponentGoals'])]);
  const initial = createInitialState(d, { sessionId: 'exit-proof', scenarioVersionId: 'exit-proof' });
  const exit = transition(d, initial, { requestId: 'exit', expectedRevision: 0, action: action('walk_away') });
  if (!exit.ok || exit.state.outcome?.family !== 'NO_AGREEMENT') return envelope([issue('Путь выхода без соглашения недоступен.')]);
  // Domain semantic validation replays the exact saved traces through the same engine.
  const verified = validateScenario(d);
  if (!verified.valid) return envelope([issue('Проверка сохранённых путей завершилась отказом. Выберите другое сочетание.')]);
  return envelope([], verified.scenario);
}
