import { mkdirSync, writeFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { DraftSchema, ContextPublicationSchema } from '@arena/contracts/context-config';
import { SessionViewSchema } from '@arena/contracts/g2';
import { FeedbackReportSchema } from '@arena/contracts/feedback';
import { productionHarness } from './production.ts';

let server: Awaited<ReturnType<typeof productionHarness>> | undefined;
const evidence = { browser:'', cases:[] as string[], layouts:[] as {name:string;width:number;overflow:number}[],
  screenshots:[] as string[], external:[] as string[], errors:[] as string[], productions:[] as unknown[] };
test.beforeEach(async ({context,page,browser})=>{
  evidence.browser=browser.version();
  server=await productionHarness({label:'g5-context-'+evidence.cases.length});await server.start();
  await context.route('**/*',async route=>{
    const url=route.request().url();
    if(/^https?:/.test(url)&&new URL(url).origin!==server!.origin){evidence.external.push(url);await route.abort();}
    else await route.continue();
  });
  page.on('pageerror',e=>evidence.errors.push(e.message));
});
test.afterEach(async ({}, info)=>{
  if(server){await server.stop();evidence.productions.push(server.evidence());server.cleanup();server=undefined;}
  if(info.status==='passed')evidence.cases.push(info.title);
  mkdirSync('.tools',{recursive:true});writeFileSync('.tools/g5-browser-evidence.json',JSON.stringify(evidence,null,2));
});
test.afterAll(()=>{expect(evidence.external).toEqual([]);expect(evidence.errors).toEqual([]);});
const workspace=(page:Page)=>page.getByRole('region',{name:'Настроить контекст'});
async function open(page:Page,width=1280){
  await page.setViewportSize({width,height:1000});await page.goto(server!.origin+'/admin');
  await expect(workspace(page).getByLabel('Сфера',{exact:true})).toHaveValue('supply');
}
async function save(page:Page){
  await workspace(page).getByRole('button',{name:'Сохранить черновик',exact:true}).click();
  await expect(workspace(page).getByText('Черновик сохранён. Требуется новая проверка.')).toBeVisible();
}
async function validate(page:Page){
  await workspace(page).getByRole('button',{name:'Подобрать и проверить сценарий',exact:true}).click();
  await expect(workspace(page).getByText(/Сценарий проверен\./)).toBeVisible();
}
async function preview(page:Page){
  await workspace(page).getByRole('button',{name:'Предпросмотр',exact:true}).click();
  await expect(workspace(page).getByRole('region',{name:'Предпросмотр сценария'})).toBeVisible();
}
async function approve(page:Page){
  await workspace(page).getByRole('checkbox',{name:/Я проверил/}).check();
}
async function publish(page:Page){
  await approve(page);await workspace(page).getByRole('button',{name:'Опубликовать',exact:true}).click();
  await expect(workspace(page).getByText(/Настроенная версия опубликована/)).toBeVisible();
}
async function draft(page:Page){
  const r=await page.request.get(server!.origin+'/api/admin/context-draft');expect(r.status()).toBe(200);return DraftSchema.parse(await r.json());
}
async function snap(page:Page){
  const id=/\/session\/([^/]+)/.exec(page.url())![1]!;
  const r=await page.request.get(server!.origin+'/api/sessions/'+id);expect(r.status()).toBe(200);return SessionViewSchema.parse(await r.json());
}
async function report(page:Page){
  await expect(page.getByTestId('process-score')).toBeVisible();
  const s=await snap(page),r=await page.request.get(server!.origin+'/api/sessions/'+s.projection.sessionId+'/feedback?revision='+s.projection.revision);
  expect(r.status()).toBe(200);const result=FeedbackReportSchema.parse(await r.json());
  expect(result.scenarioVersionId).toBe(s.scenarioVersionId);
  for(const e of result.evidence)if(e.quote)expect(e.quote.text).toBe(s.transcript[e.turnNumber-1]!.playerText.slice(e.quote.start,e.quote.end));
  return result;
}
async function begin(page:Page){
  await workspace(page).getByRole('button',{name:'Начать настроенные переговоры'}).click();
  await page.getByLabel('Моя цель').selectOption('target');
  await page.getByRole('checkbox',{name:/Я фиксирую свою альтернативу/}).check();
  await page.getByRole('button',{name:'Сохранить подготовку',exact:true}).click();
  await expect(page.getByText(/Подготовка сохранена:/)).toBeVisible();
  await page.getByRole('button',{name:'Начать переговоры',exact:true}).click();
}
async function move(page:Page,kind:string,label:string,value:string){
  const before=await snap(page);
  await page.getByLabel('Что вы хотите сделать?').selectOption(kind);
  await page.getByLabel(label).selectOption(value);
  await page.getByRole('button',{name:'Отправить ход',exact:true}).click();
  await expect(page.getByTestId('turn')).toHaveCount(before.projection.revision+1);
}
async function offer(page:Page,values:[string,string][]){
  await page.getByLabel('Что вы хотите сделать?').selectOption('offer');
  for(const [label,value]of values)await page.getByLabel(label).selectOption(value);
  await page.getByRole('button',{name:'Проверить предложение',exact:true}).click();
  await page.getByRole('button',{name:'Отправить предложение',exact:true}).click();
  await expect(page.getByTestId('result')).toBeVisible();
}
async function exit(page:Page){
  await page.getByLabel('Что вы хотите сделать?').selectOption('walk_away');
  await page.getByRole('button',{name:'Подтвердить выход…',exact:true}).click();
  await page.getByRole('button',{name:'Выйти без сделки',exact:true}).click();
  await expect(page.getByTestId('result')).toBeVisible();
}
async function screenshot(page:Page,name:string,selector?:string){
  if(selector)await page.locator(selector).scrollIntoViewIfNeeded();
  const size=await page.evaluate(()=>({width:innerWidth,overflow:document.documentElement.scrollWidth-innerWidth}));
  expect(size.overflow).toBeLessThanOrEqual(0);evidence.layouts.push({name,...size});
  const path='.tools/'+name+'.png';await page.screenshot({path,fullPage:!selector});evidence.screenshots.push(path);
  if(!selector) { const viewportPath='.tools/'+name+'-viewport.png'; await page.screenshot({path:viewportPath}); evidence.screenshots.push(viewportPath); }
}

test('configured S1: real lost publication response, safe retry, preparation, G6 evidence and same-version replay',async({page})=>{
  await open(page);
  await workspace(page).getByLabel('Тема',{exact:true}).selectOption('planned');
  await workspace(page).getByLabel('Тон оппонента',{exact:true}).selectOption('friendly');
  await workspace(page).getByLabel('Цели оппонента',{exact:true}).selectOption('margin');
  await save(page);await validate(page);await preview(page);
  await screenshot(page,'g5-preview-1280');
  await approve(page);await page.setViewportSize({width:390,height:900});
  await screenshot(page,'g5-publication-controls-390','.approval');
  const payloads:unknown[]=[];
  await page.route('**/api/admin/context-draft/publish',async route=>{
    payloads.push(route.request().postDataJSON());
    const response=await route.fetch();expect(response.status()).toBe(200);
    // Only drop transport after real commit; no mocked compiler/publication body.
    await route.abort();
  });
  await workspace(page).getByRole('button',{name:'Опубликовать',exact:true}).click();
  await expect(workspace(page).getByRole('alert')).toContainText('Связь с приложением прервалась');
  await page.setViewportSize({width:390,height:900});await screenshot(page,'g5-publication-retry-390','.context-workspace [role=alert]');
  await page.unroute('**/api/admin/context-draft/publish');
  page.on('request',r=>{if(r.url().endsWith('/context-draft/publish'))payloads.push(r.postDataJSON());});
  await workspace(page).getByRole('button',{name:'Опубликовать',exact:true}).click();
  await expect(workspace(page).getByText(/Настроенная версия опубликована/)).toBeVisible();
  expect(payloads).toHaveLength(2);expect(payloads[1]).toEqual(payloads[0]);
  const publications=await page.request.get(server!.origin+'/api/scenarios');expect(await publications.json()).toHaveLength(1);
  await begin(page);
  await move(page,'question','Тема вопроса','logistics');await move(page,'acknowledge','Какой факт вы признаёте?','logistics-saving');
  await move(page,'argument','На что вы хотите сослаться?','logistics-argument');await move(page,'question','Тема вопроса','payment');
  await offer(page,[['Цена за партию (тыс. условных единиц)','95'],['Поставка (график партии)','split40at7_rest14'],['Предоплата (%)','50']]);
  const s=await snap(page),r=await report(page);expect(s.projection.scenario.topic).toBe('Плановая поставка');expect(r.outcome.playerUtility).toBe(64);expect(r.overall.score).toBe(100);
  expect(s.transcript[0]!.playerText).toContain('плановой поставки');
  const dimension=page.getByTestId('dimension-value');await dimension.locator('summary').click();
  const link=page.getByTestId('check-value.mutual').getByRole('link').first();
  await dimension.locator('summary').focus();await page.keyboard.press('Tab');await expect(link).toBeFocused();
  expect(await link.evaluate(e=>getComputedStyle(e).outlineStyle)).not.toBe('none');
  const href=await link.getAttribute('href');await page.keyboard.press('Enter');await expect(page.locator(href!)).toBeFocused();
  await screenshot(page,'g5-s1-evidence-390',href!);
  await page.getByRole('button',{name:'Повторить ту же ситуацию'}).click();
  await expect(page).toHaveURL(/\/briefing$/);
  const replay=await snap(page);expect(replay.scenarioVersionId).toBe(s.scenarioVersionId);expect(replay.replayOf).toBe(s.projection.sessionId);
  await page.getByRole('button',{name:'Начать переговоры',exact:true}).click();await exit(page);
  expect((await report(page)).overall.score).toBeNull();
  await page.getByRole('button',{name:'Сравнить с предыдущей попыткой',exact:true}).click();
  await expect(page.getByTestId('comparison')).toContainText('Показаны только общие наблюдаемые проверки');
  const old=await page.request.get(server!.origin+'/api/sessions/'+s.projection.sessionId+'/feedback?revision='+s.projection.revision);expect(await old.json()).toEqual(r);
});

test('configured S2: explicit dependencies, unavailable resources, valid lead goal, draft and active-session restart, G6',async({page})=>{
  await open(page,360);
  await workspace(page).getByLabel('Сфера',{exact:true}).selectOption('team');
  for(const label of ['Тема','Роль оппонента','Цели оппонента'])await expect(workspace(page).getByLabel(label,{exact:true})).toHaveValue('');
  await workspace(page).getByLabel('Тема',{exact:true}).selectOption('reprioritize');
  await workspace(page).getByLabel('Роль оппонента',{exact:true}).selectOption('team_lead');
  await workspace(page).getByLabel('Цели оппонента',{exact:true}).selectOption('deliver_scope');
  await workspace(page).getByLabel('Сложность',{exact:true}).selectOption('advanced');
  await workspace(page).getByLabel('Тон оппонента',{exact:true}).selectOption('friendly');
  await save(page);
  await workspace(page).getByRole('button',{name:'Подобрать и проверить сценарий'}).click();
  await expect(workspace(page).getByRole('alert')).toContainText('Настройки несовместимы');
  await expect(workspace(page).getByLabel('Тема',{exact:true})).toHaveValue('reprioritize');
  expect((await draft(page)).validation?.status).toBe('invalid');
  await screenshot(page,'g5-invalid-resources-360');
  await workspace(page).getByLabel('Тема',{exact:true}).selectOption('urgent');await save(page);await validate(page);await preview(page);
  await page.setViewportSize({width:390,height:900});await screenshot(page,'g5-s2-preview-390');
  await publish(page);const savedDraft=await draft(page);
  await server!.stop();await server!.start();await page.reload();expect(await draft(page)).toEqual(savedDraft);
  await preview(page);await publish(page);await begin(page);
  await move(page,'question','Тема вопроса','priorities');await move(page,'question','Тема вопроса','resources');
  const active=await snap(page);expect(active.projection.scenario.opponent.roleId).toBe('team_lead');
  await server!.stop();await server!.start();await page.reload();expect(await snap(page)).toEqual(active);
  await move(page,'acknowledge','Какой факт вы признаёте?','report-deferrable');await move(page,'argument','На что вы хотите сослаться?','resource-argument');
  await offer(page,[['Объём (часов работы)','full'],['Срок (рабочих дней)','2'],['Помощник (6 часов ресурса)','1'],['Перенос отчёта (6 часов ресурса)','1']]);
  const r=await report(page);expect(r.outcome.playerUtility).toBe(47);expect(r.overall.score).toBe(100);
  await page.setViewportSize({width:1280,height:900});await screenshot(page,'g5-s2-report-1280','[data-testid="feedback"]');
  await server!.stop();await server!.start();await page.reload();expect(await report(page)).toEqual(r);
});

test('two real tabs: stale publication/save preserve input, restore is explicit, validation pending and duplicate IDs',async({page,context})=>{
  await open(page,390);await validate(page);await preview(page);await approve(page);
  const other=await context.newPage();await other.goto(server!.origin+'/admin');
  await expect(workspace(other).getByLabel('Сфера',{exact:true})).toHaveValue('supply');
  await workspace(other).getByLabel('Тон оппонента',{exact:true}).selectOption('friendly');await save(other);
  await workspace(page).getByRole('button',{name:'Опубликовать',exact:true}).click();
  await expect(workspace(page).getByRole('alert')).toContainText('другой вкладке');
  await workspace(page).getByLabel('Цели оппонента',{exact:true}).selectOption('margin');
  await workspace(page).getByRole('button',{name:'Сохранить черновик',exact:true}).click();
  await expect(workspace(page).getByRole('alert')).toContainText('другой вкладке');
  await expect(workspace(page).getByLabel('Цели оппонента',{exact:true})).toHaveValue('margin');
  await screenshot(page,'g5-stale-tab-390');
  page.once('dialog',dialog=>dialog.accept());
  await workspace(page).getByRole('button',{name:'Загрузить сохранённый черновик'}).click();
  await expect(workspace(page).getByLabel('Тон оппонента',{exact:true})).toHaveValue('friendly');
  await expect(workspace(page).getByRole('button',{name:'Предпросмотр',exact:true})).toHaveCount(0);
  let release=()=>{};const paused=new Promise<void>(resolve=>{release=resolve;});
  await page.route('**/api/admin/context-draft/validate',async route=>{await paused;await route.continue();});
  await workspace(page).getByRole('button',{name:'Подобрать и проверить сценарий'}).click();
  await expect(workspace(page).getByText('Проверяем условия и достижимость…')).toBeVisible();
  await expect(workspace(page).getByLabel('Тон оппонента',{exact:true})).toBeDisabled();
  release();await expect(workspace(page).getByText(/Сценарий проверен\./)).toBeVisible();
  await preview(page);await approve(page);
  await workspace(page).getByLabel('Сложность',{exact:true}).selectOption('beginner');
  await expect(workspace(page).getByText(/Предыдущая проверка и предпросмотр больше не действуют/)).toBeVisible();
  await expect(workspace(page).getByRole('button',{name:'Опубликовать',exact:true})).toHaveCount(0);
  await save(page);await validate(page);await preview(page);await publish(page);
  const d=await draft(page),payload={requestId:randomUUID(),expectedRevision:d.revision,settingsHash:d.settingsHash,candidateHash:d.validation!.candidateHash,approved:true};
  const a=await page.request.post(server!.origin+'/api/admin/context-draft/publish',{data:payload});
  const b=await page.request.post(server!.origin+'/api/admin/context-draft/publish',{data:payload});expect(a.status()).toBe(200);
  expect(ContextPublicationSchema.parse(await a.json())).toEqual(ContextPublicationSchema.parse(await b.json()));
  const conflict=await page.request.post(server!.origin+'/api/admin/context-draft/publish',{data:{...payload,candidateHash:'a'.repeat(64)}});expect(conflict.status()).toBe(409);
  await other.close();
});

for(const width of [360,390,1280])test('admin initial defaults and keyboard focus without horizontal overflow at '+width,async({page})=>{
  await open(page,width);
  for(const label of ['Сфера','Тема','Сложность','Тон оппонента','Роль оппонента','Цели оппонента'])await expect(workspace(page).getByLabel(label,{exact:true})).toBeVisible();
  await expect(workspace(page).getByRole('button',{name:'Сохранить черновик',exact:true})).toBeDisabled();
  await page.keyboard.press('Tab');
  for(let i=0;i<12;i++){
    if(await workspace(page).getByLabel('Сфера',{exact:true}).evaluate(e=>e===document.activeElement))break;
    await page.keyboard.press('Tab');
  }
  const sphere=workspace(page).getByLabel('Сфера',{exact:true});await expect(sphere).toBeFocused();
  expect(await sphere.evaluate(e=>getComputedStyle(e).outlineStyle)).not.toBe('none');
  await screenshot(page,'g5-initial-'+width);
  await page.goto(server!.origin+'/');await expect(page.getByText('Пока нет опубликованных ситуаций')).toBeVisible();
});
