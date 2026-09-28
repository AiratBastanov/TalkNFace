import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { SessionViewSchema } from '@arena/contracts/g2';
import { FeedbackReportSchema } from '@arena/contracts/feedback';
import type { SessionView } from '@arena/contracts/g2';
import { S1 } from '@arena/scenarios';
import { productionHarness } from './production.ts';

let server: Awaited<ReturnType<typeof productionHarness>>;
const evidence: { browser: string; channel: string; routes: string[]; cases: Record<string, unknown>[]; viewportChecks: { width: number; screen: string; overflow: number }[];
  browserResponses: number; externalRequests: string[]; privacyFailures: string[]; browserErrors: string[] } = {
  browser: '', channel: 'chrome', routes: [], cases: [], viewportChecks: [], browserResponses: 0,
  externalRequests: [], privacyFailures: [], browserErrors: [],
};
const inspectionTasks: Promise<void>[] = [];

function inspectBody(value: unknown) {
  const report = FeedbackReportSchema.safeParse(value);
  // The strict terminal report permits a derived accepted-credit count, never raw private state.
  const body = JSON.stringify(report.success ? { ...report.data, overall: { ...report.data.overall, progressCredits: undefined } } : value);
  if (/"(?:trust|tension|warning|earnedEventKeys|progressCredits|groundedArgumentIds|resourceAuthorizations|aspiration|opponentUtility|opponentBatna|witnessTraces|definition_json|definitionJson|participants)"\s*:/.test(body)) evidence.privacyFailures.push('Private field');
  if (body.includes(S1.participants[1].privateBrief) || body.includes(S1.participants[1].batna.description)) evidence.privacyFailures.push('Private opponent description');
  const parsed = SessionViewSchema.safeParse(value);
  const known = parsed.success ? parsed.data.projection.knownFacts.map(f => f.id)
    : report.success ? S1.facts.filter(f => report.data.outcome.observations.some(o => o.ruleId === 'FACT_DISCLOSED' && o.text.includes(f.text))).map(f => f.id) : [];
  for (const fact of S1.facts.filter(f => f.visibility === 'hidden' && !known.includes(f.id))) {
    if (body.includes(fact.text) || body.includes(fact.id)) evidence.privacyFailures.push('Undisclosed fact');
  }
}
test.beforeAll(async ({ browser }) => {
  evidence.browser = browser.version(); server = await productionHarness(); await server.start();
});
test.beforeEach(async ({ context, page }) => {
  await context.route('**/*', async route => {
    const url = route.request().url();
    if (/^https?:/.test(url) && new URL(url).origin !== server.origin) { evidence.externalRequests.push(url); await route.abort(); }
    else await route.continue();
  });
  context.on('page', tab => tab.on('pageerror', error => evidence.browserErrors.push(error.message)));
  page.on('pageerror', error => evidence.browserErrors.push(error.message));
  context.on('response', response => {
    if (!response.url().startsWith(server.origin + '/api/')) return;
    const task = (async () => {
      try {
        const value: unknown = await response.json(); evidence.browserResponses++;
        // Result route is not fetched by the UI; all observed payloads are envelopes/previews/errors.
        inspectBody(value);
      } catch { /* The deliberately aborted retry response may not have a body. */ }
    })(); inspectionTasks.push(task);
  });
});
test.afterAll(async () => {
  await Promise.all(inspectionTasks);
  if (server) await server.stop();
  mkdirSync('.tools', { recursive: true });
  writeFileSync('.tools/g2-browser-evidence.json', JSON.stringify({ ...evidence, production: server?.evidence() }, null, 2));
  server?.cleanup();
  expect(evidence.externalRequests).toEqual([]); expect(evidence.privacyFailures).toEqual([]); expect(evidence.browserErrors).toEqual([]);
});
async function snapshot(page: Page): Promise<SessionView> {
  const id = /\/session\/([^/]+)/.exec(page.url())?.[1]; expect(id).toBeTruthy();
  const response = await page.request.get(`${server.origin}/api/sessions/${id}`); expect(response.status()).toBe(200);
  const value: unknown = await response.json(); inspectBody(value); return SessionViewSchema.parse(value);
}
async function responsive(page: Page, screen: string) {
  const result = await page.evaluate(() => ({ width: innerWidth, overflow: document.documentElement.scrollWidth - innerWidth }));
  expect(result.overflow, screen).toBeLessThanOrEqual(0);
  const controls = page.locator('button:visible, select:visible');
  for (let i = 0; i < await controls.count(); i++) {
    const box = await controls.nth(i).boundingBox(); expect(box).not.toBeNull();
    if (box) { expect(box.x).toBeGreaterThanOrEqual(0); expect(box.x + box.width).toBeLessThanOrEqual(result.width + 1); expect(box.height).toBeGreaterThanOrEqual(44); }
  }
  evidence.viewportChecks.push({ ...result, screen });
}
async function openNew(page: Page) {
  const published = await page.request.get(server.origin + '/api/scenarios');
  if (!(await published.json() as unknown[]).length) {
    const response = await page.request.post(server.origin + '/api/admin/reference-scenarios/s1/publish', { data: {} });
    expect(response.status()).toBe(200);
  }
  await page.goto(server.origin + '/');
  await page.getByRole('button', { name: 'Выбрать ситуацию' }).first().click();
  await expect(page.getByRole('button', { name: 'Начать переговоры' })).toBeVisible();
  await responsive(page, 'briefing');
  const initial = await snapshot(page);
  await page.getByRole('button', { name: 'Начать переговоры' }).click();
  await expect(page.getByTestId('revision')).toHaveText('Ход 0 из 8');
  await expect(page.locator('textarea, input[type=text]')).toHaveCount(0);
  return initial;
}
async function choose(page: Page, kind: string) { await page.getByLabel('Что вы хотите сделать?').selectOption(kind); }
async function send(page: Page, turn: number) {
  await page.getByRole('button', { name: 'Отправить ход', exact: true }).click();
  await expect(page.getByTestId('turn')).toHaveCount(turn);
  if (turn < 8) await expect(page.getByLabel('Что вы хотите сделать?')).toBeEnabled();
}
async function ask(page: Page, topic: string, turn: number) {
  await choose(page, 'question'); await page.getByLabel('Тема вопроса').selectOption(topic); await send(page, turn);
}
async function offerForm(page: Page, price: string, delivery: string, prepay: string) {
  await choose(page, 'offer');
  await page.getByLabel('Цена за партию (тыс. условных единиц)').selectOption(price);
  await page.getByLabel('Поставка (график партии)').selectOption(delivery);
  await page.getByLabel('Предоплата (%)').selectOption(prepay);
  await responsive(page, 'offer');
  await page.getByRole('button', { name: 'Проверить предложение', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Проверьте перед отправкой' })).toBeFocused();
  await responsive(page, 'confirmation');
}
async function sendOffer(page: Page, turn: number) {
  await page.getByRole('button', { name: 'Отправить предложение', exact: true }).click();
  await expect(page.getByTestId('turn')).toHaveCount(turn);
}

test('A: admin publish → GS1 → refresh + process restart → result → clean replay, 1280px', async ({ page }) => {
  await page.goto(server.origin + '/admin'); await expect(page.getByText('S1-SUPPLY-LAUNCH', { exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Настроить контекст' }).locator('select')).toHaveCount(6);
  await expect(page.locator('textarea')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Предмет переговоров' })).toBeVisible();
  await responsive(page, 'admin');
  await page.getByRole('button', { name: 'Опубликовать S1' }).click();
  await expect(page.getByText('Версия опубликована. Ситуация доступна игроку.')).toBeVisible();
  await page.getByRole('link', { name: 'Открыть вход игрока' }).click();
  const initial = await openNew(page); const id = initial.projection.sessionId;
  await ask(page, 'logistics', 1); await ask(page, 'payment', 2);
  const before = await snapshot(page); const history = await page.getByRole('region', { name: 'История переговоров' }).innerText();
  const facts = await page.getByTestId('known-facts').innerText();
  await page.reload(); await expect(page.getByTestId('revision')).toHaveText('Ход 2 из 8');
  expect(await snapshot(page)).toEqual(before); expect(await page.getByRole('region', { name: 'История переговоров' }).innerText()).toBe(history);
  expect(await page.getByTestId('known-facts').innerText()).toBe(facts);
  await server.stop(); await server.start();
  await page.reload(); await expect(page.getByTestId('revision')).toHaveText('Ход 2 из 8'); expect(await snapshot(page)).toEqual(before);
  await choose(page, 'acknowledge'); await page.getByLabel('Какой факт вы признаёте?').selectOption('cashflow-need'); await send(page, 3);
  await choose(page, 'argument'); await page.getByLabel('На что вы хотите сослаться?').selectOption('logistics-argument'); await send(page, 4);
  await offerForm(page, '100', 'split40at7_rest14', '50'); expect((await snapshot(page)).projection.revision).toBe(4);
  await page.getByRole('button', { name: 'Вернуться к выбору' }).click();
  await page.getByLabel('Цена за партию (тыс. условных единиц)').selectOption('95');
  await page.getByRole('button', { name: 'Проверить предложение', exact: true }).click(); await sendOffer(page, 5);
  await expect(page.getByRole('heading', { name: 'Цель достигнута', exact: true })).toBeVisible();
  await responsive(page, 'result'); const final = await snapshot(page);
  expect(final.result?.family).toBe('MUTUAL_GAIN'); expect(final.result?.playerUtility).toBe(64);
  expect(final.result?.batnaComparison).toBe('above');
  await page.screenshot({ path: '.tools/g2-result-1280.png', fullPage: true });
  await page.getByRole('link', { name: 'Ход 1 — открыть в диалоге' }).first().click(); await expect(page.locator('#turn-1')).toBeInViewport();
  await page.reload(); expect(await snapshot(page)).toEqual(final);
  await page.getByRole('button', { name: 'Повторить ту же ситуацию' }).click();
  await expect(page.getByRole('button', { name: 'Начать переговоры' })).toBeVisible();
  const replay = await snapshot(page); expect(replay.projection.sessionId).not.toBe(id); expect(replay.scenarioVersionId).toBe(initial.scenarioVersionId);
  expect(replay.projection.knownFacts).toEqual(initial.projection.knownFacts); expect(replay.projection.activeOffer).toBeNull(); expect(replay.transcript).toEqual([]);
  const original = await page.request.get(`${server.origin}/api/sessions/${id}`); expect(await original.json()).toEqual(final);
  evidence.routes.push('/admin', '/', '/session/:id/briefing', '/session/:id', '/session/:id/result');
  evidence.cases.push({ name: 'GS1', expected: 'MUTUAL_GAIN', actual: final.result?.family, refresh: 'PASS', restart: 'PASS', replay: 'PASS', offerEditConfirmation: 'PASS' });
});
test('B: early poor offer and deliberate pressure cause opponent walkaway', async ({ page }) => {
  await openNew(page); await offerForm(page, '90', 'all7', '0'); await sendOffer(page, 1);
  await choose(page, 'pressure'); await page.getByLabel('Тон реплики').selectOption('threat');
  for (const turn of [2, 3, 4]) await send(page, turn);
  await expect(page.getByRole('status')).toContainText('Оппонент предупредил о выходе');
  await page.getByRole('button', { name: 'Отправить ход', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Соглашение не достигнуто', exact: true })).toBeVisible();
  const final = await snapshot(page); expect(final.result?.family).toBe('NO_AGREEMENT'); expect(final.result?.terminalReason).toBe('opponent_walkaway');
  expect(final.result?.observations.map(o => o.ruleId)).toContain('TENSION_WARNING');
  evidence.cases.push({ name: 'GS3', expected: 'NO_AGREEMENT', actual: final.result?.family, terminalReason: final.result?.terminalReason });
});
test('active offer survives question and refresh, exact acceptance confirmation, 390px', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 }); await openNew(page);
  await offerForm(page, '95', 'all14', '50'); await sendOffer(page, 1);
  await expect(page.getByTestId('turn')).toContainText('обязательные условия');
  const offered = await snapshot(page); expect(offered.projection.activeOffer).not.toBeNull();
  await ask(page, 'payment', 2); const before = await snapshot(page); expect(before.projection.activeOffer).toEqual(offered.projection.activeOffer);
  await page.reload(); await expect(page.getByTestId('revision')).toHaveText('Ход 2 из 8'); expect(await snapshot(page)).toEqual(before);
  await page.getByRole('button', { name: 'Принять предложение', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Проверьте перед отправкой' })).toBeFocused(); await responsive(page, 'accept-confirmation');
  expect((await snapshot(page)).projection.revision).toBe(2);
  await page.getByRole('button', { name: 'Принять эти условия' }).click(); await expect(page.getByTestId('result')).toBeVisible();
  const final = await snapshot(page); expect(final.result?.agreementOffer).toEqual(offered.projection.activeOffer);
  await responsive(page, 'accepted-result');
  evidence.cases.push({ name: 'active-commitment', physicalRejection: 'PASS', questionPreservesOffer: 'PASS', refresh: 'PASS', exactAcceptance: 'PASS' });
});
for (const width of [360, 390]) test(`responsive ${width}px: admin, briefing, offer, keyboard confirmation, poor result`, async ({ page }) => {
  await page.setViewportSize({ width, height: 844 }); await page.goto(server.origin + '/admin');
  await expect(page.getByRole('button', { name: 'Опубликовать S1' })).toBeVisible(); await responsive(page, 'admin');
  await openNew(page); await ask(page, 'payment', 1);
  await offerForm(page, '115', 'all7', '50');
  const commit = page.getByRole('button', { name: 'Отправить предложение', exact: true }); await commit.focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Сделка хуже вашей альтернативы' })).toBeVisible();
  await responsive(page, 'poor-result');
  const final = await snapshot(page); expect(final.result?.family).toBe('POOR_AGREEMENT'); expect(final.result?.batnaComparison).toBe('below');
  await page.screenshot({ path: `.tools/g2-result-${width}.png`, fullPage: true });
  evidence.cases.push({ name: `responsive-${width}`, expected: 'POOR_AGREEMENT', actual: final.result?.family, keyboard: 'PASS' });
});
test('uncertain network response → reload/retry once; stale tab reloads authoritative state; confirmed walkaway', async ({ page, context }) => {
  const initial = await openNew(page); let intercepted = false;
  await page.route('**/api/sessions/*/turns', async route => {
    if (!intercepted) { intercepted = true; await route.fetch(); await route.abort('failed'); }
    else await route.continue();
  });
  await page.getByRole('button', { name: 'Отправить ход', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Повторить отправку' })).toBeVisible();
  expect((await snapshot(page)).projection.revision).toBe(1);
  await page.reload(); await expect(page.getByTestId('revision')).toHaveText('Ход 1 из 8');
  await page.getByRole('button', { name: 'Повторить отправку' }).click(); await expect(page.getByLabel('Что вы хотите сделать?')).toBeEnabled();
  expect((await snapshot(page)).projection.revision).toBe(1); await expect(page.getByTestId('turn')).toHaveCount(1);
  const stale = await context.newPage(); await stale.goto(`${server.origin}/session/${initial.projection.sessionId}`);
  await expect(stale.getByTestId('revision')).toHaveText('Ход 1 из 8');
  await ask(page, 'payment', 2);
  await stale.getByRole('button', { name: 'Отправить ход', exact: true }).click();
  await expect(stale.getByRole('alert')).toContainText('другой вкладке'); await expect(stale.getByTestId('revision')).toHaveText('Ход 2 из 8');
  await expect(stale.getByRole('alert')).toContainText('Загружено актуальное состояние');
  expect((await snapshot(stale)).projection.revision).toBe(2); await stale.close();
  await choose(page, 'walk_away'); await page.getByRole('button', { name: 'Подтвердить выход…' }).click();
  expect((await snapshot(page)).projection.revision).toBe(2);
  await page.getByRole('button', { name: 'Выйти без сделки' }).click(); await expect(page.getByTestId('result')).toBeVisible();
  expect((await snapshot(page)).result?.terminalReason).toBe('player_walkaway');
  evidence.cases.push({ name: 'retry-and-stale-tab', uncertainRetry: 'PASS', refreshPending: 'PASS', singleCommit: 'PASS', staleTabRecovery: 'PASS', confirmedWalkaway: 'PASS' });
});
