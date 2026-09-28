import { createHash, randomUUID } from 'node:crypto';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import type DatabaseDriver from 'better-sqlite3';
import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { SessionViewSchema } from '@arena/contracts/g2';
import { FeedbackReportSchema } from '@arena/contracts/feedback';
import { productionHarness } from './production.ts';
const Database = createRequire(new URL('../../apps/server/package.json', import.meta.url))('better-sqlite3') as typeof DatabaseDriver;
let server: Awaited<ReturnType<typeof productionHarness>>;
const evidence = { browser: '', cases: [] as string[], negatives: [] as { action: string; status: number }[],
  screenshots: [] as string[], productions: [] as unknown[], cookies: [] as object[], errors: [] as string[] };
test.beforeEach(async ({ browser, page }) => {
  evidence.browser = browser.version(); server = await productionHarness({ label: 'g8-access-' + evidence.cases.length }); await server.start();
  page.on('pageerror', e => evidence.errors.push(e.message));
});
test.afterEach(async ({}, info) => {
  await server.stop(); evidence.productions.push(server.evidence());
  // Logs are checked in memory; no credentials or raw headers enter the receipt.
  for (let i = 1; i <= server.evidence().starts; i++) {
    const log = readFileSync(`.tools/logs/g8-access-${evidence.cases.length}-browser-production-${i}.log`, 'utf8');
    expect(/csrfToken|x-csrf-token|arena_session|scrypt\$|"password"|"cookie"|"authorization"|"state_json"/.test(log)).toBe(false);
  }
  server.cleanup(); if (info.status === 'passed') evidence.cases.push(info.title);
  mkdirSync('.tools', { recursive: true }); writeFileSync('.tools/g8-browser-evidence.json', JSON.stringify(evidence, null, 2));
});
test.afterAll(() => expect(evidence.errors).toEqual([]));
async function screenshot(page: Page, name: string) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
  const path = `.tools/${name}.png`; await page.screenshot({ path }); evidence.screenshots.push(path);
}
async function snapshot(page: Page) {
  const id = /\/session\/([^/]+)/.exec(page.url())![1]!;
  const r = await page.request.get(server.origin + '/api/sessions/' + id); expect(r.status()).toBe(200);
  return SessionViewSchema.parse(await r.json());
}
async function configure(page: Page, family: 'S1' | 'S2') {
  const workspace = page.getByRole('region', { name: 'Настроить контекст' });
  if (family === 'S1') {
    await workspace.getByLabel('Тема', { exact: true }).selectOption('planned');
    await workspace.getByLabel('Цели оппонента', { exact: true }).selectOption('margin');
  } else {
    await workspace.getByLabel('Сфера', { exact: true }).selectOption('team');
    await workspace.getByLabel('Тема', { exact: true }).selectOption('urgent');
    await workspace.getByLabel('Роль оппонента', { exact: true }).selectOption('team_lead');
    await workspace.getByLabel('Цели оппонента', { exact: true }).selectOption('deliver_scope');
    await workspace.getByLabel('Сложность', { exact: true }).selectOption('advanced');
  }
  await workspace.getByLabel('Тон оппонента', { exact: true }).selectOption('friendly');
  await workspace.getByRole('button', { name: 'Сохранить черновик', exact: true }).click();
  await expect(workspace.getByText('Черновик сохранён. Требуется новая проверка.')).toBeVisible();
  await workspace.getByRole('button', { name: 'Подобрать и проверить сценарий' }).click();
  await expect(workspace.getByText(/Сценарий проверен\./)).toBeVisible();
  await workspace.getByRole('button', { name: 'Предпросмотр', exact: true }).click();
  await workspace.getByRole('checkbox', { name: /Я проверил/ }).check();
  await workspace.getByRole('button', { name: 'Опубликовать', exact: true }).click();
  await expect(workspace.getByText(/Настроенная версия опубликована/)).toBeVisible();
}
async function move(page: Page, kind: string, label: string, value: string) {
  const before = await snapshot(page);
  await page.getByLabel('Что вы хотите сделать?').selectOption(kind);
  await page.getByLabel(label).selectOption(value);
  await page.getByRole('button', { name: 'Отправить ход', exact: true }).click();
  await expect(page.getByTestId('turn')).toHaveCount(before.projection.revision + 1);
}
async function negative(action: string, response: { status(): number }, status: number) {
  expect(response.status(), action).toBe(status); evidence.negatives.push({ action, status: response.status() });
}

