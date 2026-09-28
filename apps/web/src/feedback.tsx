import { useEffect, useState } from 'react';
import type { SessionView } from '@arena/contracts/g2';
import { ComparisonSchema, FeedbackReportSchema, PreparationViewSchema } from '@arena/contracts/feedback';
import type { FeedbackComparison, FeedbackEvidence, FeedbackReport, Preparation } from '@arena/contracts/feedback';
import { errorMessage, request } from './api';

const statusText = { passed: 'Выполнено', failed: 'Не выполнено', not_applicable: 'Не применимо', unobservable: 'Не наблюдается' };
export function PreparationForm({ data }: { data: SessionView }) {
  const p = data.projection, [record, setRecord] = useState<Preparation | null>(null);
  const [goal, setGoal] = useState(''), [ack, setAck] = useState(false), [busy, setBusy] = useState(true), [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    request(`/api/sessions/${p.sessionId}/preparation`, PreparationViewSchema)
      .then(value => { if (active) setRecord(value.record); })
      .catch(caught => { if (active) setError(errorMessage(caught)); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [p.sessionId]);
  async function save() {
    setBusy(true); setError('');
    try {
      const value = await request(`/api/sessions/${p.sessionId}/preparation`, PreparationViewSchema, {
        expectedRevision: 0, goal, ownBoundary: p.scenario.player.batna.utility, acknowledgedAlternative: ack,
      });
      setRecord(value.record);
    } catch (caught) { setError(errorMessage(caught)); }
    finally { setBusy(false); }
  }
  return <section aria-label="Подготовка до первого хода" className="note">
    <h2>Зафиксируйте подготовку</h2>
    {record ? <p role="status">Подготовка сохранена: цель ≥ {record.selectedThreshold}, своя альтернатива — {record.ownBoundary}. Запись относится только к этой попытке.</p>
      : p.revision ? <p>Первый ход уже сделан. Дописать подготовку задним числом нельзя.</p>
        : <><p>Выберите цель и подтвердите свою альтернативу. Без этой записи разбор не сможет оценить подготовку и показать общий балл.</p>
          <fieldset disabled={busy}><legend className="sr-only">Ваш явный выбор до старта</legend>
            <label>Моя цель<select value={goal} onChange={e => setGoal(e.target.value)}>
              <option value="">Выберите цель</option>
              <option value="target">Достичь целевой полезности {p.scenario.player.target}</option>
              <option value="batna">Договориться не хуже своей альтернативы {p.scenario.player.batna.utility}</option>
            </select></label>
            <label className="checkbox-label"><input type="checkbox" checked={ack} onChange={e => setAck(e.target.checked)} />
              Я фиксирую свою альтернативу: {p.scenario.player.batna.description} Её полезность — {p.scenario.player.batna.utility}.</label>
            <button disabled={!goal || !ack} onClick={() => void save()}>Сохранить подготовку</button>
          </fieldset></>}
    {busy && <p role="status">Загружаем подготовку…</p>}{error && <p className="error" role="alert">{error}</p>}
  </section>;
}
function EvidenceLink({ item }: { item: FeedbackEvidence }) {
  const target = item.turnNumber ? `turn-${item.turnNumber}` : 'preparation-record';
  return <a href={`#${target}`} onClick={() => {
    const element = document.getElementById(target); element?.focus();
  }}>{item.turnNumber ? `Ход ${item.turnNumber} — открыть сохранённый момент` : 'Открыть запись подготовки'}</a>;
}
function EvidenceDetails({ items }: { items: FeedbackEvidence[] }) {
  return <ul className="feedback-evidence">{items.map(item => <li key={item.id}>
    <p>{item.kind === 'window' ? 'Проверенное окно' : item.kind === 'guided_action' ? 'Сохранённое guided-действие' : item.kind === 'preparation' ? 'Подготовка' : 'Структурное событие'}: {item.description}</p>
    {item.window && <p className="hint">{item.window.from === 0 ? 'До первого хода' : `Ходы ${item.window.from}–${item.window.to}`}; отсутствие действия не является цитатой.</p>}
    {item.quote && <blockquote><p>{item.quote.text}</p><footer>Точная сохранённая фраза из выбранных элементов управления</footer></blockquote>}
    <EvidenceLink item={item} />
  </li>)}</ul>;
}
export function Feedback({ data }: { data: SessionView }) {
  const [report, setReport] = useState<FeedbackReport | null>(null), [error, setError] = useState(''), [load, setLoad] = useState(0);
  const [comparison, setComparison] = useState<FeedbackComparison | null>(null), [compareError, setCompareError] = useState(''), [comparing, setComparing] = useState(false);
  const id = data.projection.sessionId, revision = data.projection.revision;
  useEffect(() => {
    let active = true; setReport(null); setError('');
    request(`/api/sessions/${id}/feedback?revision=${revision}`, FeedbackReportSchema)
      .then(value => { if (active) setReport(value); })
      .catch(caught => { if (active) setError(errorMessage(caught)); });
    return () => { active = false; };
  }, [id, revision, load]);
  async function compare() {
    if (!data.replayOf) return;
    setComparing(true); setCompareError('');
    try { setComparison(await request(`/api/sessions/${id}/feedback/comparison?revision=${revision}&predecessorId=${data.replayOf}`, ComparisonSchema)); }
    catch (caught) { setCompareError(errorMessage(caught)); }
    finally { setComparing(false); }
  }
  return <section className="panel reading feedback" aria-labelledby="feedback-title" data-testid="feedback">
    <h2 id="feedback-title">Разбор действий</h2>
    <p>Полезность сделки описана выше. Здесь оцениваются только записанные действия в учебной модели — не личность и не рейтинг сотрудника.</p>
    {error ? <div className="error" role="alert"><p>Разбор не удалось загрузить. Результат и история попытки сохранены.</p><p>{error}</p>
      <button onClick={() => setLoad(v => v + 1)}>Повторить загрузку разбора</button></div>
      : !report ? <p role="status">Загружаем разбор…</p> : <>
        <p className="process-score" data-testid="process-score">{report.overall.score === null ? 'Недостаточно наблюдений' : `Процесс: ${report.overall.score} из 100`}</p>
        <p>{report.overall.explanation}</p>
        <p className="hint">Применимых проверок: {report.overall.applicableChecks} из 12. Принятых зачётов прогресса: {report.overall.progressCredits}.</p>
        <p id="preparation-record" tabIndex={-1}>{report.preparation
          ? `Подготовка до старта: выбрана цель ≥ ${report.preparation.selectedThreshold}; подтверждена своя альтернатива ${report.preparation.ownBoundary}.`
          : 'Подготовка до старта: явная запись отсутствует. Значения брифинга не доказывают подготовку.'}</p>
        <div className="rubric">{report.dimensions.map(d => <details key={d.id} data-testid={`dimension-${d.id}`}>
          <summary>{d.label} · вес {d.weight} · {d.score === null ? (d.applicable ? 'недостаточно данных' : 'нет оценки') : `${d.score}/100`}</summary>
          <ul>{d.checks.map(c => <li key={c.id} data-testid={`check-${c.id}`}>
            <h3>{c.label}</h3><p className={`check-status ${c.status}`}>{statusText[c.status]}</p><p>{c.explanation}</p>
            <EvidenceDetails items={c.evidenceIds.map(ref => report.evidence.find(e => e.id === ref)!)} />
          </li>)}</ul>
        </details>)}</div>
        <section aria-label="Следующий фокус"><h3>Один следующий фокус</h3>
          {report.suggestions.length ? report.suggestions.map(s => <div key={s.checkId} className="note">
            <p>{s.focus}</p><p><strong>Предложенный вариант:</strong> {s.proposedWording}</p>
            <p className="hint">{s.validation === 'prior_state' ? `Действие проверено на состоянии перед ходом ${s.priorRevision + 1}. ` : ''}{s.disclaimer}</p>
            {s.evidenceIds.map(ref => <p key={ref}><EvidenceLink item={report.evidence.find(e => e.id === ref)!} /></p>)}
          </div>) : <p>Нет подходящей проверенной рекомендации для этой записи. Изучите конкретные действия в разборе.</p>}
        </section>
        <details><summary>Основание расчёта</summary>
          <p>Разбор вычислен сейчас по сохранённой завершённой попытке. Он не дописывает прошлые действия. В guided-режиме фразы получены из элементов управления; понимание свободной речи AI здесь не проверялось.</p>
          <p className="hint">Правила: {report.rubricVersion}. Вычислитель: {report.evaluatorVersion}. Редакция попытки: {report.terminalRevision}.</p>
          <p>Принятые зачёты прогресса:</p><EvidenceDetails items={report.overall.progressEvidenceIds.map(id => report.evidence.find(e => e.id === id)!)} />
          <p className="hint">Для измеримых проверок: 100 × выполнено / применимо. Итог учитывает веса применимых измерений. Отсутствующее обязательное доказательство блокирует общий балл.</p>
        </details>
      </>}
    {data.replayOf && <section className="replay-comparison">
      <h3>Сравнение с предыдущей попыткой</h3>
      <button disabled={comparing} onClick={() => void compare()}>Сравнить с предыдущей попыткой</button>
      {comparing && <p role="status">Загружаем сравнение…</p>}{compareError && <p className="error" role="alert">{compareError}</p>}
      {comparison && <div data-testid="comparison"><p>{comparison.reason}</p>
        <p>Ранее: {comparison.predecessorOutcome.headline}. Сейчас: {comparison.currentOutcome.headline}.</p>
        <p className="hint">Полезность сделки: ранее {comparison.predecessorOutcome.playerUtility ?? 'нет сделки'}, сейчас {comparison.currentOutcome.playerUtility ?? 'нет сделки'}.</p>
        <ul>{comparison.sharedChecks.map(c => <li key={c.id}>{c.label}: {statusText[c.before]} → {statusText[c.after]}</li>)}</ul>
        {!!comparison.excludedChecks.length && <p className="hint">Вне сопоставления: {comparison.excludedChecks.join('; ')}.</p>}
        <a href={`/session/${comparison.predecessorSessionId}/result`}>Открыть исходную попытку</a>
      </div>}
    </section>}
  </section>;
}
