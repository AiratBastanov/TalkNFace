import { randomUUID } from 'node:crypto';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import type DatabaseDriver from 'better-sqlite3';
const Database = createRequire(new URL('../../apps/server/package.json', import.meta.url))('better-sqlite3') as typeof DatabaseDriver;
import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { SessionViewSchema } from '@arena/contracts/g2';
import { FeedbackReportSchema } from '@arena/contracts/feedback';
import { S1, S2 } from '@arena/scenarios';
import { createInitialState } from '@arena/domain';
import { ArenaRepository } from '../../apps/server/src/repositories/arena-repository.ts';
import { SessionService } from '../../apps/server/src/services/session-service.ts';
import { g2Migration } from '../../apps/server/src/migration-g2.ts';
import { temporaryDatabase } from '../../apps/server/test/helpers.ts';
import { productionHarness } from './production.ts';

let server: Awaited<ReturnType<typeof productionHarness>> | undefined;
const evidence = { browser: '', cases: [] as string[], screenshots: [] as string[], layouts: [] as { name: string; width: number; overflow: number }[],
  externalRequests: [] as string[], browserErrors: [] as string[], productions: [] as unknown[] };
test.beforeEach(async ({ context, page, browser }) => {
  evidence.browser = browser.version();
  await context.route('**/*', async route => {
    const url = route.request().url();
    if (/^https?:/.test(url) && new URL(url).origin !== server?.origin) { evidence.externalRequests.push(url); await route.abort(); }
    else await route.continue();
  });
  page.on('pageerror', error => evidence.browserErrors.push(error.message));
});
test.afterEach(async ({}, info) => {
  if (server) { await server.stop(); evidence.productions.push(server.evidence()); server.cleanup(); server = undefined; }
  if (info.status === 'passed') evidence.cases.push(info.title);
  mkdirSync('.tools', { recursive: true }); writeFileSync('.tools/g6-browser-evidence.json', JSON.stringify(evidence, null, 2));
});
test.afterAll(() => { expect(evidence.externalRequests).toEqual([]); expect(evidence.browserErrors).toEqual([]); });
async function start(seedDatabase?: string) {
  server = await productionHarness({ label: 'g6-' + evidence.cases.length, ...(seedDatabase ? { seedDatabase } : {}) });
  await server.start();
}
async function snapshot(page: Page) {
  const id = /\/session\/([^/]+)/.exec(page.url())![1]!;
  const response = await page.request.get(server!.origin + '/api/sessions/' + id); expect(response.status()).toBe(200);
  return SessionViewSchema.parse(await response.json());
}
async function report(page: Page) {
  await expect(page.getByTestId('process-score')).toBeVisible();
  const s = await snapshot(page);
  const response = await page.request.get(`${server!.origin}/api/sessions/${s.projection.sessionId}/feedback?revision=${s.projection.revision}`);
  expect(response.status()).toBe(200); const r = FeedbackReportSchema.parse(await response.json());
  expect(r.outcome).toEqual(s.result);
  const json = JSON.stringify(r);
  expect(json).not.toMatch(/"opponentUtility"|"opponentBatna"|"trust"|"tension"|"witnessTraces"|"participants"/);
  const scenario = s.projection.scenario.title === S1.title ? S1 : S2;
  expect(json).not.toContain(scenario.participants[1]!.privateBrief);
  expect(json).not.toContain(scenario.participants[1]!.batna.description);
  for (const fact of scenario.facts.filter(f => !s.projection.knownFacts.some(k => k.id === f.id))) {
    expect(json).not.toContain(fact.id); expect(json).not.toContain(fact.text);
  }
  for (const e of r.evidence) {
    expect(e.sessionId).toBe(s.projection.sessionId); expect(e.scenarioVersionId).toBe(s.scenarioVersionId);
    if (e.quote) expect(e.quote.text).toBe(s.transcript[e.turnNumber - 1]!.playerText.slice(e.quote.start, e.quote.end));
  }
  return r;
}
async function prepare(page: Page) {
  await page.getByLabel('Моя цель').selectOption('target');
  await page.getByRole('checkbox', { name: /Я фиксирую свою альтернативу/ }).check();
  await page.getByRole('button', { name: 'Сохранить подготовку', exact: true }).click();
  await expect(page.getByText(/Подготовка сохранена:/)).toBeVisible();
}
async function begin(page: Page, scenario: 'S1' | 'S2', width: number, prepared = true) {
  await page.setViewportSize({ width, height: 900 }); await page.goto(server!.origin + '/admin');
  await page.getByRole('button', { name: scenario + ' — ' + (scenario === 'S1' ? S1.title : S2.title), exact: true }).click();
  await page.getByRole('button', { name: 'Опубликовать ' + scenario, exact: true }).click();
  await page.getByRole('button', { name: 'Открыть брифинг', exact: true }).click();
  if (prepared) await prepare(page);
  await page.getByRole('button', { name: 'Начать переговоры', exact: true }).click();
  await expect(page.getByTestId('revision')).toHaveText('Ход 0 из 8');
}
async function move(page: Page, kind: string, label?: string, value?: string) {
  const before = await snapshot(page);
  await page.getByLabel('Что вы хотите сделать?').selectOption(kind);
  if (label && value) await page.getByLabel(label).selectOption(value);
  await page.getByRole('button', { name: 'Отправить ход', exact: true }).click();
  await expect(page.getByTestId('turn')).toHaveCount(before.projection.revision + 1);
}
async function leave(page: Page) {
  await page.getByLabel('Что вы хотите сделать?').selectOption('walk_away');
  await page.getByRole('button', { name: 'Подтвердить выход…', exact: true }).click();
  await page.getByRole('button', { name: 'Выйти без сделки', exact: true }).click();
  await expect(page.getByTestId('result')).toBeVisible();
}
async function propose(page: Page, values: [string, string][], condition?: string) {
  const before = await snapshot(page);
  await page.getByLabel('Что вы хотите сделать?').selectOption('offer');
  for (const [label, value] of values) await page.getByLabel(label).selectOption(value);
  if (condition) await page.getByLabel('Встречное условие').selectOption(condition);
  await page.getByRole('button', { name: 'Проверить предложение', exact: true }).click();
  await page.getByRole('button', { name: 'Отправить предложение', exact: true }).click();
  await expect(page.getByTestId('turn')).toHaveCount(before.projection.revision + 1);
}
const supply = (price: string, delivery: string, prepay: string): [string, string][] =>
  [['Цена за партию (тыс. условных единиц)', price], ['Поставка (график партии)', delivery], ['Предоплата (%)', prepay]];