for (const family of ['S1', 'S2'] as const) test(`G8 ${family}: admin login/configure/publish/logout; player G6/replay/restart and independent browser UUID isolation`, async ({ page, browser }) => {
  await page.setViewportSize({ width: 390, height: 900 }); await page.goto(server.origin + '/admin');
  await expect(page.getByRole('heading', { name: 'Вход администратора' })).toBeVisible();
  await screenshot(page, 'g8-login-' + family);
  const before = (await page.context().cookies(server.origin)).find(c => c.name === 'arena_session')!;
  const loginResponse = page.waitForResponse(r => r.url().endsWith('/api/auth/login'));
  await server.login(page); const setCookie = await (await loginResponse).headerValue('set-cookie');
  expect(setCookie?.includes('HttpOnly') && setCookie.includes('SameSite=Strict') && setCookie.includes('Path=/')).toBe(true);
  expect(setCookie?.includes('Domain=') || setCookie?.includes('Secure')).toBe(false);
  const admin = (await page.context().cookies(server.origin)).find(c => c.name === 'arena_session')!;
  expect(admin.value === before.value).toBe(false);
  expect(await page.evaluate(() => document.cookie.includes('arena_session'))).toBe(false);
  evidence.cookies.push({ profile: 'local', httpOnly: admin.httpOnly, secure: admin.secure, sameSite: admin.sameSite, path: admin.path, rotated: true, documentCookieReadable: false });
  await configure(page, family); await screenshot(page, 'g8-published-' + family);
  const csrfBeforeLogout = (await (await page.request.get(server.origin + '/api/auth/session')).json()).csrfToken as string;
  await page.getByRole('button', { name: 'Выйти', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Вход администратора' })).toBeVisible();
  await negative('logged-out administrator publish', await page.request.post(server.origin + '/api/admin/reference-scenarios/s1/publish',
    { data: {}, headers: { Cookie: `arena_session=${admin.value}`, Origin: server.origin, 'X-CSRF-Token': csrfBeforeLogout } }), 401);
  await page.goto(server.origin + '/'); await page.getByRole('button', { name: 'Выбрать ситуацию', exact: true }).click();
  await page.getByLabel('Моя цель').selectOption('target');
  await page.getByRole('checkbox', { name: /Я фиксирую свою альтернативу/ }).check();
  await page.getByRole('button', { name: 'Сохранить подготовку', exact: true }).click();
  await expect(page.getByText(/Подготовка сохранена:/)).toBeVisible();
  await page.getByRole('button', { name: 'Начать переговоры', exact: true }).click();
  const initial = await snapshot(page), id = initial.projection.sessionId;
  const otherContext = await browser.newContext({ viewport: { width: 360, height: 900 } });
  try {
    const other = await otherContext.newPage(); await other.goto(server.origin + '/session/' + id);
    await expect(other.getByRole('alert')).toContainText('Попытка недоступна');
    await expect(other.getByTestId('turn')).toHaveCount(0); await screenshot(other, 'g8-foreign-uuid-' + family);
    await negative('foreign exact UUID GET', await other.request.get(server.origin + '/api/sessions/' + id), 404);
    await negative('foreign exact UUID turn', await server.post(other, server.origin + '/api/sessions/' + id + '/turns',
      { requestId: randomUUID(), expectedRevision: 0, action: { kind: 'walk_away', tone: 'neutral', acknowledgementFactId: null, argumentId: null, contradictsFactId: null, evidenceRefs: [] } }), 404);
    await negative('player admin draft', await other.request.get(server.origin + '/api/admin/context-draft'), 403);
    const noCsrf = await page.evaluate(async id => {
      const r = await fetch('/api/sessions/' + id + '/preparation', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      return { status: r.status, code: (await r.json()).code };
    }, id);
    expect(noCsrf).toEqual({ status: 403, code: 'CSRF_REJECTED' }); evidence.negatives.push({ action: 'Chrome authenticated mutation missing CSRF', status: noCsrf.status });
    expect(await snapshot(page)).toEqual(initial);
    if (family === 'S1') {
      await move(page, 'question', 'Тема вопроса', 'logistics');
      await move(page, 'acknowledge', 'Какой факт вы признаёте?', 'logistics-saving');
    } else {
      await move(page, 'question', 'Тема вопроса', 'priorities'); await move(page, 'question', 'Тема вопроса', 'resources');
    }
    const active = await snapshot(page); await page.reload(); expect(await snapshot(page)).toEqual(active);
    await server.stop(); await server.start(); await page.reload(); expect(await snapshot(page)).toEqual(active);
    if (family === 'S1') {
      await move(page, 'argument', 'На что вы хотите сослаться?', 'logistics-argument'); await move(page, 'question', 'Тема вопроса', 'payment');
    } else {
      await move(page, 'acknowledge', 'Какой факт вы признаёте?', 'report-deferrable'); await move(page, 'argument', 'На что вы хотите сослаться?', 'resource-argument');
    }
    await page.getByLabel('Что вы хотите сделать?').selectOption('offer');
    const values = family === 'S1' ? [['Цена за партию (тыс. условных единиц)', '95'], ['Поставка (график партии)', 'split40at7_rest14'], ['Предоплата (%)', '50']]
      : [['Объём (часов работы)', 'full'], ['Срок (рабочих дней)', '2'], ['Помощник (6 часов ресурса)', '1'], ['Перенос отчёта (6 часов ресурса)', '1']];
    for (const [label, value] of values) await page.getByLabel(label!).selectOption(value!);
    await page.getByRole('button', { name: 'Проверить предложение', exact: true }).click();
    await page.getByRole('button', { name: 'Отправить предложение', exact: true }).click();
    await expect(page.getByTestId('process-score')).toBeVisible(); const terminal = await snapshot(page);
    const reportUrl = `${server.origin}/api/sessions/${id}/feedback?revision=${terminal.projection.revision}`;
    const report = FeedbackReportSchema.parse(await (await page.request.get(reportUrl)).json());
    expect(report.outcome.playerUtility).toBe(family === 'S1' ? 64 : 47); expect(report.overall.score).toBe(100);
    await screenshot(page, 'g8-report-' + family);
    await page.getByTestId('feedback').scrollIntoViewIfNeeded(); await screenshot(page, 'g8-process-' + family);
    await negative('foreign report', await other.request.get(reportUrl), 404);
    await negative('foreign result', await other.request.get(server.origin + '/api/sessions/' + id + '/result'), 404);
    await negative('foreign replay creation', await server.post(other, server.origin + '/api/sessions/' + id + '/replay', {}), 404);
    await page.getByTestId('dimension-value').locator('summary').click();
    const link = page.getByTestId('check-value.mutual').getByRole('link').first(); await link.focus(); await page.keyboard.press('Enter');
    const href = await link.getAttribute('href'); await expect(page.locator(href!)).toBeFocused();
    await page.getByRole('button', { name: 'Повторить ту же ситуацию' }).click(); await expect(page).toHaveURL(/\/briefing$/);
    const replay = await snapshot(page); expect(replay.replayOf).toBe(id); expect(replay.scenarioVersionId).toBe(terminal.scenarioVersionId);
    await negative('foreign replay GET', await other.request.get(server.origin + '/api/sessions/' + replay.projection.sessionId), 404);
    const storage = await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, tab: { ...sessionStorage }, cookie: document.cookie }));
    const currentCookie = (await page.context().cookies(server.origin)).find(c => c.name === 'arena_session')!;
    const currentCsrf = (await (await page.request.get(server.origin + '/api/auth/session')).json()).csrfToken as string;
    expect(storage.includes(currentCookie.value) || storage.includes(currentCsrf) || storage.includes(admin.value)).toBe(false);
  } finally { await otherContext.close(); }
});

