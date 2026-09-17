import type { ScenarioDefinition } from '@arena/contracts';
import { acknowledge, argument, offer, question, supplyTerms } from './reference-actions.ts';

const prices = [90, 95, 100, 105, 110, 115];
const deliveries = ['all7', 'split40at7_rest14', 'all14'];
const prepays = [0, 30, 50];
const cells = (entries: [string, number][]) => entries.map(([valueId, utility]) => ({ valueId, utility }));

export const S1: ScenarioDefinition = {
  schemaVersion: 1, templateId: 'S1-SUPPLY-LAUNCH', title: 'Закупка к запуску', sphere: 'Промышленные закупки', topic: 'Запуск через семь дней',
  provenance: 'reference', configFingerprint: 'S1-normal-neutral-director-cashflow-v1',
  publicBrief: 'Через 7 дней запускается производство. Не менее 40% партии требуется к запуску, остаток можно получить на день 14. Обсудите цену, поставку и предоплату. Ситуация вымышлена; числа описывают учебную модель.',
  participants: [
    {
      id: 'buyer', party: 'player', label: 'Закупщик', roleId: 'buyer',
      privateBrief: 'Бюджет до 115 тысяч условных единиц, предоплата до 50%. Альтернатива: другой поставщик привезёт всё на день 7 за 115 без предоплаты.',
      initialPosition: 'Нужна выполнимая поставка к запуску в пределах бюджета.',
      goals: [{ id: 'buyer-target', text: 'Достичь учебной полезности не менее 62.', issueIds: ['PRICE', 'DELIVERY', 'PREPAY'] }],
      interests: [{ id: 'buyer-launch', text: 'Запустить производство без задержки и сохранить бюджет.', visibility: 'public', issueIds: ['PRICE', 'DELIVERY', 'PREPAY'] }],
      target: 62, reservation: 55, batna: { description: 'Другой поставщик: 115 / all7 / 0.', utility: 55 },
      utility: { base: 170, unary: [
        { issueId: 'PRICE', cells: prices.map(price => ({ valueId: String(price), utility: -price })) },
        { issueId: 'DELIVERY', cells: cells([['all7', 0], ['split40at7_rest14', -5], ['all14', -20]]) },
        { issueId: 'PREPAY', cells: cells([['0', 0], ['30', -3], ['50', -6]]) },
      ], pairs: [] },
      authority: { allowedValues: [], resources: [] },
    },
    {
      id: 'supplier', party: 'opponent', label: 'Директор продаж поставщика', roleId: 'director',
      privateBrief: 'Срочная логистика стоит дорого. Предоплата обеспечивает закупку сырья. Альтернативный заказ даёт полезность 20.',
      initialPosition: 'Готовы обсудить сочетание цены, сроков и оплаты.',
      goals: [{ id: 'supplier-target', text: 'Сохранить приемлемую доходность и оборотные средства.', issueIds: ['PRICE', 'DELIVERY', 'PREPAY'] }],
      interests: [
        { id: 'supplier-logistics', text: 'Снизить расходы срочной логистики.', visibility: 'hidden', issueIds: ['DELIVERY'] },
        { id: 'supplier-cashflow', text: 'Получить средства на закупку сырья.', visibility: 'hidden', issueIds: ['PREPAY'] },
      ],
      target: 35, reservation: 20, batna: { description: 'Альтернативный заказ.', utility: 20 },
      utility: { base: -80, unary: [
        { issueId: 'PRICE', cells: prices.map(price => ({ valueId: String(price), utility: price })) },
        { issueId: 'DELIVERY', cells: cells([['all7', -24], ['split40at7_rest14', -8], ['all14', 0]]) },
        { issueId: 'PREPAY', cells: cells([['0', 0], ['30', 8], ['50', 20]]) },
      ], pairs: [] },
      authority: { allowedValues: [{ id: 'supplier-price-authority', issueId: 'PRICE', valueIds: prices.map(String), reasonCode: 'PRICE_AUTHORITY_FLOOR', explanationFactId: 'supplier-authority' }], resources: [] },
    },
  ],
  issues: [
    { id: 'PRICE', label: 'Цена за партию', unit: 'тыс. условных единиц', ordered: true, values: prices.map(price => ({ id: String(price), label: String(price), quantity: price })) },
    { id: 'DELIVERY', label: 'Поставка', unit: 'график партии', ordered: false, values: deliveries.map(id => ({ id, label: id === 'all7' ? 'Всё на день 7' : id === 'all14' ? 'Всё на день 14' : '40% на день 7, остаток на день 14', quantity: null })) },
    { id: 'PREPAY', label: 'Предоплата', unit: '%', ordered: true, values: prepays.map(amount => ({ id: String(amount), label: String(amount), quantity: amount })) },
  ],
  constraints: [{ id: 'launch', kind: 'allowed_values', issueId: 'DELIVERY', valueIds: ['all7', 'split40at7_rest14'], reasonCode: 'LAUNCH_MINIMUM_40_PERCENT', explanationFactId: 'launch-bound' }],
  topics: [
    { id: 'logistics', label: 'Возможности поставки', issueIds: ['DELIVERY'] },
    { id: 'payment', label: 'Условия оплаты', issueIds: ['PREPAY'] },
    { id: 'authority', label: 'Полномочия по цене', issueIds: ['PRICE'] },
  ],
  facts: [
    { id: 'launch-bound', ownerId: 'buyer', text: 'Не менее 40% партии требуется на день 7; остаток допустим на день 14.', visibility: 'public', kind: 'constraint', topicId: 'logistics', interestId: null, issueIds: ['DELIVERY'], relatedFactIds: [], disclosure: [] },
    { id: 'logistics-saving', ownerId: 'supplier', text: 'Разделение партии снижает расходы срочной логистики поставщика.', visibility: 'hidden', kind: 'interest', topicId: 'logistics', interestId: 'supplier-logistics', issueIds: ['DELIVERY'], relatedFactIds: [], disclosure: [{ kind: 'question', topicId: 'logistics', gate: 'trust' }] },
    { id: 'cashflow-need', ownerId: 'supplier', text: 'Предоплата помогает поставщику закупить сырьё для партии.', visibility: 'hidden', kind: 'interest', topicId: 'payment', interestId: 'supplier-cashflow', issueIds: ['PREPAY'], relatedFactIds: [], disclosure: [{ kind: 'question', topicId: 'payment', gate: 'trust' }] },
    { id: 'supplier-authority', ownerId: 'supplier', text: 'Директор вправе согласовать цену от 90 тысяч условных единиц.', visibility: 'hidden', kind: 'authority', topicId: 'authority', interestId: null, issueIds: ['PRICE'], relatedFactIds: [], disclosure: [{ kind: 'question', topicId: 'authority', gate: 'always' }, { kind: 'constraint_explanation', constraintId: 'supplier-price-authority' }] },
  ],
  arguments: [
    { id: 'logistics-argument', label: 'Учесть экономию на разделении партии', factIds: ['logistics-saving'], interestId: 'supplier-logistics', condition: [{ kind: 'eq', issueId: 'DELIVERY', valueId: 'split40at7_rest14' }] },
    { id: 'cashflow-argument', label: 'Учесть предоплату на сырьё', factIds: ['cashflow-need'], interestId: 'supplier-cashflow', condition: [{ kind: 'eq', issueId: 'PREPAY', valueId: '50' }] },
  ],
  acknowledgementTargets: ['launch-bound', 'logistics-saving', 'cashflow-need', 'supplier-authority'].map(factId => ({ factId, countsAsConstraint: true })),
  policy: { difficulty: 'normal', tone: 'neutral', maxTurns: 8, policyVersion: 'training-policy-v1' },
  evaluation: { rubricVersion: 'training-rubric-v1', goalIds: ['buyer-target', 'supplier-target'], interestIds: ['buyer-launch', 'supplier-logistics', 'supplier-cashflow'], constraintIds: ['launch'] },
  validation: { witnessTraces: [
    { id: 's1-interest-exchange', actions: [question('logistics'), question('payment'), acknowledge('cashflow-need'), argument('logistics-argument'), offer(supplyTerms(95, 'split40at7_rest14', 50))] },
    { id: 's1-urgent-partial', actions: [question('logistics'), question('payment'), acknowledge('logistics-saving'), argument('logistics-argument'), acknowledge('cashflow-need'), argument('cashflow-argument'), offer(supplyTerms(105, 'all7', 50))] },
  ] },
};
