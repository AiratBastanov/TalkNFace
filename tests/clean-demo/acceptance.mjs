// Run with Node 24 from a tooling checkout; target must be fresh authoritative source.
// No runtime, npm cache, database, environment or build files are copied into the target.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { randomBytes, createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { once } from 'node:events';
import os from 'node:os';
import { chromium, expect } from '@playwright/test';

const target = path.resolve(process.argv[2] ?? '.');
const reuse = process.argv.includes('--prepared'); // Explicit development rerun; never fresh-source evidence.
const preparedByPrompt = process.argv.includes('--prepared-by-prompt');
const port = process.argv.includes('--archive') ? 3101 : 3100;
const origin = `http://127.0.0.1:${port}`;
let password = randomBytes(24).toString('base64url') + 'Ж';
if (preparedByPrompt) {
  password = ''; process.stdin.setEncoding('utf8');
  for await (const chunk of process.stdin) { password += chunk; if (password.length > 256) throw Error('Invalid acceptance password input'); }
  password = password.replace(/\r?\n$/, '');
}
const evidence = { schema: 1, platform: `${os.platform()} ${os.release()} ${os.arch()}`, fresh: !reuse,
  withoutGit: !fs.existsSync(path.join(target, '.git')), absentBefore: [], commands: [], tests: [], screenshots: [], externalRequests: [], pageErrors: [] };
const absent = ['node_modules', '.tools', '.tmp', '.local', '.env', 'apps/server/node_modules', 'apps/server/dist', 'apps/web/dist',
  'packages/contracts/dist', 'packages/domain/dist', 'packages/scenarios/dist', 'AlagModels', 'AlagDatasets'];
