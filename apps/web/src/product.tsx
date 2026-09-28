import { useEffect, useRef, useState } from 'react';
import type { PublicProjection } from '@arena/contracts';
import { ResourceIdSchema, SessionViewSchema } from '@arena/contracts/g2';
import type { BasicResult, SessionView } from '@arena/contracts/g2';
import { PublishedCatalogScenarioSchema as PublishedScenarioSchema, ReferenceCatalogSchema,
  PublishedCatalogSchema as ScenarioListSchema, formatIssueValue } from '@arena/contracts/catalog';
import type { PublishedCatalogScenario as PublishedScenario, CatalogReference as ReferencePreview } from '@arena/contracts/catalog';
import { errorMessage, request } from './api';
import { Board, Terms, Transcript } from './board';

export function navigate(path: string, replace = false) {
  if (replace) history.replaceState(null, '', path); else history.pushState(null, '', path);
  window.dispatchEvent(new PopStateEvent('popstate')); window.scrollTo(0, 0);
}
function Link({ to, children }: { to: string; children: React.ReactNode }) {
  return <a href={to} onClick={event => {
    if (!event.ctrlKey && !event.metaKey && !event.shiftKey && event.button === 0) { event.preventDefault(); navigate(to); }
  }}>{children}</a>;
}
function remember(id: string) { try { localStorage.setItem('arena:last-session', id); } catch { /* URL still restores the session. */ } }
function remembered(): string | null { try { return localStorage.getItem('arena:last-session'); } catch { return null; } }
export const sessionPath = (data: SessionView, briefing = false) => `/session/${data.projection.sessionId}${data.result ? '/result' : briefing ? '/briefing' : ''}`;
function IssueList({ scenario }: { scenario: PublicProjection['scenario'] }) {
  return <dl className="issue-list">{scenario.issues.map(issue => <div key={issue.id}>
    <dt>{issue.label} <span className="muted">({issue.unit})</span></dt><dd>{issue.values.map(v => formatIssueValue(issue, v)).join(' · ')}</dd>
  </div>)}</dl>;
}
function Preview({ data }: { data: ReferencePreview }) {
  const s = data.scenario;
  return <>
    <p className="eyebrow">{data.templateId}</p><h2>{s.title}</h2><p>{s.publicBrief}</p>
    <dl className="properties">
      <div><dt>Сфера</dt><dd>{s.sphere}</dd></div><div><dt>Тема</dt><dd>{s.topic}</dd></div>
      <div><dt>Игрок</dt><dd>{s.player.label}</dd></div><div><dt>Оппонент</dt><dd>{s.opponent.label}</dd></div>
      <div><dt>Сложность</dt><dd>{({ beginner: 'Начальная', normal: 'Обычная', advanced: 'Повышенная' })[data.difficulty]}</dd></div>
      <div><dt>Тон оппонента</dt><dd>{({ neutral: 'Нейтральный', friendly: 'Дружелюбный', skeptical: 'Скептический' })[data.tone]}</dd></div>
    </dl>
    <h3>Цель игрока</h3>{s.player.goals.map(goal => <p key={goal.id}>{goal.text}</p>)}
    <h3>Условия и ограничения</h3><p>{s.player.privateBrief}</p>
    <ul>{data.publicFacts.map(fact => <li key={fact.id}>{fact.text}</li>)}</ul>
    <h3>Предмет переговоров</h3><IssueList scenario={s} />
  </>;
}
function Briefing({ data }: { data: SessionView }) {
  const p = data.projection;
  return <article className="panel reading">
    <p className="eyebrow">Брифинг · {p.maxTurns} ходов</p><h1>{p.scenario.title}</h1><p className="lead">{p.scenario.publicBrief}</p>
    <h2>Ваша роль — {p.scenario.player.label.toLocaleLowerCase('ru')}</h2>
    <p>На другой стороне — {p.scenario.opponent.label.toLocaleLowerCase('ru')}.</p><p>{p.scenario.player.initialPosition}</p>
    <h2>Цель и ваша альтернатива</h2>{p.scenario.player.goals.map(goal => <p key={goal.id}>{goal.text}</p>)}
    <p>{p.scenario.player.privateBrief}</p>
    <p className="note">Согласуйте весь пакет: {p.scenario.issues.map(issue => issue.label.toLocaleLowerCase('ru')).join(', ')}. Учитывайте обязательные ограничения и свою альтернативу. Учебная полезность вашей альтернативы — {p.scenario.player.batna.utility}; целевая граница — {p.scenario.player.target}.</p>
    <h2>Что можно согласовать</h2><IssueList scenario={p.scenario} />
    <h2>Обязательные условия</h2><ul>{p.knownFacts.map(fact => <li key={fact.id}>{fact.text}</li>)}</ul>
    <h2>Как вести разговор</h2><p>Выбирайте действие, тему и тон. Узнавайте условия, признавайте факты, приводите аргументы или сразу предлагайте пакет. Предложение, принятие и выход требуют подтверждения. Каждый отправленный ход приближает завершение: всего {p.maxTurns}.</p>
    <p>В этом демо вы выбираете смысл реплики через элементы управления. Произвольный текст не вводится.</p>
    <button className="primary" onClick={() => navigate(sessionPath(data))}>Начать переговоры</button>
  </article>;
}
function Result({ data, replay, busy }: { data: SessionView; replay(): void; busy: boolean }) {
  const result = data.result as BasicResult;
  const comparisons = { above: 'Выше вашей альтернативы', equal: 'На уровне вашей альтернативы', below: 'Хуже вашей альтернативы', not_exercised: 'Сделки нет; ваша альтернатива остаётся доступной' };
  return <><article className="panel reading result" data-testid="result">
    <p className="eyebrow">Результат переговоров · {data.projection.turnNumber} ходов</p><h1>{result.headline}</h1><p className="lead">{result.terminalExplanation}</p>
    {result.agreementOffer && <><h2>Согласованные условия</h2><Terms terms={result.agreementOffer.terms} p={data.projection.scenario} /></>}
    <h2>Ваша цель</h2>{result.goals.map(goal => <p key={goal}>{goal}</p>)}<p>{result.targetReached ? 'Целевая граница достигнута.' : 'Целевая граница не достигнута.'}</p>
    <p className="note">{comparisons[result.batnaComparison]}.{result.playerUtility !== null && <> Учебная полезность сделки: {result.playerUtility}; ваша альтернатива: {result.playerBatna}; цель: {result.playerTarget}.</>}</p>
    <h2>Что повлияло на результат</h2><p className="hint">Наблюдения основаны на событиях этой попытки. Это базовый разбор без общего балла.</p>
    <ol className="observations">{result.observations.map(item => <li key={`${item.eventId}-${item.ruleId}`}><p>{item.text}</p><a href={`#turn-${item.turnNumber}`}>Ход {item.turnNumber} — открыть в диалоге</a></li>)}</ol>
    <button className="primary" disabled={busy} onClick={replay}>Повторить ту же ситуацию</button><p className="hint">Новая попытка начнётся с чистого состояния на той же версии сценария.</p>
  </article><div className="reading"><Transcript data={data} /></div></>;
}
export function Product() {
  const [path, setPath] = useState(location.pathname);
  const [version, setVersion] = useState(0);
  const [scenarios, setScenarios] = useState<PublishedScenario[]>([]);
  const [references, setReferences] = useState<ReferencePreview[]>([]);
  const [selectedReference, setSelectedReference] = useState('S1-SUPPLY-LAUNCH');
  const preview = references.find(item => item.templateId === selectedReference);
  const referenceKey = preview?.templateId.split('-')[0]?.toLowerCase();
  const [published, setPublished] = useState<PublishedScenario | null>(null);
  const [session, setSession] = useState<SessionView | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const lock = useRef(false);
  const match = /^\/session\/([^/]+)(\/briefing|\/result)?$/.exec(path);
  const id = match?.[1];
  useEffect(() => {
    const pop = () => setPath(location.pathname); window.addEventListener('popstate', pop);
    return () => window.removeEventListener('popstate', pop);
  }, []);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(''); setSession(null);
    (async () => {
      try {
        if (path === '/admin') {
          const value = await request('/api/reference-scenarios', ReferenceCatalogSchema);
          if (active) { setReferences(value); setPublished(null); }
        } else if (path === '/') {
          const value = await request('/api/scenarios', ScenarioListSchema); if (active) setScenarios(value);
        } else if (id && ResourceIdSchema.safeParse(id).success) {
          const value = await request(`/api/sessions/${id}`, SessionViewSchema);
          if (active) { setSession(value); remember(id); if (value.result && !path.endsWith('/result')) navigate(sessionPath(value), true); }
        } else throw new Error('Страница не найдена. Откройте список ситуаций.');
      } catch (caught) { if (active) setError(errorMessage(caught)); }
      finally { if (active) setLoading(false); }
    })();
    return () => { active = false; };
  }, [path, version, id]);
  async function perform(work: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError('');
    try { await work(); } catch (caught) { setError(errorMessage(caught)); }
    finally { lock.current = false; setBusy(false); }
  }
  const start = (scenarioVersionId: string) => void perform(async () => {
    const value = await request('/api/sessions', SessionViewSchema, { scenarioVersionId }); remember(value.projection.sessionId); navigate(sessionPath(value, true));
  });
  const last = remembered();
  return <>
    <header className="site-header"><div className="header-inner"><Link to="/">Арена переговоров</Link><nav aria-label="Основная навигация"><Link to="/">Игрок</Link><Link to="/admin">Администратор</Link></nav></div></header>
    <div className="mode-banner">Демо без AI <span>Переговоры работают без внешнего API и ключей</span></div>
    <main>
      {error && <div className="error" role="alert"><p>{error}</p><button disabled={busy} onClick={() => setVersion(v => v + 1)}>Обновить данные</button> <Link to="/">К ситуациям</Link></div>}
      {loading ? <p role="status">Загружаем ситуацию…</p> : path === '/admin' && preview ? <>
        <div className="page-heading"><div><p className="eyebrow">Администратор · эталонный сценарий</p><h1>Подготовить тренировку</h1></div></div>
        <div className="button-row reading" role="group" aria-label="Эталонные сценарии">{references.map(item => <button key={item.templateId}
          disabled={busy} aria-pressed={item.templateId === selectedReference} onClick={() => { setSelectedReference(item.templateId); setPublished(null); }}>
          {item.templateId.split('-')[0]} — {item.scenario.title}</button>)}</div>
        <article className="panel reading"><Preview data={preview} /><p className="note">Это проверенная конфигурация {referenceKey?.toUpperCase()}. Публикация закрепит её для новых попыток. Повторная публикация тех же данных использует ту же версию.</p>
          <button className="primary" disabled={busy} onClick={() => void perform(async () => setPublished(await request(`/api/admin/reference-scenarios/${referenceKey}/publish`, PublishedScenarioSchema, {})))}>{busy ? 'Публикуем…' : `Опубликовать ${referenceKey?.toUpperCase()}`}</button>
          {published && <div className="success" role="status"><p>Версия опубликована. Ситуация доступна игроку.</p><div className="button-row"><Link to="/">Открыть вход игрока</Link><button disabled={busy} onClick={() => start(published.id)}>Открыть брифинг</button></div></div>}
        </article></> : path === '/' ? <>
          <p className="eyebrow">Практика деловых переговоров</p><h1>Выберите ситуацию</h1><p className="lead">Выясните интересы, согласуйте условия и посмотрите, к чему привела ваша стратегия.</p>
          {last && ResourceIdSchema.safeParse(last).success && <p><Link to={`/session/${last}`}>Вернуться к последней попытке</Link></p>}
          {!scenarios.length && <section className="panel"><h2>Пока нет опубликованных ситуаций</h2><p>Откройте эталонный сценарий и опубликуйте его, чтобы начать тренировку.</p><Link to="/admin">Открыть экран администратора</Link></section>}
          <div className="scenario-cards">{scenarios.map(item => <article className="panel" key={item.id}><p className="eyebrow">{item.preview.scenario.sphere} · {item.preview.maxTurns} ходов</p><h2>{item.preview.scenario.title}</h2>
            <p>{item.preview.scenario.publicBrief}</p><p className="muted">Ваша роль: {item.preview.scenario.player.label}</p><button className="primary" disabled={busy} onClick={() => start(item.id)}>Выбрать ситуацию</button></article>)}</div>
        </> : session ? (session.result ? <Result data={session} busy={busy} replay={() => void perform(async () => {
          const value = await request(`/api/sessions/${session.projection.sessionId}/replay`, SessionViewSchema, {}); remember(value.projection.sessionId); navigate(sessionPath(value, true));
        })} /> : path.endsWith('/briefing') ? <Briefing data={session} /> : <Board key={session.projection.sessionId} data={session} onChange={setSession} />) : null}
    </main><footer>Учебная ситуация. Выбор действий и условий определяет результат.</footer>
  </>;
}
