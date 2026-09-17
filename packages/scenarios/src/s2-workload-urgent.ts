import type { ScenarioDefinition } from '@arena/contracts';
import { acknowledge, argument, offer, question, workloadTerms } from './reference-actions.ts';

const cells = (entries: [string, number][]) => entries.map(([valueId, utility]) => ({ valueId, utility }));
const pairCells = (entries: [string, string, number][]) => entries.map(([a, b, utility]): { valueIds: [string, string]; utility: number } => ({ valueIds: [a, b], utility }));
const zeros = (issueId: string, values: string[]) => ({ issueId, cells: values.map(valueId => ({ valueId, utility: 0 })) });

export const S2: ScenarioDefinition = {
  schemaVersion: 1, templateId: 'S2-WORKLOAD-URGENT', title: 'Срочная задача и нагрузка', sphere: 'Управление командой', topic: 'Согласование срочного проекта',
  provenance: 'reference', configFingerprint: 'S2-normal-neutral-specialist-protect-load-v1',
  publicBrief: 'Срочный проект конкурирует с согласованной работой сотрудника. Доступно 2 часа в день, сверхурочной работы нет. Core требует 8 часов, full — 16. Обсудите объём, срок и ресурсы. Это вымышленная учебная ситуация.',
  participants: [
    {
      id: 'manager', party: 'player', label: 'Руководитель', roleId: 'manager',
      privateBrief: 'Вы можете выделить помощника и разрешить перенос отчёта. Альтернатива: внешняя группа выполнит core за 5 дней с учебной полезностью 25.', initialPosition: 'Нужно согласовать выполнимый объём и срок.',
      goals: [{ id: 'manager-target', text: 'Достичь учебной полезности не менее 45.', issueIds: ['SCOPE', 'DEADLINE', 'HELP', 'DEFER_REPORT'] }],
      interests: [{ id: 'manager-delivery', text: 'Выполнить проект и сохранить рабочие отношения.', visibility: 'public', issueIds: ['SCOPE', 'DEADLINE', 'HELP', 'DEFER_REPORT'] }],
      target: 45, reservation: 25, batna: { description: 'Внешняя группа: core за 5 дней.', utility: 25 },
      utility: { base: 0, unary: [zeros('SCOPE', ['core', 'full']), zeros('DEADLINE', ['2', '5']), { issueId: 'HELP', cells: cells([['0', 0], ['1', -8]]) }, { issueId: 'DEFER_REPORT', cells: cells([['0', 0], ['1', -10]]) }],
        pairs: [{ issueIds: ['SCOPE', 'DEADLINE'], cells: pairCells([['core', '2', 40], ['core', '5', 20], ['full', '2', 65], ['full', '5', 45]]) }] },
      authority: { allowedValues: [], resources: [] },
    },
    {
      id: 'employee', party: 'opponent', label: 'Специалист', roleId: 'specialist',
      privateBrief: 'Отчёт можно перенести. Есть подходящий помощник на 6 часов, но специалист не назначает его сам. Важно сохранить выполнимость ранее данных обязательств и самостоятельность.', initialPosition: 'Готов обсудить выполнимый план с учётом согласованной нагрузки.',
      goals: [{ id: 'employee-target', text: 'Согласовать выполнимую нагрузку и не сорвать обязательства.', issueIds: ['SCOPE', 'DEADLINE', 'HELP', 'DEFER_REPORT'] }],
      interests: [
        { id: 'employee-priorities', text: 'Сохранить согласованные обязательства.', visibility: 'hidden', issueIds: ['DEFER_REPORT'] },
        { id: 'employee-load', text: 'Сохранить самостоятельность и выполнимую нагрузку.', visibility: 'hidden', issueIds: ['SCOPE', 'HELP'] },
      ],
      target: 40, reservation: 25, batna: { description: 'Продолжить ранее согласованную работу.', utility: 25 },
      utility: { base: 50, unary: [zeros('SCOPE', ['core', 'full']), { issueId: 'DEADLINE', cells: cells([['2', -10], ['5', 0]]) }, zeros('HELP', ['0', '1']), { issueId: 'DEFER_REPORT', cells: cells([['0', 0], ['1', 10]]) }],
        pairs: [{ issueIds: ['SCOPE', 'HELP'], cells: pairCells([['core', '0', -16], ['core', '1', -4], ['full', '0', -32], ['full', '1', -20]]) }] },
      authority: { allowedValues: [], resources: [{ id: 'helper-authorization', reasonCode: 'HELP_REQUIRES_MANAGER_RESOURCE', explanationFactId: 'helper-authority', proposalRequiresAuthorization: true,
        requiredWhen: [{ kind: 'eq', issueId: 'HELP', valueId: '1' }], grantWhen: [{ kind: 'eq', issueId: 'HELP', valueId: '1' }] }] },
    },
  ],
  issues: [
    { id: 'SCOPE', label: 'Объём', unit: 'часов работы', ordered: true, values: [{ id: 'core', label: 'Основной объём', quantity: 8 }, { id: 'full', label: 'Полный объём', quantity: 16 }] },
    { id: 'DEADLINE', label: 'Срок', unit: 'рабочих дней', ordered: true, values: [2, 5].map(days => ({ id: String(days), label: String(days), quantity: days })) },
    { id: 'HELP', label: 'Помощник', unit: '6 часов ресурса', ordered: false, values: [{ id: '0', label: 'Без помощника', quantity: 0 }, { id: '1', label: 'Выделить помощника', quantity: 6 }] },
    { id: 'DEFER_REPORT', label: 'Перенос отчёта', unit: '6 часов ресурса', ordered: false, values: [{ id: '0', label: 'Сохранить срок отчёта', quantity: 0 }, { id: '1', label: 'Перенести отчёт', quantity: 6 }] },
  ],
  constraints: [{ id: 'capacity', kind: 'linear_lte', reasonCode: 'WORK_EXCEEDS_CAPACITY', explanationFactId: 'capacity-bound', bound: 0,
    contributions: [
      { issueId: 'SCOPE', cells: [{ valueId: 'core', amount: 8 }, { valueId: 'full', amount: 16 }] },
      { issueId: 'DEADLINE', cells: [{ valueId: '2', amount: -4 }, { valueId: '5', amount: -10 }] },
      { issueId: 'HELP', cells: [{ valueId: '0', amount: 0 }, { valueId: '1', amount: -6 }] },
      { issueId: 'DEFER_REPORT', cells: [{ valueId: '0', amount: 0 }, { valueId: '1', amount: -6 }] },
    ] }],
  topics: [{ id: 'priorities', label: 'Приоритеты работы', issueIds: ['DEFER_REPORT'] }, { id: 'resources', label: 'Доступные ресурсы', issueIds: ['HELP'] }, { id: 'capacity-topic', label: 'Время и полномочия', issueIds: ['SCOPE', 'DEADLINE', 'HELP'] }],
  facts: [
    { id: 'capacity-bound', ownerId: 'employee', text: 'Доступно 2 часа в день; сверхурочная работа не допускается. Core требует 8 часов, full — 16.', visibility: 'public', kind: 'constraint', topicId: 'capacity-topic', interestId: null, issueIds: ['SCOPE', 'DEADLINE', 'HELP', 'DEFER_REPORT'], relatedFactIds: [], disclosure: [] },
    { id: 'report-deferrable', ownerId: 'employee', text: 'Отчёт можно перенести, освободив 6 часов для проекта.', visibility: 'hidden', kind: 'resource', topicId: 'priorities', interestId: 'employee-priorities', issueIds: ['DEFER_REPORT'], relatedFactIds: ['capacity-bound'], disclosure: [{ kind: 'question', topicId: 'priorities', gate: 'trust' }, { kind: 'opponent_commitment_contains', condition: [{ kind: 'eq', issueId: 'DEFER_REPORT', valueId: '1' }] }] },
    { id: 'helper-available', ownerId: 'employee', text: 'Подходящий помощник доступен на 6 часов работы.', visibility: 'hidden', kind: 'resource', topicId: 'resources', interestId: 'employee-load', issueIds: ['HELP'], relatedFactIds: ['capacity-bound'], disclosure: [{ kind: 'question', topicId: 'resources', gate: 'trust' }, { kind: 'opponent_commitment_contains', condition: [{ kind: 'eq', issueId: 'HELP', valueId: '1' }] }] },
    { id: 'helper-authority', ownerId: 'employee', text: 'Специалист может принять выделенного руководителем помощника, но не назначить его самостоятельно.', visibility: 'hidden', kind: 'authority', topicId: 'capacity-topic', interestId: null, issueIds: ['HELP'], relatedFactIds: [], disclosure: [{ kind: 'question', topicId: 'capacity-topic', gate: 'always' }, { kind: 'constraint_explanation', constraintId: 'helper-authorization' }] },
  ],
  arguments: [
    { id: 'resource-argument', label: 'Связать помощь с выполнимым планом', factIds: ['helper-available'], interestId: 'employee-load', condition: [{ kind: 'eq', issueId: 'HELP', valueId: '1' }] },
    { id: 'priority-argument', label: 'Учесть согласованный перенос отчёта', factIds: ['report-deferrable'], interestId: 'employee-priorities', condition: [{ kind: 'eq', issueId: 'DEFER_REPORT', valueId: '1' }] },
  ],
  acknowledgementTargets: ['capacity-bound', 'report-deferrable', 'helper-available', 'helper-authority'].map(factId => ({ factId, countsAsConstraint: true })),
  policy: { difficulty: 'normal', tone: 'neutral', maxTurns: 8, policyVersion: 'training-policy-v1' },
  evaluation: { rubricVersion: 'training-rubric-v1', goalIds: ['manager-target', 'employee-target'], interestIds: ['manager-delivery', 'employee-priorities', 'employee-load'], constraintIds: ['capacity'] },
  validation: { witnessTraces: [
    { id: 's2-full-resource', actions: [question('priorities'), question('resources'), acknowledge('report-deferrable'), argument('resource-argument'), offer(workloadTerms('full', 2, 1, 1))] },
    { id: 's2-reduced-scope', actions: [question('resources'), acknowledge('helper-available'), offer(workloadTerms('core', 2, 1, 0))] },
  ] },
};
