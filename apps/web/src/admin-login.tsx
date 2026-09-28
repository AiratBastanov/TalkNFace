import { useRef, useState } from 'react';
import { adminLogin, errorMessage } from './api';

export function AdminLogin({ configured, onSuccess }: { configured: boolean; onSuccess(): void }) {
  const password = useRef<HTMLInputElement>(null);
  const lock = useRef(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  return <section className="panel reading" aria-labelledby="admin-login-title">
    <p className="eyebrow">Администратор</p><h1 id="admin-login-title">Вход администратора</h1>
    <p>Для настройки и публикации тренировок нужен пароль владельца. Играть можно без регистрации.</p>
    {!configured ? <p role="status" className="note">Вход администратора пока не настроен. Владелец должен задать ADMIN_PASSWORD_HASH и перезапустить приложение. Опубликованные ситуации доступны игрокам.</p> :
      <form className="admin-login" onSubmit={event => {
        event.preventDefault(); if (lock.current || !password.current) return;
        lock.current = true; setBusy(true); setError('');
        const value = password.current.value; password.current.value = '';
        void adminLogin(value).then(onSuccess).catch(e => { setError(errorMessage(e)); password.current?.focus(); })
          .finally(() => { lock.current = false; setBusy(false); });
      }}>
        <label htmlFor="admin-password">Пароль администратора</label>
        <input ref={password} id="admin-password" type="password" autoComplete="current-password" required maxLength={256}
          disabled={busy} aria-describedby="admin-password-help" />
        <p id="admin-password-help" className="hint">После выхода или истечения срока доступа потребуется повторный вход. Сохранённые черновики и публикации останутся.</p>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" disabled={busy}>{busy ? 'Проверяем…' : 'Войти'}</button>
      </form>}
    <p><a href="/">Открыть ситуации для игрока</a></p>
  </section>;
}
