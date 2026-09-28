import { useEffect, useRef, useState } from 'react';
import { CONTROLS, DraftSchema, ContextPublicationSchema } from '@arena/contracts/context-config';
import type { Draft, Settings, ContextPublication } from '@arena/contracts/context-config';
import type { CatalogReference } from '@arena/contracts/catalog';
import { errorMessage, request } from './api';

export function ContextAdmin({ start, preview }: { start: (id: string) => void; preview: (p: CatalogReference) => React.ReactNode }) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [showPreview, setShowPreview] = useState(false);
  const [approved, setApproved] = useState(false);
  const [published, setPublished] = useState<ContextPublication | null>(null);
  const lock = useRef(false);
  const pending = useRef<{ key: string; body: object } | null>(null);
  async function run(label: string, work: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(label); setError('');
    try { await work(); } catch (e) { setError(errorMessage(e)); }
    finally { lock.current = false; setBusy(''); }
  }
  function acceptDraft(value: Draft) { setDraft(value); setSettings(value.settings); setDirty(false); setShowPreview(false); setApproved(false); }
  async function restore() {
    if (dirty && !window.confirm('Заменить несохранённый ввод сохранённым черновиком?')) return;
    await run('Загружаем черновик…', async () => {
      acceptDraft(await request('/api/admin/context-draft', DraftSchema));
      setNotice('Сохранённый черновик загружен.'); pending.current = null;
    });
  }
  useEffect(() => { void restore(); }, []);
  function body(operation: string, value: object) {
    const key = operation + JSON.stringify(value);
    if (pending.current?.key !== key) pending.current = { key, body: { ...value, requestId: crypto.randomUUID() } };
    return pending.current.body;
  }
  const binding = (d: Draft) => ({ expectedRevision: d.revision, settingsHash: d.settingsHash });
  async function save() {
    if (!draft || !settings) return;
    await run('Сохраняем черновик…', async () => {
      acceptDraft(await request('/api/admin/context-draft/save', DraftSchema, body('save', { ...binding(draft), settings })));
      pending.current = null; setNotice('Черновик сохранён. Требуется новая проверка.');
    });
  }
  async function validate() {
    if (!draft || dirty) return;
    await run('Проверяем условия и достижимость…', async () => {
      acceptDraft(await request('/api/admin/context-draft/validate', DraftSchema, body('validate', binding(draft))));
      pending.current = null; setNotice('');
    });
  }
  const valid = !dirty && draft?.validation?.status === 'valid';
  async function publish() {
    if (!draft || !valid || !showPreview || !approved || !draft.validation?.candidateHash) return;
    await run('Публикуем проверенную версию…', async () => {
      const result = await request('/api/admin/context-draft/publish', ContextPublicationSchema,
        body('publish', { ...binding(draft), candidateHash: draft.validation!.candidateHash, approved: true }));
      setPublished(result); pending.current = null; setNotice('');
    });
  }
  return <section className="panel context-workspace" aria-labelledby="context-title">
    <h2 id="context-title">Настроить контекст</h2>
    <p>Подбор на основе S1/S2 без AI. Один общий локальный черновик. Опубликованные версии и сыгранные попытки сохраняются отдельно.</p>
    {busy && <p role="status">{busy}</p>}
    {error && <div className="error" role="alert"><p>{error}</p><p>Повторите то же действие или загрузите сохранённый черновик. Несохранённый ввод остаётся в форме.</p></div>}
    {!settings || !draft ? <button disabled={!!busy} onClick={() => void restore()}>Загрузить черновик</button> : <>
      <div className="context-controls">{CONTROLS.map(control => {
        const choices = control.options.filter(o => !o.sphere || o.sphere === settings.sphere);
        const selected = choices.find(o => o.id === settings[control.field]);
        const fieldErrors = !dirty ? draft.validation?.issues.filter(i => i.fields.includes(control.field)) : [];
        return <div className="context-field" key={control.field}>
          <label htmlFor={'config-' + control.field}>{control.label}</label>
          <select id={'config-' + control.field} value={settings[control.field] ?? ''} disabled={!!busy}
            aria-describedby={'help-' + control.field + (fieldErrors?.length ? ' error-' + control.field : '')} aria-invalid={!!fieldErrors?.length || !selected}
            onChange={event => {
              const value = event.target.value;
              setSettings(control.field === 'sphere'
                ? { ...settings, sphere: value as Settings['sphere'], topic: null, opponentRole: null, opponentGoals: null }
                : { ...settings, [control.field]: value || null });
              setDirty(true); setShowPreview(false); setApproved(false); setPublished(null); setNotice(''); setError('');
            }}>
            {!selected && <option value="">Выберите для этой сферы</option>}
            {choices.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
          <p className="hint" id={'help-' + control.field}>{control.help} {selected?.description}</p>
          {!!fieldErrors?.length && <p className="field-error" id={'error-' + control.field}>Проверьте это поле — причина приведена ниже.</p>}
        </div>;
      })}</div>
      {(!settings.topic || !settings.opponentRole || !settings.opponentGoals) && <p className="note">После смены сферы выберите заново тему, роль и цели. Скрытые значения другой сферы не переносятся.</p>}
      {dirty && <p className="note" role="status">Настройки изменены. Предыдущая проверка и предпросмотр больше не действуют. Сохраните черновик и проверьте его заново.</p>}
      <div className="button-row">
        <button disabled={!!busy || !dirty} onClick={() => void save()}>Сохранить черновик</button>
        <button disabled={!!busy} onClick={() => void restore()}>Загрузить сохранённый черновик</button>
        <button className="primary" disabled={!!busy || dirty} onClick={() => void validate()}>Подобрать и проверить сценарий</button>
      </div>
      {notice && <p role="status">{notice}</p>}
      {!dirty && draft.validation && <div className={valid ? 'success' : 'error'} role={valid ? 'status' : 'alert'}>
        <p>{valid ? 'Сценарий проверен.' : 'Настройки несовместимы.'} {draft.validation.summary}</p>
        {!valid && <ul>{draft.validation.issues.map((i, n) => <li key={n}>{i.message}</li>)}</ul>}
      </div>}
      {valid && <button disabled={!!busy} onClick={() => { setShowPreview(true); setApproved(false); }}>Предпросмотр</button>}
      {valid && showPreview && draft.validation?.preview && <section className="context-preview" aria-label="Предпросмотр сценария">
        <h3>Эффективные настройки</h3>
        <dl className="properties">{CONTROLS.map(c => <div key={c.field}><dt>{c.label}</dt><dd>{c.options.find(o => o.id === settings[c.field])?.label}</dd></div>)}</dl>
        <h3>Брифинг игрока</h3>{preview(draft.validation.preview)}
        <p className="hint">Это брифинг, который увидит игрок. Проверьте цель, единицы и условия перед публикацией.</p>
        <label className="approval"><input type="checkbox" checked={approved} disabled={!!busy} onChange={e => setApproved(e.target.checked)} /> Я проверил(а) настройки и брифинг и одобряю эту версию</label>
        <button className="primary" disabled={!!busy || !approved} onClick={() => void publish()}>Опубликовать</button>
      </section>}
      {published && <div className="success" role="status"><p>Настроенная версия опубликована. Она закреплена для новых попыток.</p>
        <div className="button-row"><button disabled={!!busy} onClick={() => start(published.publication.id)}>Начать настроенные переговоры</button><a href="/">Открыть список ситуаций</a></div></div>}
    </>}
  </section>;
}