if (!reuse && !preparedByPrompt) for (const relative of absent) { assert(!fs.existsSync(path.join(target, relative)), `Fresh target contains ${relative}`); evidence.absentBefore.push(relative); }
if (preparedByPrompt) evidence.preparation = 'Exact documented -Prepare with real hidden interactive prompt; pre-bootstrap absence/timing recorded by outer source-acquisition receipt';
const artifact = path.join(target, '.local/arena-demo/acceptance');
let browser, phase = 'preparation', globalTimer;
const digest = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const save = () => { fs.mkdirSync(artifact, { recursive: true }); fs.writeFileSync(path.join(artifact, reuse ? 'rerun.json' : 'result.json'), JSON.stringify(evidence, null, 2)); };
async function command(args, input, timeout = 30_000) {
  const start = Date.now();
  const result = await new Promise((resolve, reject) => {
    const child = spawn('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', '.\\scripts\\windows-demo.ps1', ...args],
      { cwd: target, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'], env: { ...process.env, NODE_OPTIONS: '', NODE_PATH: '' } });
    let out = '', err = '';
    const timer = setTimeout(() => { child.kill(); reject(Error('Documented command timed out')); }, timeout);
    child.stdout.on('data', b => { out += b; process.stdout.write(b); }); child.stderr.on('data', b => { err += b; process.stderr.write(b); });
    child.once('error', reject); child.once('exit', code => { clearTimeout(timer); child.stdout.destroy(); child.stderr.destroy(); resolve({ code, out, err }); });
    child.stdin.end(input ?? '');
  });
  evidence.commands.push({ arguments: args, seconds: (Date.now() - start) / 1000, exitCode: result.code });
  assert.equal(result.code, 0, 'Documented launcher command failed'); return result.out;
}
async function scenario(name, fn) {
  phase = name; const start = Date.now(); let timer;
  try {
    await Promise.race([fn(), new Promise((_, reject) => { timer = setTimeout(() => reject(Error('90s case budget exceeded')), 90_000); })]);
    evidence.tests.push({ name, status: 'passed', seconds: (Date.now() - start) / 1000 });
  } catch (e) { evidence.tests.push({ name, status: 'failed', seconds: (Date.now() - start) / 1000 }); throw e; }
  finally { clearTimeout(timer); save(); }
}
async function watch(context) {
  context.on('request', req => { if (/^https?:/.test(req.url()) && new URL(req.url()).origin !== origin) evidence.externalRequests.push(new URL(req.url()).origin); });
  context.on('page', page => page.on('pageerror', () => evidence.pageErrors.push('pageerror')));
}
async function shot(page, name) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: path.join(artifact, name + '.png') }); evidence.screenshots.push(name + '.png');
}
async function snapshot(page) {
  const id = /\/session\/([^/]+)/.exec(page.url())?.[1]; assert(id, 'Expected session route');
  const response = await page.request.get(`${origin}/api/sessions/${id}`); assert.equal(response.status(), 200);
  return response.json();
}
async function post(page, url, body) {
  const auth = await (await page.request.get(origin + '/api/auth/session')).json();
  return page.request.post(url, { data: body, headers: { Origin: origin, 'X-CSRF-Token': auth.csrfToken } });
}
async function move(page, kind, label, value) {
  const before = await snapshot(page);
  await page.getByLabel('Что вы хотите сделать?').selectOption(kind);
  await page.getByLabel(label).selectOption(value);
  await page.getByRole('button', { name: 'Отправить ход', exact: true }).click();
  await expect(page.getByTestId('turn')).toHaveCount(before.projection.revision + 1);
}
let admin, player, outsider, adminPage, playerPage, otherPage, s1ReportUrl, s1Report, replayUrl;
try {
  const setupAt = Date.now();
  if (reuse) { await command(['-Stop']); await command(['-SetAdminPassword', '-PasswordFromStdin'], password); }
  else if (!preparedByPrompt) await command(['-Prepare', '-PasswordFromStdin'], password, 970_000);
  evidence.prepare = JSON.parse(fs.readFileSync(path.join(target, '.local/arena-demo/prepared.json')));
  // Keep aggregate timings, not build hashes or local configuration in the public receipt.
  evidence.prepare = { node: evidence.prepare.node, npm: evidence.prepare.npm, dependencies: evidence.prepare.dependencies, timings: evidence.prepare.timings };
  await command(['-Start', '-Port', String(port)]);
  evidence.totalSetupSeconds = (Date.now() - setupAt) / 1000;
  evidence.handsOn = { commands: 2, hiddenPasswordEntries: 2, automation: preparedByPrompt ? 'Real hidden interactive Prepare; test password reaches Chrome harness through memory/stdin only' : 'UTF-8 stdin substitutes hidden password entry; no password argument or fixture hash' };
  fs.mkdirSync(artifact, { recursive: true });
  browser = await chromium.launch({ channel: 'chrome', headless: true }); evidence.browser = browser.version();
  globalTimer = setTimeout(() => { console.error('Clean Chrome journey exceeded 300s'); process.exitCode = 1; void browser.close(); }, 300_000);
  if (process.argv.includes('--archive')) {
    assert(evidence.withoutGit, 'Archive smoke requires no .git');
    await scenario('Tracked source without .git bootstraps, builds, starts and authenticates in Chrome', async () => {
      const context = await browser.newContext(); await watch(context); const page = await context.newPage();
      await page.goto(origin + '/admin');
      await page.getByLabel('Пароль администратора', { exact: true }).fill(password);
      await page.getByRole('button', { name: 'Войти', exact: true }).click();
      await expect(page.getByRole('region', { name: 'Настроить контекст' })).toBeVisible();
      assert.equal((await page.request.get(origin + '/ready')).status(), 200);
      await shot(page, 'archive-admin-ready'); await context.close();
    });
    assert.deepEqual(evidence.externalRequests, []); evidence.status = 'passed';
  } else {
  admin = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  player = await browser.newContext({ viewport: { width: 390, height: 900 } });
  outsider = await browser.newContext({ viewport: { width: 390, height: 900 } });
  for (const context of [admin, player, outsider]) { await watch(context); context.setDefaultTimeout(5000); context.setDefaultNavigationTimeout(10000); }
  adminPage = await admin.newPage(); playerPage = await player.newPage(); otherPage = await outsider.newPage();
  for (const family of ['S1', 'S2']) await scenario(`${family} configured publish, preparation, guided negotiation, G6 evidence and replay`, async () => {
    await adminPage.goto(origin + '/admin');
    if (family === 'S1') {
      await shot(adminPage, 'clean-admin-login');
      const before = (await admin.cookies(origin)).find(c => c.name === 'arena_session');
      await adminPage.getByLabel('Пароль администратора', { exact: true }).fill(password);
      await adminPage.getByRole('button', { name: 'Войти', exact: true }).click();
      await expect(adminPage.getByRole('button', { name: 'Выйти', exact: true })).toBeVisible();
      const cookie = (await admin.cookies(origin)).find(c => c.name === 'arena_session');
      assert(cookie.httpOnly && cookie.sameSite === 'Strict' && cookie.path === '/' && !cookie.secure && cookie.value !== before.value, 'G8 cookie/rotation');
      assert(!(await adminPage.evaluate(() => document.cookie)).includes(cookie.value), 'HttpOnly');
      evidence.adminCookie = { httpOnly: true, sameSite: 'Strict', path: '/', secure: false, rotated: true, readableFromScript: false };
    }
    const workspace = adminPage.getByRole('region', { name: 'Настроить контекст' });
    const settings = family === 'S1' ? ['supply', 'planned', 'normal', 'friendly', 'director', 'margin'] : ['team', 'urgent', 'advanced', 'friendly', 'team_lead', 'deliver_scope'];
    const labels = ['Сфера', 'Тема', 'Сложность', 'Тон оппонента', 'Роль оппонента', 'Цели оппонента'];
    for (let i = 0; i < labels.length; i++) await workspace.getByLabel(labels[i], { exact: true }).selectOption(settings[i]);
    await workspace.getByRole('button', { name: 'Сохранить черновик', exact: true }).click();
    await expect(workspace.getByText('Черновик сохранён. Требуется новая проверка.')).toBeVisible();
    await workspace.getByRole('button', { name: 'Подобрать и проверить сценарий' }).click();
    await expect(workspace.getByText(/Сценарий проверен\./)).toBeVisible();
    await workspace.getByRole('button', { name: 'Предпросмотр', exact: true }).click();
    await shot(adminPage, 'clean-preview-' + family);
    await workspace.getByRole('checkbox', { name: /Я проверил/ }).check();
    await workspace.getByRole('button', { name: 'Опубликовать', exact: true }).click();
    await expect(workspace.getByText(/Настроенная версия опубликована/)).toBeVisible();
    // Registration-free, separate player context. Choose the newly published family's catalog option.
    await playerPage.goto(origin + '/');
    const catalog = await (await playerPage.request.get(origin + '/api/scenarios')).json();
    // Product catalog is a list of buttons; its visible order follows the returned public catalog.
    const buttons = playerPage.getByRole('button', { name: 'Выбрать ситуацию', exact: true });
    await expect(buttons).toHaveCount(catalog.length);
    const wantedIndex = family === 'S1' ? 0 : catalog.findIndex(x => JSON.stringify(x).includes('G5-S2-'));
    assert(wantedIndex >= 0, 'Configured family is present in public catalog');
    await buttons.nth(wantedIndex).click();
    await playerPage.getByLabel('Моя цель').selectOption('target');
    await playerPage.getByRole('checkbox', { name: /Я фиксирую свою альтернативу/ }).check();
    await playerPage.getByRole('button', { name: 'Сохранить подготовку', exact: true }).click();
    await expect(playerPage.getByText(/Подготовка сохранена:/)).toBeVisible();
    await playerPage.getByRole('button', { name: 'Начать переговоры', exact: true }).click();
    const initial = await snapshot(playerPage), id = initial.projection.sessionId;
    await otherPage.goto(origin + '/session/' + id);
    await expect(otherPage.getByRole('alert')).toContainText('Попытка недоступна');
    assert.equal((await otherPage.request.get(origin + '/api/sessions/' + id)).status(), 404);
    assert.equal((await otherPage.request.get(origin + '/api/admin/context-draft')).status(), 403);
    const rejected = await playerPage.evaluate(async id => {
      const r = await fetch('/api/sessions/' + id + '/preparation', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      return { status: r.status, code: (await r.json()).code };
    }, id);
    assert(rejected.status === 403 && rejected.code === 'CSRF_REJECTED', 'Missing CSRF remains rejected');
    assert(digest(await snapshot(playerPage)) === digest(initial), 'CSRF rejection is non-mutating');
    if (family === 'S1') {
      await shot(otherPage, 'clean-foreign-uuid');
      await move(playerPage, 'question', 'Тема вопроса', 'logistics');
      await move(playerPage, 'acknowledge', 'Какой факт вы признаёте?', 'logistics-saving');
      await move(playerPage, 'argument', 'На что вы хотите сослаться?', 'logistics-argument');
      await move(playerPage, 'question', 'Тема вопроса', 'payment');
    } else {
      await move(playerPage, 'question', 'Тема вопроса', 'priorities');
      await move(playerPage, 'question', 'Тема вопроса', 'resources');
      await move(playerPage, 'acknowledge', 'Какой факт вы признаёте?', 'report-deferrable');
      await move(playerPage, 'argument', 'На что вы хотите сослаться?', 'resource-argument');
    }
    await playerPage.getByLabel('Что вы хотите сделать?').selectOption('offer');
    const values = family === 'S1' ? [['Цена за партию (тыс. условных единиц)', '95'], ['Поставка (график партии)', 'split40at7_rest14'], ['Предоплата (%)', '50']]
      : [['Объём (часов работы)', 'full'], ['Срок (рабочих дней)', '2'], ['Помощник (6 часов ресурса)', '1'], ['Перенос отчёта (6 часов ресурса)', '1']];
    for (const [label, value] of values) await playerPage.getByLabel(label).selectOption(value);
    await playerPage.getByRole('button', { name: 'Проверить предложение', exact: true }).click();
    await playerPage.getByRole('button', { name: 'Отправить предложение', exact: true }).click();
    await expect(playerPage.getByTestId('process-score')).toBeVisible();
    const terminal = await snapshot(playerPage), reportUrl = `${origin}/api/sessions/${id}/feedback?revision=${terminal.projection.revision}`;
    const report = await (await playerPage.request.get(reportUrl)).json();
    assert.equal(report.outcome.playerUtility, family === 'S1' ? 64 : 47); assert.equal(report.overall.score, 100);
    await playerPage.getByTestId('feedback').scrollIntoViewIfNeeded(); await shot(playerPage, 'clean-feedback-' + family);
    assert.equal((await otherPage.request.get(reportUrl)).status(), 404);
    assert.equal((await post(otherPage, origin + '/api/sessions/' + id + '/replay', {})).status(), 404);
    await playerPage.getByTestId('dimension-value').locator('summary').click();
    const link = playerPage.getByTestId('check-value.mutual').getByRole('link').first(); await link.focus(); await playerPage.keyboard.press('Enter');
    await expect(playerPage.locator(await link.getAttribute('href'))).toBeFocused();
    await playerPage.getByRole('button', { name: 'Повторить ту же ситуацию' }).click(); await expect(playerPage).toHaveURL(/\/briefing$/);
    const replay = await snapshot(playerPage);
    assert(replay.replayOf === id && replay.scenarioVersionId === terminal.scenarioVersionId, 'Replay is linked to the same immutable publication');
    for (const p of [adminPage, playerPage, otherPage]) {
      const storage = await p.evaluate(() => JSON.stringify({ local: { ...localStorage }, tab: { ...sessionStorage }, cookie: document.cookie }));
      const cookie = (await p.context().cookies(origin)).find(c => c.name === 'arena_session');
      const auth = await (await p.request.get(origin + '/api/auth/session')).json();
      const hash = JSON.parse(fs.readFileSync(path.join(target, '.local/arena-config/admin.json'))).adminPasswordHash;
      assert(![password, hash, cookie?.value, auth.csrfToken].filter(Boolean).some(secret => storage.includes(secret)), 'No secrets in browser storage');
      const assets = fs.readdirSync(path.join(target, 'apps/web/dist/assets')).filter(n => n.endsWith('.js')).map(n => fs.readFileSync(path.join(target, 'apps/web/dist/assets', n), 'utf8')).join('');
      assert(![password, hash, cookie?.value, auth.csrfToken].filter(Boolean).some(secret => assets.includes(secret)), 'No secrets in source bundle');
    }
    if (family === 'S1') { s1ReportUrl = reportUrl; s1Report = report; replayUrl = playerPage.url(); }
  });
  await scenario('Stop/Start preserves publication, draft, turns, G6 report, replay and valid access', async () => {
    const catalog = await (await adminPage.request.get(origin + '/api/scenarios')).json();
    const draft = await (await adminPage.request.get(origin + '/api/admin/context-draft')).json();
    await playerPage.goto(replayUrl); const before = await snapshot(playerPage);
    await command(['-Stop']); await command(['-Start', '-Port', String(port)]);
    await playerPage.reload(); assert(digest(await snapshot(playerPage)) === digest(before), 'Replay survives restart');
    assert(digest(await (await playerPage.request.get(s1ReportUrl)).json()) === digest(s1Report), 'G6 report survives restart');
    assert(digest(await (await adminPage.request.get(origin + '/api/scenarios')).json()) === digest(catalog), 'Publications survive restart');
    assert(digest(await (await adminPage.request.get(origin + '/api/admin/context-draft')).json()) === digest(draft), 'Admin draft/access survives restart');
    await playerPage.getByLabel('Моя цель').selectOption('target');
    await playerPage.getByRole('checkbox', { name: /Я фиксирую свою альтернативу/ }).check();
    await playerPage.getByRole('button', { name: 'Сохранить подготовку', exact: true }).click();
    await expect(playerPage.getByText(/Подготовка сохранена:/)).toBeVisible();
    await playerPage.getByRole('button', { name: 'Начать переговоры', exact: true }).click();
    await move(playerPage, 'question', 'Тема вопроса', 'logistics'); await shot(playerPage, 'clean-continued-after-restart');
    evidence.restart = { reportEquivalent: true, publication: true, draft: true, replay: true, continuedTurn: true, adminAndPlayerAccess: true };
  });
  await scenario('Safe live backup and stopped restore preserve data without reviving logout', async () => {
    const before = await snapshot(playerPage);
    const output = await command(['-Backup']); const id = /Verified backup: (\S+)/.exec(output)?.[1]; assert(id);
    const oldOtherCookie = (await outsider.cookies(origin)).find(c => c.name === 'arena_session');
    await post(otherPage, origin + '/api/auth/logout', {});
    await command(['-Stop']); await command(['-Restore', id], undefined, 60_000); await command(['-Start', '-Port', String(port)]);
    assert(digest(await snapshot(playerPage)) === digest(before), 'SQLite restored attempt byte-equivalent');
    assert(digest(await (await playerPage.request.get(s1ReportUrl)).json()) === digest(s1Report), 'SQLite restored G6 report');
    await outsider.addCookies([oldOtherCookie]);
    assert.equal((await otherPage.request.get(origin + '/api/auth/session')).status(), 401, 'Restore must not revive logout');
    evidence.backupRestore = { liveSqliteBackup: true, integrityVerified: true, previousDbPreserved: true, resultEquivalent: true, logoutStillRevoked: true };
  });
  await scenario('Real Chrome foreign Origin and wrong CSRF cannot publish', async () => {
    const catalog = await (await adminPage.request.get(origin + '/api/scenarios')).json();
    // Separate intentionally foreign page; excluded from the gameplay network observation.
    const foreignContext = await browser.newContext(); const foreignPage = await foreignContext.newPage();
    const foreign = createServer((_q, r) => { r.setHeader('Content-Type', 'text/html'); r.end('<!doctype html><title>Origin boundary test</title>'); });
    foreign.listen(0, '127.0.0.1'); await once(foreign, 'listening');
    try {
      await foreignPage.goto(`http://localhost:${foreign.address().port}`);
      const response = foreignPage.waitForResponse(r => r.url() === origin + '/api/admin/reference-scenarios/s1/publish');
      await foreignPage.evaluate(async base => { await fetch(base + '/api/admin/reference-scenarios/s1/publish', { method: 'POST', mode: 'no-cors', credentials: 'include', headers: { 'Content-Type': 'text/plain' }, body: '{}' }); }, origin);
      assert.equal((await response).status(), 403);
      await adminPage.goto(origin + '/admin');
      const code = await adminPage.evaluate(async () => (await fetch('/api/admin/reference-scenarios/s1/publish', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': 'wrong' }, body: '{}' })).status);
      assert.equal(code, 403); assert(digest(await (await adminPage.request.get(origin + '/api/scenarios')).json()) === digest(catalog), 'Security rejection preserved publications');
    } finally { await foreignContext.close(); foreign.closeAllConnections(); await new Promise(resolve => foreign.close(resolve)); }
  });
  assert.deepEqual(evidence.externalRequests, []); assert.deepEqual(evidence.pageErrors, []);
  evidence.status = 'passed'; evidence.security = { ownership404: true, playerAdmin403: true, csrf403: true, origin403: true, noSecretsInStorageOrBundle: true, noExternalGameplayRequests: true };
  }
} catch (e) {
  evidence.status = 'failed'; evidence.failedPhase = phase;
  // Never dump Playwright call logs: they can include password fills or request headers.
  console.error(`Acceptance failed in ${phase} (${e.name}).`);
  console.error((e.stack ?? '').split('\n').filter(line => /acceptance\.mjs:\d/.test(line)).join('\n'));
  process.exitCode = 1;
} finally {
  clearTimeout(globalTimer); await browser?.close();
  try { await command(['-Stop']); } catch { process.exitCode = 1; }
  save(); console.log('Acceptance result: ' + evidence.status + '; unique cases executed: ' + evidence.tests.length);
}
