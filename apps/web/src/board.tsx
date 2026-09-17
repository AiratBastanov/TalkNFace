import { useEffect, useRef, useState } from 'react';
import type { CanonicalAction, Package, PublicProjection } from '@arena/contracts';
import { PlayTurnSchema, SessionViewSchema } from '@arena/contracts/g2';
import type { PlayTurnRequest, SessionView } from '@arena/contracts/g2';
import { errorMessage, request, RequestError } from './api';
import { navigate, sessionPath } from './product';

const tones = { neutral: 'Спокойно', respectful_firm: 'Уважительно и твёрдо', accusatory: 'С обвинением', threat: 'Личная угроза' };
const actions = { question: 'Задать вопрос', acknowledge: 'Признать факт', argument: 'Привести аргумент', offer: 'Предложить условия',
  accept: 'Принять предложение', pressure: 'Обозначить границу / давление', walk_away: 'Завершить без сделки' };
type ActionKind = keyof typeof actions;
const social = () => ({ tone: 'neutral' as const, acknowledgementFactId: null, argumentId: null, contradictsFactId: null, evidenceRefs: [] });

export function Terms({ terms, p }: { terms: Package; p: PublicProjection['scenario'] }) {
  return <dl className="terms">{p.issues.map(issue => {
    const value = issue.values.find(item => terms.some(term => term.issueId === issue.id && term.valueId === item.id));
    return <div key={issue.id}><dt>{issue.label}</dt><dd>{value?.label}{value && value.quantity !== null && <> {issue.unit}</>}</dd></div>;
  })}</dl>;
}
export function Transcript({ data }: { data: SessionView }) {
  return <section className="panel dialogue" aria-label="История переговоров">
    <h2>Диалог</h2><div className="message opponent"><strong>{data.projection.scenario.opponent.label}</strong><p>{data.projection.scenario.opponent.initialPosition}</p></div>
    {data.transcript.map(turn => <article className="turn" id={`turn-${turn.turnNumber}`} key={turn.turnNumber} data-testid="turn">
      <p className="turn-label">Ход {turn.turnNumber}</p>
      <div className="message player"><strong>Вы</strong><p>{turn.playerText}</p></div>
      <div className="message opponent"><strong>Оппонент</strong><p>{turn.opponentText}</p></div>
    </article>)}
    {!data.transcript.length && <p className="muted">Разговор ещё не начался. Выберите первое действие.</p>}
  </section>;
}
const pendingKey = (id: string) => `arena:pending:${id}`;
function readPending(id: string): PlayTurnRequest | null {
  try {
    const saved = sessionStorage.getItem(pendingKey(id));
    const parsed = PlayTurnSchema.safeParse(saved ? JSON.parse(saved) : null);
    return parsed.success ? parsed.data : null;
  } catch { return null; }
}
export function Board({ data, onChange }: { data: SessionView; onChange(data: SessionView): void }) {
  const p = data.projection;
  const [kind, setKind] = useState<ActionKind>('question');
  const [topic, setTopic] = useState(p.scenario.topics[0]?.id ?? '');
  const [tone, setTone] = useState<CanonicalAction['tone']>('neutral');
  const [fact, setFact] = useState('');
  const [argument, setArgument] = useState('');
  const [values, setValues] = useState<Record<string, string>>({});
  const [confirmation, setConfirmation] = useState<CanonicalAction | null>(null);
  const [pending, setPending] = useState<PlayTurnRequest | null>(() => readPending(p.sessionId));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const lock = useRef(false);
  const confirmationTitle = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (confirmation) confirmationTitle.current?.focus(); }, [confirmation]);
  const choose = (next: ActionKind) => {
    setKind(next); setConfirmation(null); setError(''); setTone(next === 'pressure' ? 'respectful_firm' : 'neutral');
  };
  async function submit(action: CanonicalAction, retry?: PlayTurnRequest) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError('');
    const command = retry ?? { requestId: crypto.randomUUID(), expectedRevision: p.revision, action };
    setPending(command);
    try { sessionStorage.setItem(pendingKey(p.sessionId), JSON.stringify(command)); } catch { /* Retry remains in component memory. */ }
    const clearPending = () => { setPending(null); try { sessionStorage.removeItem(pendingKey(p.sessionId)); } catch { /* Best effort. */ } };
    try {
      const updated = await request(`/api/sessions/${p.sessionId}/turns`, SessionViewSchema, command);
      clearPending(); setConfirmation(null);
      const current = retry ? await request(`/api/sessions/${p.sessionId}`, SessionViewSchema) : updated;
      onChange(current); if (current.result) navigate(sessionPath(current));
    } catch (caught) {
      setError(errorMessage(caught));
      if (caught instanceof RequestError && ['STALE_REVISION', 'IDEMPOTENCY_CONFLICT', 'SESSION_TERMINAL', 'DOMAIN_REJECTED', 'INVALID_REQUEST'].includes(caught.code)) {
        clearPending(); setConfirmation(null);
        try {
          const current = await request(`/api/sessions/${p.sessionId}`, SessionViewSchema);
          onChange(current); if (current.result) navigate(sessionPath(current));
        } catch (refreshError) { setError(errorMessage(refreshError)); }
      }
    } finally { lock.current = false; setBusy(false); }
  }
  function draft(): CanonicalAction | null {
    switch (kind) {
      case 'question': return { ...social(), kind, primaryTopicId: topic, secondaryTopicId: null, tone };
      case 'acknowledge': return fact ? { ...social(), kind, acknowledgementFactId: fact } : null;
      case 'argument': return argument ? { ...social(), kind, argumentId: argument } : null;
      case 'offer': return p.scenario.issues.every(issue => values[issue.id])
        ? { ...social(), kind, terms: p.scenario.issues.map(issue => ({ issueId: issue.id, valueId: values[issue.id]! })), conditionalOn: [] } : null;
      case 'accept': return p.activeOffer ? { ...social(), kind, offerId: p.activeOffer.id } : null;
      case 'pressure': return { ...social(), kind, tone };
      case 'walk_away': return { ...social(), kind };
    }
  }
  const copyTerms = (terms: Package) => { setValues(Object.fromEntries(terms.map(t => [t.issueId, t.valueId]))); choose('offer'); };
  const selected = draft();
  const stance = { calm: 'Спокойный разговор', strained: 'Разговор напряжён', warning: 'Оппонент предупредил о выходе', closed: 'Переговоры завершены' };
  return <>
    <div className="page-heading"><div><p className="eyebrow">{p.scenario.player.label} ↔ {p.scenario.opponent.label}</p><h1>{p.scenario.title}</h1></div>
      <p className="turn-count" data-testid="revision">Ход {p.turnNumber} из {p.maxTurns}</p></div>
    <p className={`stance ${p.stance}`} role="status">{stance[p.stance]}</p>
    <div className="arena-grid"><div className="conversation-column"><Transcript data={data} />
      <section className="panel composer" aria-label="Ваш ход" aria-busy={busy}>
        <h2>Ваш ход</h2>{error && <p className="error" id="action-error" role="alert">{error}</p>}
        {pending && !busy && <div className="note"><p>Результат последней отправки нужно подтвердить. Повтор использует тот же идентификатор хода.</p>
          <button onClick={() => void submit(pending.action, pending)}>Повторить отправку</button></div>}
        <fieldset disabled={busy || pending !== null}><legend className="sr-only">Действие и параметры</legend>
          <label>Что вы хотите сделать?<select value={kind} onChange={event => choose(event.target.value as ActionKind)}>
            {data.actions.kinds.map(k => <option key={k} value={k}>{actions[k]}</option>)}</select></label>
          {!p.availableArguments.length && <p className="hint">Аргументы появятся, когда вы узнаете факты, на которые можно сослаться.</p>}
          {kind === 'question' && <label>Тема вопроса<select value={topic} onChange={event => setTopic(event.target.value)}>
            {p.scenario.topics.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>}
          {(kind === 'question' || kind === 'pressure') && <label>Тон реплики<select value={tone} onChange={event => setTone(event.target.value as CanonicalAction['tone'])}>
            {(kind === 'question' ? data.actions.questionTones : data.actions.pressureTones).map(t => <option key={t} value={t}>{tones[t]}</option>)}</select></label>}
          {kind === 'acknowledge' && <label>Какой факт вы признаёте?<select value={fact} onChange={event => setFact(event.target.value)}>
            <option value="">Выберите известный факт</option>{p.knownFacts.filter(f => p.acknowledgementFactIds.includes(f.id)).map(item => <option key={item.id} value={item.id}>{item.text}</option>)}</select></label>}
          {kind === 'argument' && <label>На что вы хотите сослаться?<select value={argument} onChange={event => setArgument(event.target.value)}>
            <option value="">Выберите аргумент</option>{p.availableArguments.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>}
          {kind === 'offer' && <><p className="hint">Выберите одно значение по каждому условию. Перед отправкой проверьте весь пакет.</p>
            {p.lastUserOffer && <button className="small" onClick={() => copyTerms(p.lastUserOffer!.terms)}>Изменить последнее предложение</button>}
            <div className="offer-fields">{p.scenario.issues.map(issue => <label key={issue.id}>{issue.label} ({issue.unit})
              <select value={values[issue.id] ?? ''} onChange={event => { setValues({ ...values, [issue.id]: event.target.value }); setConfirmation(null); }}>
                <option value="">Выберите значение</option>{issue.values.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}</select></label>)}</div></>}
          {kind === 'accept' && p.activeOffer && <><p>Вы принимаете именно это действующее предложение:</p><Terms terms={p.activeOffer.terms} p={p.scenario} /></>}
          {kind === 'pressure' && <p className="hint">Твёрдо обозначить альтернативу и перейти к личному давлению — разные действия. Выберите намеренно.</p>}
          {kind === 'walk_away' && <p>Вы можете закончить разговор без сделки и выбрать свою альтернативу.</p>}
          {!confirmation && <button className="primary" disabled={!selected} aria-describedby={error ? 'action-error' : undefined} onClick={() => {
            if (!selected) return;
            if (['offer', 'accept', 'walk_away'].includes(selected.kind)) setConfirmation(selected); else void submit(selected);
          }}>{kind === 'offer' ? 'Проверить предложение' : kind === 'accept' ? 'Проверить принятие' : kind === 'walk_away' ? 'Подтвердить выход…' : 'Отправить ход'}</button>}
          {confirmation && <section className="confirmation" aria-label="Подтверждение действия">
            <h3 ref={confirmationTitle} tabIndex={-1}>Проверьте перед отправкой</h3>
            {confirmation.kind === 'offer' && <Terms terms={confirmation.terms} p={p.scenario} />}
            {confirmation.kind === 'accept' && p.activeOffer && <Terms terms={p.activeOffer.terms} p={p.scenario} />}
            {confirmation.kind === 'walk_away' && <p>Переговоры завершатся без соглашения. Эту сессию нельзя будет продолжить.</p>}
            <div className="button-row"><button className="primary" onClick={() => void submit(confirmation)}>
              {confirmation.kind === 'offer' ? 'Отправить предложение' : confirmation.kind === 'accept' ? 'Принять эти условия' : 'Выйти без сделки'}</button>
              <button onClick={() => setConfirmation(null)}>Вернуться к выбору</button></div>
          </section>}
        </fieldset>{busy && <p role="status">Сохраняем ход…</p>}
      </section>
    </div><aside>
      <section className="panel"><h2>Предложение оппонента</h2>{p.activeOffer ? <><Terms terms={p.activeOffer.terms} p={p.scenario} />
        <p className="hint">Действует с хода {p.activeOffer.turnNumber}, пока не заменено или не завершён разговор.</p>
        <div className="button-row"><button disabled={busy || pending !== null} onClick={() => { choose('accept'); setConfirmation({ ...social(), kind: 'accept', offerId: p.activeOffer!.id }); }}>Принять предложение</button>
          <button disabled={busy || pending !== null} onClick={() => copyTerms(p.activeOffer!.terms)}>Изменить эти условия</button></div></> : <p className="muted">Действующего предложения пока нет.</p>}</section>
      <section className="panel"><h2>Известные факты</h2><ul data-testid="known-facts">{p.knownFacts.map(item => <li key={item.id}>{item.text}</li>)}</ul></section>
      <details className="panel"><summary>Ваша цель и условия</summary><p>{p.scenario.player.privateBrief}</p>{p.scenario.player.goals.map(goal => <p key={goal.id}>{goal.text}</p>)}</details>
    </aside></div>
  </>;
}
