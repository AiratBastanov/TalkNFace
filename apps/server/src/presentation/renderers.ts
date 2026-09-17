import type { CanonicalAction, DomainEvent, Package, PublicProjection } from '@arena/contracts';
import { assertNever } from '@arena/contracts';
import type { BasicResult, GuidedActions, Observation, PublicTurn } from '@arena/contracts/g2';
import { BasicResultSchema, PublicTurnSchema } from '@arena/contracts/g2';

export function renderTerms(terms: Package, projection: PublicProjection): string {
  return projection.scenario.issues.map(issue => {
    const term = terms.find(item => item.issueId === issue.id);
    const value = issue.values.find(item => item.id === term?.valueId);
    if (!value) throw new Error('Cannot render unknown public term');
    return `${issue.label}: ${value.label}${value.quantity === null ? '' : ' ' + issue.unit}`;
  }).join('; ');
}
const factText = (p: PublicProjection, id: string) => {
  const fact = p.knownFacts.find(item => item.id === id);
  if (!fact) throw new Error('Cannot render an undisclosed fact');
  return fact.text;
};
const argumentText = (p: PublicProjection, id: string) => {
  const argument = p.availableArguments.find(item => item.id === id);
  if (!argument) throw new Error('Cannot render an unavailable argument');
  return argument.label;
};

// Presentation consumes public knowledge only. No private definition or utility table.
export function renderPlayer(action: CanonicalAction, before: PublicProjection): string {
  let text: string;
  switch (action.kind) {
    case 'question': {
      const topic = before.scenario.topics.find(item => item.id === action.primaryTopicId);
      if (!topic) throw new Error('Unknown public topic');
      const questions: Record<string, string> = {
        logistics: 'Можно ли разделить поставку: часть к запуску, остальное позже?',
        payment: 'Какие условия оплаты для вас наиболее важны?',
        authority: 'Какие у вас полномочия по согласованию цены?',
      };
      text = questions[topic.id] ?? `Давайте обсудим тему «${topic.label}».`;
      break;
    }
    case 'acknowledge': text = `Я учитываю следующее: ${factText(before, action.acknowledgementFactId)}`; break;
    case 'argument': text = `Предлагаю ${argumentText(before, action.argumentId).toLocaleLowerCase('ru')}.`; break;
    case 'offer': case 'counter_offer': text = `Предлагаю пакет: ${renderTerms(action.terms, before)}.`; break;
    case 'accept': {
      if (before.activeOffer?.id !== action.offerId) throw new Error('Cannot render a stale acceptance');
      text = `Принимаю ваше предложение: ${renderTerms(before.activeOffer.terms, before)}.`; break;
    }
    case 'pressure': text = action.tone === 'respectful_firm'
      ? 'Если приемлемые условия не найдутся, я выберу свою альтернативу.'
      : 'Требую уступить по условиям.'; break;
    case 'walk_away': text = 'Завершаю переговоры без соглашения и выбираю свою альтернативу.'; break;
    case 'clarification': text = 'Давайте уточним текущую позицию.'; break;
    default: return assertNever(action);
  }
  if (action.kind !== 'acknowledge' && action.acknowledgementFactId) text += ` Я учитываю: ${factText(before, action.acknowledgementFactId)}`;
  if (action.kind !== 'argument' && action.argumentId) text += ` Предлагаю ${argumentText(before, action.argumentId).toLocaleLowerCase('ru')}.`;
  if ((action.kind === 'offer' || action.kind === 'counter_offer') && action.conditionalOn.length) {
    const labels = action.conditionalOn.map(term => {
      const issue = before.scenario.issues.find(item => item.id === term.issueId);
      const value = issue?.values.find(item => item.id === term.valueId);
      if (!issue || !value) throw new Error('Unknown condition');
      return `${issue.label}: ${value.label}`;
    });
    text += ` Встречное условие: ${labels.join('; ')}.`;
  }
  if (action.tone === 'accusatory') text = 'Вы не хотите идти навстречу. ' + text;
  if (action.tone === 'threat') text = 'Если не уступите, я добьюсь неприятностей лично для вас. ' + text;
  if (action.tone === 'respectful_firm' && action.kind !== 'pressure') text = 'Для меня важно договориться на приемлемых условиях. ' + text;
  if (action.contradictsFactId) text += ` Я отрицаю установленный факт: ${factText(before, action.contradictsFactId)}`;
  return text;
}

