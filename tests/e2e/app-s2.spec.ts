import { mkdirSync, writeFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { SessionViewSchema } from '@arena/contracts/g2';
import { FeedbackReportSchema } from '@arena/contracts/feedback';
import { S1, S2, accept, walkAway } from '@arena/scenarios';
import { productionHarness } from './production.ts';

let server: Awaited<ReturnType<typeof productionHarness>>;
const evidence = { browser: '', responses: 0, externalRequests: [] as string[], privacyFailures: [] as string[], browserErrors: [] as string[],
  layouts: [] as { width: number; screen: string; overflow: number }[], outcomes: [] as { family: string; utility: number | null }[] };
const inspections: Promise<void>[] = [];
function inspect(value: unknown) {
  const report = FeedbackReportSchema.safeParse(value);
  // The strict terminal report permits a derived accepted-credit count, never raw private state.
  const body = JSON.stringify(report.success ? { ...report.data, overall: { ...report.data.overall, progressCredits: undefined } } : value); evidence.responses++;
  if (/"(?:trust|tension|resourceAuthorizations|opponentUtility|opponentBatna|witnessTraces|definition_json|participants)"\s*:/.test(body)) evidence.privacyFailures.push('private state');
  const session = SessionViewSchema.safeParse(value);
  const known = session.success ? session.data.projection.knownFacts.map(f => f.id)
    : report.success ? [...S1.facts, ...S2.facts].filter(f => report.data.outcome.observations.some(o => o.ruleId === 'FACT_DISCLOSED' && o.text.includes(f.text))).map(f => f.id) : [];
  for (const scenario of [S1, S2]) {
    if (body.includes(scenario.participants[1].privateBrief) || body.includes(scenario.participants[1].batna.description)) evidence.privacyFailures.push('private opponent');
    for (const fact of scenario.facts.filter(f => f.visibility === 'hidden' && !known.includes(f.id))) {
      if (body.includes(fact.text) || body.includes(fact.id)) evidence.privacyFailures.push('undisclosed fact');
    }
  }
}
test.beforeAll(async ({ browser }) => {
  evidence.browser = browser.version(); server = await productionHarness({ label: 'app-s2' }); await server.start();
});
test.beforeEach(async ({ context, page }) => {
  await context.route('**/*', async route => {
    const url = route.request().url();
    if (/^https?:/.test(url) && new URL(url).origin !== server.origin) { evidence.externalRequests.push(url); await route.abort(); }
    else await route.continue();
  });
  page.on('pageerror', error => evidence.browserErrors.push(error.message));
  context.on('page', tab => tab.on('pageerror', error => evidence.browserErrors.push(error.message)));
  context.on('response', response => {
    if (!response.url().startsWith(server.origin + '/api/')) return;
    inspections.push((async () => { try { inspect(await response.json()); } catch { /* Deliberately lost response. */ } })());
  });
});
test.afterAll(async () => {
  await Promise.all(inspections); if (server) await server.stop();
  mkdirSync('.tools', { recursive: true });
  writeFileSync('.tools/app-browser-evidence.json', JSON.stringify({ ...evidence, production: server?.evidence() }, null, 2));
  server?.cleanup();
  expect(evidence.privacyFailures).toEqual([]); expect(evidence.externalRequests).toEqual([]); expect(evidence.browserErrors).toEqual([]);
});
async function snapshot(page: Page) {
  const id = /\/session\/([^/]+)/.exec(page.url())?.[1]; expect(id).toBeTruthy();
  const r = await page.request.get(`${server.origin}/api/sessions/${id}`); expect(r.status()).toBe(200);
  const value: unknown = await r.json(); inspect(value); return SessionViewSchema.parse(value);
}
async function layout(page: Page, screen: string) {
  const result = await page.evaluate(() => ({ width: innerWidth, overflow: document.documentElement.scrollWidth - innerWidth }));
  expect(result.overflow).toBeLessThanOrEqual(0);
  for (const control of await page.locator('button:visible, select:visible').all()) {
    const box = await control.boundingBox(); expect(box).not.toBeNull();
    if (box) { expect(box.x).toBeGreaterThanOrEqual(0); expect(box.x + box.width).toBeLessThanOrEqual(result.width + 1); expect(box.height).toBeGreaterThanOrEqual(44); }
  }
  evidence.layouts.push({ ...result, screen });
}
async function begin(page: Page, width = 1280) {
  await page.setViewportSize({ width, height: 900 }); await page.goto(server.origin + '/admin');
  await page.getByRole('button', { name: 'S2 — Срочная задача и нагрузка' }).click();
  await expect(page.getByText('S2-WORKLOAD-URGENT', { exact: true })).toBeVisible();
  await layout(page, 'S2 publication'); await page.getByRole('button', { name: 'Опубликовать S2', exact: true }).click();
  await expect(page.getByText('Версия опубликована. Ситуация доступна игроку.')).toBeVisible();
  await page.getByRole('link', { name: 'Открыть вход игрока' }).click();
  const card = page.getByRole('article').filter({ has: page.getByRole('heading', { name: S2.title, exact: true }) });
  await expect(card).toContainText('Управление командой'); await layout(page, 'S2 selection');
  await card.getByRole('button', { name: 'Выбрать ситуацию' }).click();
  await expect(page.getByRole('heading', { name: 'Ваша роль — руководитель' })).toBeVisible();
  await expect(page.getByText(/Согласуйте весь пакет:/)).toContainText('объём, срок, помощник, перенос отчёта');
  await expect(page.getByText(/Согласуйте весь пакет:/)).not.toContainText('цены');
  await layout(page, 'S2 briefing');
  if (width === 390) await page.screenshot({ path: '.tools/app-s2-briefing-390.png', fullPage: true });
  const initial = await snapshot(page);
  await page.getByRole('button', { name: 'Начать переговоры' }).click();
  await expect(page.getByTestId('revision')).toHaveText('Ход 0 из 8'); return initial;
}
async function choose(page: Page, kind: string) { await page.getByLabel('Что вы хотите сделать?').selectOption(kind); }
async function send(page: Page, count: number) {
  await page.getByRole('button', { name: 'Отправить ход', exact: true }).click();
  await expect(page.getByTestId('turn')).toHaveCount(count); await expect(page.getByLabel('Что вы хотите сделать?')).toBeEnabled();
}
async function ask(page: Page, topic: string, count: number) { await choose(page, 'question'); await page.getByLabel('Тема вопроса').selectOption(topic); await send(page, count); }
async function acknowledgeHelper(page: Page, count: number) {
  await choose(page, 'acknowledge'); await page.getByLabel('Какой факт вы признаёте?').selectOption('helper-available'); await send(page, count);
}
async function propose(page: Page, scope: string, days: string, help: string, defer: string, count: number) {
  await choose(page, 'offer');
  await expect(page.getByRole('button', { name: 'Проверить предложение', exact: true })).toBeDisabled();
  for (const [label, value] of [['Объём (часов работы)', scope], ['Срок (рабочих дней)', days], ['Помощник (6 часов ресурса)', help], ['Перенос отчёта (6 часов ресурса)', defer]]) {
    await page.getByLabel(label!).selectOption(value!);
  }
  await page.getByRole('button', { name: 'Проверить предложение', exact: true }).click();
  const title = page.getByRole('heading', { name: 'Проверьте перед отправкой' }); await expect(title).toBeFocused();
  await layout(page, 'S2 confirmation');
  await page.keyboard.press('Tab');
  const submit = page.getByRole('button', { name: 'Отправить предложение', exact: true }); await expect(submit).toBeFocused();
  expect(await submit.evaluate(el => getComputedStyle(el).outlineStyle)).not.toBe('none');
  await page.keyboard.press('Enter'); await expect(page.getByTestId('turn')).toHaveCount(count);
}
async function result(page: Page, family: string, utility: number | null) {
  await expect(page.getByTestId('result')).toBeVisible(); const s = await snapshot(page);
  expect(s.result?.family).toBe(family); expect(s.result?.playerUtility).toBe(utility);
  for (const o of s.result!.observations) expect(s.transcript.some(t => t.turnNumber === o.turnNumber)).toBe(true);
  await layout(page, 'S2 result'); evidence.outcomes.push({ family, utility }); return s;
}

test('S2 complete mutual route, concurrent S1, refresh/restart, persisted result and replay at 1280px', async ({ page }) => {
  expect((await page.request.get(server.origin + '/health')).status()).toBe(200);
  expect(await (await page.request.get(server.origin + '/ready')).json()).toEqual({ status: 'ready' });
  const s1Version = await (await page.request.post(server.origin + '/api/admin/reference-scenarios/s1/publish', { data: {} })).json() as { id: string };
  const s1 = SessionViewSchema.parse(await (await page.request.post(server.origin + '/api/sessions', { data: { scenarioVersionId: s1Version.id } })).json());
  const initial = await begin(page);
  await ask(page, 'priorities', 1); await ask(page, 'resources', 2);
  const saved = await snapshot(page); await page.reload(); await expect(page.getByTestId('revision')).toHaveText('Ход 2 из 8'); expect(await snapshot(page)).toEqual(saved);
  await server.stop(); await server.start(); await page.reload(); await expect(page.getByTestId('revision')).toHaveText('Ход 2 из 8'); expect(await snapshot(page)).toEqual(saved);
  expect(await (await page.request.get(`${server.origin}/api/sessions/${s1.projection.sessionId}`)).json()).toEqual(s1);
  await choose(page, 'acknowledge'); await page.getByLabel('Какой факт вы признаёте?').selectOption('report-deferrable'); await send(page, 3);
  await choose(page, 'argument'); await page.getByLabel('На что вы хотите сослаться?').selectOption('resource-argument'); await send(page, 4);
  await propose(page, 'full', '2', '1', '1', 5); const ended = await result(page, 'MUTUAL_GAIN', 47);
  await page.screenshot({ path: '.tools/app-s2-result-1280.png', fullPage: true });
  await page.getByRole('link', { name: 'Ход 1 — открыть в диалоге' }).first().click(); await expect(page.locator('#turn-1')).toBeInViewport();
  await server.stop(); await server.start(); await page.reload(); await expect(page.getByTestId('result')).toBeVisible(); expect(await snapshot(page)).toEqual(ended);
  await page.getByRole('button', { name: 'Повторить ту же ситуацию' }).click(); await expect(page.getByRole('button', { name: 'Начать переговоры' })).toBeVisible();
  const replay = await snapshot(page); expect(replay.scenarioVersionId).toBe(initial.scenarioVersionId); expect(replay.projection.revision).toBe(0);
  expect(replay.projection.sessionId).not.toBe(initial.projection.sessionId); expect(replay.transcript).toEqual([]);
  expect(await (await page.request.get(`${server.origin}/api/sessions/${ended.projection.sessionId}`)).json()).toEqual(ended);
  const storage = await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage } }));
  expect(Object.keys(storage.local)).toEqual(['arena:last-session']); expect(storage.session).toEqual({});
});
test('S2 partial outcome through resource tradeoff at 390px', async ({ page }) => {
  await begin(page, 390); await ask(page, 'resources', 1); await acknowledgeHelper(page, 2);
  await propose(page, 'core', '2', '1', '0', 3); await result(page, 'ACCEPTABLE_PARTIAL', 32);
  await expect(page.getByTestId('result')).toContainText('целевая граница не достигнута');
});
test('S2 poor agreement explains own alternative at 360px', async ({ page }) => {
  await begin(page, 360); await ask(page, 'resources', 1); await acknowledgeHelper(page, 2);
  await propose(page, 'core', '5', '0', '0', 3); await result(page, 'POOR_AGREEMENT', 20);
  await expect(page.getByRole('heading', { name: 'Сделка хуже вашей альтернативы' })).toBeVisible();
  await expect(page.getByTestId('result')).toContainText('Без помощника');
  await expect(page.getByTestId('result')).not.toContainText('Без помощника 6 часов');
  await page.screenshot({ path: '.tools/app-s2-result-360.png', fullPage: true });
});
test('S2 impossible offer, no-deal result and terminal guard at 390px', async ({ page }) => {
  await begin(page, 390); await propose(page, 'full', '2', '0', '0', 1);
  const refused = await snapshot(page); expect(refused.result).toBeNull();
  await expect(page.getByRole('region', { name: 'История переговоров' })).toContainText('Принять его нельзя');
  expect(refused.projection.activeOffer!.terms.find(t => t.issueId === 'HELP')?.valueId).toBe('0');
  await choose(page, 'walk_away'); await page.getByRole('button', { name: 'Подтвердить выход…' }).click(); await page.getByRole('button', { name: 'Выйти без сделки', exact: true }).click();
  const ended = await result(page, 'NO_AGREEMENT', null);
  const r = await page.request.post(`${server.origin}/api/sessions/${ended.projection.sessionId}/turns`, { data: { requestId: randomUUID(), expectedRevision: ended.projection.revision, action: walkAway() } });
  expect(r.status()).toBe(409); expect((await r.json() as { code: string }).code).toBe('SESSION_TERMINAL');
  expect(await snapshot(page)).toEqual(ended);
});
test('S2 invalid input, counteroffer replacement, stale proposal and exact active acceptance', async ({ page }) => {
  const initial = await begin(page, 390);
  const url = `${server.origin}/api/sessions/${initial.projection.sessionId}/turns`;
  const invalid = await page.request.post(url, { data: { requestId: randomUUID(), expectedRevision: 0, action: { kind: 'offer', terms: [] } } });
  expect(invalid.status()).toBe(400); expect(await snapshot(page)).toEqual(initial);
  await propose(page, 'full', '2', '0', '0', 1); const old = (await snapshot(page)).projection.activeOffer!;
  await ask(page, 'capacity-topic', 2);
  // Explicitly replace the package using the generic editor.
  await page.getByRole('button', { name: 'Изменить эти условия' }).click();
  await page.getByLabel('Объём (часов работы)').selectOption('full');
  await page.getByLabel('Срок (рабочих дней)').selectOption('2');
  await page.getByLabel('Помощник (6 часов ресурса)').selectOption('1');
  await page.getByLabel('Перенос отчёта (6 часов ресурса)').selectOption('0');
  await page.getByRole('button', { name: 'Проверить предложение', exact: true }).click(); await page.getByRole('button', { name: 'Отправить предложение', exact: true }).click();
  await expect(page.getByTestId('revision')).toHaveText('Ход 3 из 8'); const active = await snapshot(page); expect(active.projection.activeOffer!.id).not.toBe(old.id);
  const stale = await page.request.post(url, { data: { requestId: randomUUID(), expectedRevision: 3, action: accept(old.id) } }); expect(stale.status()).toBe(422);
  await page.reload(); await expect(page.getByTestId('revision')).toHaveText('Ход 3 из 8'); expect(await snapshot(page)).toEqual(active);
  await page.getByRole('button', { name: 'Принять предложение', exact: true }).click();
  await page.getByRole('button', { name: 'Принять эти условия', exact: true }).click(); await expect(page.getByTestId('result')).toBeVisible();
  expect((await snapshot(page)).result!.agreementOffer!.terms).toEqual(active.projection.activeOffer!.terms);
});
test('S2 pending lock, duplicate click, lost committed response, same identity retry and stale tab error', async ({ page, context }) => {
  const initial = await begin(page, 390); let first = true; let release: () => void = () => {}; let seen: () => void = () => {};
  const held = new Promise<void>(resolve => { release = resolve; }); const observed = new Promise<void>(resolve => { seen = resolve; });
  const ids: string[] = [];
  await page.route('**/api/sessions/*/turns', async route => {
    ids.push((route.request().postDataJSON() as { requestId: string }).requestId);
    if (first) { first = false; await route.fetch(); seen(); await held; await route.abort('failed'); } else await route.continue();
  });
  await page.getByRole('button', { name: 'Отправить ход', exact: true }).dblclick(); await observed;
  try { await expect(page.getByLabel('Что вы хотите сделать?')).toBeDisabled(); await expect(page.getByRole('status').filter({ hasText: 'Сохраняем ход' })).toBeVisible(); expect(ids).toHaveLength(1); } finally { release(); }
  await expect(page.getByRole('button', { name: 'Повторить отправку' })).toBeVisible();
  const pending = await page.evaluate(() => ({ ...sessionStorage })); expect(JSON.stringify(pending)).not.toMatch(/trust|tension|privateBrief|resourceAuthorizations/);
  await page.reload(); await expect(page.getByTestId('revision')).toHaveText('Ход 1 из 8');
  await page.getByRole('button', { name: 'Повторить отправку' }).click(); await expect(page.getByLabel('Что вы хотите сделать?')).toBeEnabled();
  expect(ids).toHaveLength(2); expect(ids[1]).toBe(ids[0]); expect((await snapshot(page)).projection.revision).toBe(1);
  const stale = await context.newPage(); await stale.setViewportSize({ width: 390, height: 900 });
  await stale.goto(`${server.origin}/session/${initial.projection.sessionId}`); await expect(stale.getByTestId('revision')).toHaveText('Ход 1 из 8');
  await ask(page, 'resources', 2); await stale.getByRole('button', { name: 'Отправить ход', exact: true }).click();
  await expect(stale.getByRole('alert')).toContainText('другой вкладке'); await expect(stale.getByTestId('revision')).toHaveText('Ход 2 из 8');
  await expect(stale.getByRole('alert')).toContainText('Загружено актуальное состояние');
  await layout(stale, 'S2 actionable stale error'); await stale.screenshot({ path: '.tools/app-s2-error-390.png', fullPage: true });
  await expect(stale.getByLabel('Что вы хотите сделать?')).toBeEnabled(); expect((await snapshot(stale)).projection.revision).toBe(2); await stale.close();
});