test('G8 real foreign-origin form/fetch and browser CSRF rejection leave publication/session state unchanged', async ({ page }) => {
  await server.login(page);
  const foreign = createServer((_req, res) => { res.setHeader('Content-Type', 'text/html'); res.end('<!doctype html><title>Foreign origin test</title><p>Synthetic origin test</p>'); });
  foreign.listen(0, '127.0.0.1'); await once(foreign, 'listening'); const address = foreign.address();
  if (!address || typeof address === 'string') throw new Error('No test origin');
  try {
    // localhost vs 127.0.0.1 is cross-site as well as a different origin; both are loopback.
    await page.goto(`http://localhost:${address.port}`);
    const response = page.waitForResponse(r => r.url() === server.origin + '/api/admin/reference-scenarios/s1/publish');
    await page.evaluate(async origin => { await fetch(origin + '/api/admin/reference-scenarios/s1/publish',
      { method: 'POST', mode: 'no-cors', credentials: 'include', headers: { 'Content-Type': 'text/plain' }, body: '{}' }); }, server.origin);
    const rejected = await response; await negative('real cross-site Chrome mutation', rejected, 403);
    // Chrome withholds the opaque no-cors body / some wire headers. Confirm actual page origin,
    // the server's safe rejection event and unchanged publication data, without saving headers.
    expect(await page.evaluate(() => location.origin)).toBe(`http://localhost:${address.port}`);
    expect(server.securityEvents()).toContainEqual({ event: 'access.denied', routeClass: 'admin', reason: 'ORIGIN_REJECTED' });
    expect(await rejected.headerValue('access-control-allow-origin')).toBeNull();
    expect(await (await page.request.get(server.origin + '/api/scenarios')).json()).toEqual([]);
    await page.goto(server.origin + '/admin'); await expect(page.getByRole('button', { name: 'Выйти', exact: true })).toBeVisible();
    const wrong = await page.evaluate(async () => {
      const r = await fetch('/api/admin/reference-scenarios/s1/publish', { method: 'POST', body: '{}',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': 'wrong' } }); return { status: r.status, code: (await r.json()).code };
    }); expect(wrong).toEqual({ status: 403, code: 'CSRF_REJECTED' });
    evidence.negatives.push({ action: 'real Chrome wrong CSRF with admin cookie', status: wrong.status });
  } finally { foreign.closeAllConnections(); await new Promise<void>((resolve, reject) => foreign.close(e => e ? reject(e) : resolve())); }
});

test('G8 expired administrator returns to login, cannot publish after restart, and retains saved draft', async ({ page }) => {
  await server.login(page); const workspace = page.getByRole('region', { name: 'Настроить контекст' });
  await workspace.getByLabel('Тон оппонента', { exact: true }).selectOption('friendly');
  await workspace.getByRole('button', { name: 'Сохранить черновик', exact: true }).click();
  await expect(workspace.getByText(/Черновик сохранён/)).toBeVisible();
  const saved = await (await page.request.get(server.origin + '/api/admin/context-draft')).json();
  const cookie = (await page.context().cookies(server.origin)).find(c => c.name === 'arena_session')!;
  const db = new Database(server.database);
  try { db.prepare('UPDATE access_sessions SET idle_expires_at = unixepoch() - 1 WHERE token_digest = ?')
    .run(createHash('sha256').update(cookie.value).digest('hex')); } finally { db.close(); }
  const rejection = page.waitForResponse(r => r.url().endsWith('/api/admin/reference-scenarios/s1/publish'));
  await page.getByRole('button', { name: 'Опубликовать S1', exact: true }).click(); await negative('expired admin publish', await rejection, 401);
  await expect(page.getByRole('heading', { name: 'Вход администратора' })).toBeVisible(); await screenshot(page, 'g8-expired-admin');
  await server.stop(); await server.start();
  await negative('expired admin after real restart', await page.request.get(server.origin + '/api/admin/context-draft'), 401);
  await server.login(page); expect(await (await page.request.get(server.origin + '/api/admin/context-draft')).json()).toEqual(saved);
  expect(await (await page.request.get(server.origin + '/api/scenarios')).json()).toEqual([]);
});

test('G8 logout in another tab returns stale admin to login on CSRF refusal without retrying publication', async ({ page, context }) => {
  await server.login(page);
  const stale = await context.newPage(); await stale.goto(server.origin + '/admin');
  await expect(stale.getByRole('button', { name: 'Опубликовать S1', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Выйти', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Вход администратора' })).toBeVisible();
  // The first tab has bootstrapped a fresh player cookie; the other tab still holds its old CSRF in memory.
  await expect.poll(async () => (await (await page.request.get(server.origin + '/api/auth/session')).json()).role).toBe('player');
  let attempts = 0; stale.on('request', r => { if (r.url().endsWith('/api/admin/reference-scenarios/s1/publish')) attempts++; });
  const response = stale.waitForResponse(r => r.url().endsWith('/api/admin/reference-scenarios/s1/publish'));
  await stale.getByRole('button', { name: 'Опубликовать S1', exact: true }).click();
  await negative('stale admin tab after logout', await response, 403);
  await expect(stale.getByRole('heading', { name: 'Вход администратора' })).toBeVisible();
  expect(attempts).toBe(1); expect(await (await page.request.get(server.origin + '/api/scenarios')).json()).toEqual([]);
  await stale.close();
});