export function renderOpponent(events: readonly DomainEvent[], after: PublicProjection): string {
  const lines: string[] = [];
  const types = events.map(event => event.payload.type);
  for (const event of events) {
    const p = event.payload;
    switch (p.type) {
      case 'fact_disclosed': lines.push(factText(after, p.factId)); break;
      case 'offer_rejected_physical': lines.push('Этот пакет не выполняет обязательные условия ситуации. Принять его нельзя.'); break;
      case 'offer_rejected_authority': lines.push('Этот пакет выходит за пределы полномочий. Согласовать его нельзя.'); break;
      case 'offer_rejected_aspiration': lines.push('Предложенные условия пока не подходят. Готов обсудить другой пакет.'); break;
      case 'counteroffer_created': {
        // A final-turn counteroffer can immediately close. Never present it as still acceptable.
        lines.push(after.activeOffer?.id === p.offer.id
          ? `Встречное предложение: ${renderTerms(after.activeOffer.terms, after)}.`
          : `В ходе обсуждения предложен пакет: ${renderTerms(p.offer.terms, after)}. Сейчас он закрыт.`);
        break;
      }
      case 'counteroffer_unavailable': lines.push('Сейчас не могу предложить подходящий пакет.'); break;
      case 'agreement_reached': {
        if (!after.agreementOffer) throw new Error('Agreement without public terms');
        lines.push(`Согласовано: ${renderTerms(after.agreementOffer.terms, after)}.`); break;
      }
      case 'tension_warning': lines.push('Личное давление мешает разговору. При следующем таком ходе я прекращу переговоры.'); break;
      case 'tension_repaired': lines.push('Вы признали конкретное ограничение. Продолжим обсуждение по существу.'); break;
      case 'opponent_walkaway': lines.push('Прекращаю переговоры после повторного давления. Соглашения нет.'); break;
      case 'player_walkaway': lines.push('Принято. Завершаем разговор без соглашения.'); break;
      case 'round_limit': lines.push('Доступные ходы закончились. Соглашение не достигнуто.'); break;
      case 'fact_acknowledged': lines.push('Вы учли обозначенное условие.'); break;
      case 'grounded_argument_applied': lines.push('Довод по известной информации принят к обсуждению. Условия сделки ещё нужно согласовать.'); break;
      case 'damaging_tone': if (!types.includes('opponent_walkaway')) lines.push('Прошу обсуждать условия без личных обвинений и угроз.'); break;
      // Deliberately exclude numeric policy events and private outcome payloads.
      case 'action_played': case 'topic_asked': case 'social_state_changed': case 'progress_credit_earned':
      case 'resource_authorized': case 'offer_proposed': case 'offer_closed': case 'active_offer_accepted': break;
      default: assertNever(p);
    }
  }
  if (!lines.length) lines.push(types.includes('topic_asked')
    ? 'Новой информации по этому вопросу сейчас нет. Можно обсудить другие условия.'
    : 'Ваша позиция понятна. Продолжим обсуждать условия.');
  return lines.join('\n');
}