const workload = (scope: string, days: string, help: string, defer: string): [string, string][] =>
  [['Объём (часов работы)', scope], ['Срок (рабочих дней)', days], ['Помощник (6 часов ресурса)', help], ['Перенос отчёта (6 часов ресурса)', defer]];
async function screenshot(page: Page, name: string) {
  const size = await page.evaluate(() => ({ width: innerWidth, overflow: document.documentElement.scrollWidth - innerWidth }));
  expect(size.overflow).toBeLessThanOrEqual(0); evidence.layouts.push({ name, ...size });
  const target = name.includes('evidence') || name.includes('no-agreement') ? page.getByTestId('check-value.mutual')
    : name.includes('reciprocal') ? page.getByTestId('check-concession.reciprocal') : name.includes('noncomparable') ? page.getByTestId('comparison') : page.getByTestId('feedback');
  await target.evaluate(e => e.scrollIntoView({ block: 'start' }));
  const path = '.tools/' + name + '.png'; await page.screenshot({ path }); evidence.screenshots.push(path);
}
async function evidenceLink(page: Page) {
  const dimension = page.getByTestId('dimension-value'); await dimension.locator('summary').click();
  const finding = page.getByTestId('check-value.mutual');
  const link = finding.getByRole('link').first(); await dimension.locator('summary').focus();
  await page.keyboard.press('Tab'); await expect(link).toBeFocused();
  expect(await link.evaluate(e => getComputedStyle(e).outlineStyle)).not.toBe('none');
  const href = await link.getAttribute('href'); await page.keyboard.press('Enter');
  await expect(page.locator(href!)).toBeFocused(); await expect(page.locator(href!)).toBeInViewport();
}
test('S1 real early exit then prepared replay applies the suggested question and compares shared checks at 390px', async ({ page }) => {
  await start(); await begin(page, 'S1', 390, false); await leave(page);
  const original = await snapshot(page), first = await report(page);
  expect(first.overall.score).toBeNull(); expect(first.suggestions[0]?.action).toMatchObject({ kind: 'question', primaryTopicId: 'logistics' });
  await screenshot(page, 'g6-insufficient-390');
  await page.getByRole('button', { name: 'Повторить ту же ситуацию' }).click(); await prepare(page);
  await page.getByRole('button', { name: 'Начать переговоры', exact: true }).click();
  await move(page, 'question', 'Тема вопроса', 'logistics');
  await move(page, 'acknowledge', 'Какой факт вы признаёте?', 'logistics-saving');
  await move(page, 'argument', 'На что вы хотите сослаться?', 'logistics-argument');
  await move(page, 'question', 'Тема вопроса', 'payment');
  await propose(page, supply('95', 'split40at7_rest14', '50'));
  const next = await report(page); expect(next.overall.score).toBe(100); expect(next.outcome.playerUtility).toBe(64);
  await evidenceLink(page); await screenshot(page, 'g6-s1-evidence-390');
  await page.getByRole('button', { name: 'Сравнить с предыдущей попыткой', exact: true }).click();
  await expect(page.getByTestId('comparison')).toContainText('Показаны только общие наблюдаемые проверки');
  await expect(page.getByTestId('comparison')).toContainText('Не выполнено → Выполнено');
  const old = await page.request.get(server!.origin + '/api/sessions/' + original.projection.sessionId);
  expect(await old.json()).toEqual(original);
});
test('S2 full guided agreement renders report, exact evidence and stable refresh/restart at 1280px', async ({ page }) => {
  await start(); await begin(page, 'S2', 1280);
  await move(page, 'question', 'Тема вопроса', 'priorities'); await move(page, 'question', 'Тема вопроса', 'resources');
  await move(page, 'acknowledge', 'Какой факт вы признаёте?', 'report-deferrable');
  await move(page, 'argument', 'На что вы хотите сослаться?', 'resource-argument');
  await propose(page, workload('full', '2', '1', '1'));
  const before = await snapshot(page), r = await report(page);
  expect(r.outcome.playerUtility).toBe(47); expect(r.overall.score).toBe(100);
  await screenshot(page, 'g6-s2-report-1280'); await evidenceLink(page);
  await page.reload(); expect(await report(page)).toEqual(r);
  await server!.stop(); await server!.start(); await page.reload();
  expect(await report(page)).toEqual(r); expect(await snapshot(page)).toEqual(before);
});
test('S2 poor agreement keeps utility separate from process 44.12 at 360px', async ({ page }) => {
  await start(); await begin(page, 'S2', 360);
  await move(page, 'question', 'Тема вопроса', 'resources'); await move(page, 'acknowledge', 'Какой факт вы признаёте?', 'helper-available');
  await propose(page, workload('core', '5', '0', '0'));
  const r = await report(page); expect(r.outcome.family).toBe('POOR_AGREEMENT'); expect(r.outcome.playerUtility).toBe(20);
  expect(r.overall.score).toBe(44.12); await expect(page.getByTestId('process-score')).toHaveText('Процесс: 44.12 из 100');
  await screenshot(page, 'g6-poor-report-360');
});
test('S1 no agreement retains grounded process credit with independently expected 70', async ({ page }) => {
  await start(); await begin(page, 'S1', 360);
  await propose(page, supply('95', 'split40at7_rest14', '50'));
  await move(page, 'question', 'Тема вопроса', 'logistics'); await move(page, 'acknowledge', 'Какой факт вы признаёте?', 'logistics-saving');
  await move(page, 'argument', 'На что вы хотите сослаться?', 'logistics-argument'); await leave(page);
  const r = await report(page); expect(r.outcome.family).toBe('NO_AGREEMENT'); expect(r.overall.score).toBe(70);
  await evidenceLink(page); await screenshot(page, 'g6-no-agreement-360');
});
test('network failure fetching feedback keeps terminal facts, actionable error and retry intact at 390px', async ({ page }) => {
  await start(); await begin(page, 'S2', 390); let fail = true;
  await page.route('**/feedback?revision=*', async route => { if (fail) await route.abort('failed'); else await route.continue(); });
  await move(page, 'pressure', 'Тон реплики', 'threat'); await leave(page);
  await expect(page.getByRole('alert')).toContainText('Результат и история попытки сохранены');
  const before = await snapshot(page); await screenshot(page, 'g6-fetch-error-390');
  fail = false; const retry = page.getByRole('button', { name: 'Повторить загрузку разбора' });
  await retry.focus(); await page.keyboard.press('Enter');
  const r = await report(page); expect(r.overall.score).toBeNull();
  expect(r.suggestions[0]?.action).toMatchObject({ kind: 'pressure', tone: 'respectful_firm' });
  expect(await snapshot(page)).toEqual(before); await page.reload(); expect(await report(page)).toEqual(r);
});
test('legacy v2 S1/S2 records migrate intact and mismatched replay version renders separate factual outcomes', async ({ page }) => {
  const temp = temporaryDatabase(), file = join(temp.directory, 'legacy.sqlite'), db = new Database(file);
  let oldS1: ReturnType<SessionService['create']>, oldS2: ReturnType<SessionService['create']>, mismatch: ReturnType<SessionService['create']>;
  try {
    db.pragma('foreign_keys = ON');
    db.exec("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT 'legacy') STRICT; CREATE TABLE foundation_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL) STRICT;");
    db.exec(g2Migration.sql); db.exec("INSERT INTO schema_migrations(version,name) VALUES(1,'foundation_metadata'),(2,'s1_sessions_turns');");
    const repo = new ArenaRepository(db), sessions = new SessionService(repo);
    const action = { kind: 'walk_away' as const, tone: 'neutral' as const, acknowledgementFactId: null, argumentId: null, contradictsFactId: null, evidenceRefs: [] };
    oldS1 = sessions.create(repo.publish(S1).id); oldS1 = sessions.playTurn(oldS1.projection.sessionId, { requestId: randomUUID(), expectedRevision: 0, action });
    oldS2 = sessions.create(repo.publish(S2).id); oldS2 = sessions.playTurn(oldS2.projection.sessionId, { requestId: randomUUID(), expectedRevision: 0, action });
    const different = structuredClone(S1); different.configFingerprint = 'synthetic-app-version-two';
    const version = repo.publish(different), id = randomUUID();
    repo.insertSession(createInitialState(different, { sessionId: id, scenarioVersionId: version.id }), oldS1.projection.sessionId);
    mismatch = sessions.playTurn(id, { requestId: randomUUID(), expectedRevision: 0, action });
  } finally { db.close(); }
  try {
    await start(file); await page.setViewportSize({ width: 1280, height: 900 });
    for (const saved of [oldS1!, oldS2!]) {
      await page.goto(server!.origin + '/session/' + saved.projection.sessionId + '/result');
      expect(await snapshot(page)).toEqual(saved); const r = await report(page);
      expect(r.preparation).toBeNull(); expect(r.overall.score).toBeNull();
    }
    await page.goto(server!.origin + '/session/' + mismatch!.projection.sessionId + '/result');
    await report(page); await page.getByRole('button', { name: 'Сравнить с предыдущей попыткой', exact: true }).click();
    await expect(page.getByTestId('comparison')).toContainText('Оценки процесса несопоставимы');
    await expect(page.getByTestId('comparison')).toContainText('Ранее: Соглашение не достигнуто. Сейчас: Соглашение не достигнуто.');
    await screenshot(page, 'g6-noncomparable-1280');
    const inspect = new Database(server!.database, { readonly: true });
    try { expect(inspect.prepare('SELECT version FROM schema_migrations ORDER BY version').all()).toEqual([{ version: 1 }, { version: 2 }, { version: 3 }]); }
    finally { inspect.close(); }
  } finally { temp.cleanup(); }
});

test('guided genuine conditional exchange is committed, explained and linked at 360px', async ({ page }) => {
  await start(); await begin(page, 'S1', 360);
  await propose(page, supply('100', 'all7', '0'));
  await propose(page, supply('95', 'split40at7_rest14', '50'), 'PRICE');
  await leave(page);
  const r = await report(page), check = r.dimensions.flatMap(d => d.checks).find(c => c.id === 'concession.reciprocal')!;
  expect(check.status).toBe('passed');
  const saved = await snapshot(page); expect(saved.transcript[1]!.playerText).toContain('Встречное условие: Цена за партию: 95.');
  await page.getByTestId('dimension-concession').locator('summary').click();
  const finding = page.getByTestId('check-concession.reciprocal');
  await expect(finding).toContainText('Выполнено');
  const second = finding.getByRole('link').nth(1); await second.focus(); await page.keyboard.press('Enter');
  await expect(page.locator('#turn-2')).toBeFocused();
  await screenshot(page, 'g6-reciprocal-360');
});