export function observations(events: readonly DomainEvent[], after: PublicProjection): Observation[] {
  const result: Observation[] = [];
  for (const event of events) {
    const add = (ruleId: Observation['ruleId'], text: string) => result.push({ eventId: event.id, turnNumber: event.turnNumber, ruleId, text });
    const p = event.payload;
    switch (p.type) {
      case 'fact_disclosed': add('FACT_DISCLOSED', `Вы получили информацию: ${factText(after, p.factId)}`); break;
      case 'fact_acknowledged': if (p.first) add('FACT_ACKNOWLEDGED', `Вы признали факт: ${factText(after, p.factId)}`); break;
      case 'grounded_argument_applied': if (p.first) add('GROUNDED_ARGUMENT', `Вы использовали известную информацию в аргументе «${argumentText(after, p.argumentId)}».`); break;
      case 'topic_asked': if (!p.first && !events.some(e => e.payload.type === 'fact_disclosed')) add('REPEATED_QUESTION', 'Повтор вопроса не дал новой информации.'); break;
      case 'damaging_tone': add('DAMAGING_TONE', p.effect === 'contradiction' ? 'Вы оспорили установленный факт; это ухудшило отношения.' : 'Личное давление или обвинение усилило напряжение.'); break;
      case 'offer_rejected_physical': add('PHYSICAL_REJECTION', 'Предложение отклонено из-за обязательного ограничения. Ход израсходован.'); break;
      case 'offer_rejected_authority': add('AUTHORITY_REJECTION', 'Предложение отклонено из-за пределов полномочий.'); break;
      case 'offer_rejected_aspiration': add('POSITION_REJECTION', 'Оппонент пока не принял предложенное сочетание условий.'); break;
      case 'counteroffer_created': add('COUNTEROFFER', 'Оппонент предложил другой пакет условий.'); break;
      case 'tension_warning': add('TENSION_WARNING', 'Оппонент предупредил о прекращении разговора при дальнейшем давлении.'); break;
      case 'tension_repaired': add('TENSION_REPAIRED', 'Признание конкретного ограничения сняло предупреждение.'); break;
      case 'agreement_reached':
        add('AGREEMENT', 'Зафиксировано соглашение по точным условиям.');
        if (after.outcome?.family === 'POOR_AGREEMENT') add('BELOW_OWN_BATNA', 'Вы согласовали сделку хуже собственной альтернативы.');
        break;
      case 'player_walkaway': add('PLAYER_WALKAWAY', 'Вы завершили переговоры и сохранили возможность выбрать свою альтернативу.'); break;
      case 'opponent_walkaway': add('OPPONENT_WALKAWAY', 'Повторное давление после предупреждения завершило переговоры.'); break;
      case 'round_limit': add('ROUND_LIMIT', 'Ходы закончились до достижения соглашения.'); break;
      default: break;
    }
  }
  return result;
}
export function renderTurn(requestId: string, action: CanonicalAction, events: DomainEvent[], before: PublicProjection, after: PublicProjection): PublicTurn {
  return PublicTurnSchema.parse({ requestId, turnNumber: after.turnNumber, playerText: renderPlayer(action, before),
    opponentText: renderOpponent(events, after), observations: observations(events, after) });
}
export function guidedActions(p: PublicProjection): GuidedActions {
  if (p.outcome) return { kinds: [], questionTones: [], pressureTones: [] };
  return { kinds: ['question', ...(p.acknowledgementFactIds.length ? ['acknowledge' as const] : []),
    ...(p.availableArguments.length ? ['argument' as const] : []), 'offer', ...(p.activeOffer ? ['accept' as const] : []), 'pressure', 'walk_away'],
  questionTones: ['neutral', 'respectful_firm', 'accusatory'], pressureTones: ['respectful_firm', 'accusatory', 'threat'] };
}
export function basicResult(p: PublicProjection, transcript: PublicTurn[]): BasicResult | null {
  const outcome = p.outcome;
  if (!outcome) return null;
  const headlines = { MUTUAL_GAIN: 'Цель достигнута', ACCEPTABLE_PARTIAL: 'Есть соглашение, но целевая граница не достигнута',
    POOR_AGREEMENT: 'Сделка хуже вашей альтернативы', NO_AGREEMENT: 'Соглашение не достигнуто' };
  const reasons = { agreed: 'Стороны согласовали полный пакет условий.', player_walkaway: 'Вы завершили переговоры по своему решению.',
    opponent_walkaway: 'Оппонент завершил переговоры после давления вслед за предупреждением.', round_limit: 'Доступные ходы закончились.' };
  return BasicResultSchema.parse({ family: outcome.family, terminalReason: outcome.terminalReason,
    headline: headlines[outcome.family], terminalExplanation: reasons[outcome.terminalReason],
    goals: p.scenario.player.goals.map(goal => goal.text), targetReached: outcome.playerUtility !== null && outcome.playerUtility >= outcome.playerTarget,
    batnaComparison: outcome.playerUtility === null ? 'not_exercised' : outcome.playerUtility < outcome.playerBatna ? 'below' : outcome.playerUtility === outcome.playerBatna ? 'equal' : 'above',
    playerUtility: outcome.playerUtility, playerBatna: outcome.playerBatna, playerTarget: outcome.playerTarget,
    agreementOffer: p.agreementOffer, observations: transcript.flatMap(turn => turn.observations) });
}
