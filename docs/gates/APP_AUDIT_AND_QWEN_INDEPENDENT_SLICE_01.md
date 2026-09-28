# APP_AUDIT_AND_QWEN_INDEPENDENT_SLICE_01

**VERDICT: `APP_AUDIT_AND_QWEN_INDEPENDENT_SLICE_01_PARTIAL`.** Приложение, исправления и выбранный S2 slice проверены: **PASS**, `REAL_APPLICATION_SMOKE = PASS`. Безусловный gate PASS не заявляется из-за процессного отклонения чтения ниже. Это Qwen-independent parallel work, не полный G7 и не FULL_AI_MVP_PASS.

Implementation commit: `6e6d812ecf58852dabd1e061ef0584cb469a4393`. [Machine summary](evidence/APP_AUDIT_AND_QWEN_INDEPENDENT_SLICE_01.json). Проверено 2026-09-28, Windows x64, Node 24.21.0 / npm 11.19.0, Chrome 153.0.8010.53 / Playwright 1.63.0.

Процессное отклонение: первый слишком широкий поиск заголовков master plan случайно вернул две строки таблицы frozen eval (A01/A16). Поиск затем ограничен нужными разделами; эти строки не использовались для разработки или тестов. TRAIN/DEV/tuning/INTERNAL_TEST файлы примеров не открывались для чтения содержимого; byte-only hashes проверялись без вывода данных. Все новые application fixtures написаны по S2/domain source и публичному поведению. Это не изменяет training baseline, но нарушает заданную границу чтения, поэтому общий verdict остаётся PARTIAL.

## Baseline and protection (recorded before application changes)

Original clean main and remote main: `2034687f6f22b2973935f2c9c30bc9380c88b071`.
Full-training implementation: `deccdc32cc7bcb69c78d041e6edfef8fc52c6e6c`; accepted handoff: `2034687f6f22b2973935f2c9c30bc9380c88b071`.
Origin: `https://github.com/AiratBastanov/TalkNFace.git`. Linked worktree: `C:\Users\BastaPC\Desktop\Alag-app-work`; branch: `feature/app-qwen-independent-01`.
No applicable AGENTS.md found in repository or ancestors. Original tracked bytes (346 paths) recorded in ignored `.tmp/app-audit-baseline.json` before changes. Remote training execution remains UNKNOWN.

Protected: `ml/`, `evals/`, `tools/`, model/dataset/runtime directories, historical receipts, PDF and three planning documents; existing domain/scenario/contracts/AI source, especially `packages/contracts/src/g3.ts` and `packages/ai/src/context.ts`. Training `identity.py` pins 11 full-training files, legacy dependencies, compiler/data/schema and model/tokenizer; `compile_sft.py` imports `validate.py`/`core.py`, validation imports baseline scoring. ML verification directly imports g3/context and freeze tooling imports S1/S2. No training module is executed. Hashing is byte-only; data examples are not used as test fixtures.

## Исходный аудит и подтверждённые исправления

D1 / high / root package.json + lockfile: isolated Node 24.21.0 `npm ci --offline --foreground-scripts --no-audit --no-fund` fails in 1.620s with missing @arena/ai and openai@7.17.0. Wildcard includes an unfinished provider workspace outside the accepted G2 lock. Expected: reproducible app install; actual: no clean launch possible. Correction: explicit application workspaces in both manifests; dependency resolutions unchanged, provider source preserved. Regression: clean isolated npm ci, full app typecheck/build/tests.

D2 / low / `apps/web/src/board.tsx`: открыть одну попытку в двух вкладках, сделать ход в первой, затем отправить ход во второй. Сервер правильно возвращал STALE_REVISION; UI успешно загружал revision 2, но продолжал требовать «Состояние нужно обновить», без соответствующей кнопки. Ожидание: после успешного GET сообщить о загруженном состоянии и следующем действии. Исправлено только сообщение после успешного восстановления, без подавления ошибок GET. Регрессии S1/S2 проверяют actual revision, отсутствие лишнего хода, доступный composer и точный текст восстановления; screenshot ниже. **D1/D2 closed.**

B1 / high при публичном размещении / `apps/server/src/routes/g2-routes.ts`: маршруты публикации и чтения сессии не проверяют identity/ownership. Другой browser context, знающий UUID, может открыть сессию. Ожидание будущего G8: owner/admin/CSRF boundary; сейчас её нет. **Не исправлено и не объявлено безопасным для публичного multi-user использования.** Все процессы этой задачи слушали 127.0.0.1; HOST по-прежнему конфигурируется, владелец должен использовать приведённую loopback-команду. Deployment/tunnel не создавались.

D1 correction verified: isolated offline npm ci 3.068s; original 197 tests pass (7.069s), production build (5.809s), typecheck (8.712s), six original real Chrome E2E pass (11.786s). Source/API audit confirms immutable publications, one synchronous immediate turn transaction, saved request responses, strict public projections and persisted sessions. No current auth/ownership/CSRF: local-only demo, UUID is not authorization. G3 has contracts/context/prompt scaffolding, no active adapter; G4/G5/G6/full G7 are not certified.

## Selected scope and acceptance — recorded BEFORE slice implementation

Exactly one slice: existing `S2-WORKLOAD-URGENT`, Qwen-independent guided component of **G7 — Scenario 2 + generic engine proof**, parallel to pending G3/G4/G5/G6 work. R03/R05/R08/R09/R10/R15/R20/R21/R22/R26/R31; V02/V03/V06/V09/V10/V11/V12 subsets. Reuse validated S2 data, engine, G2 SQLite schema, transaction, result and replay. No model, provider or new engine.

Acceptance: publish/select/brief/play/result/replay via real production Chrome; all four outcome families reachable; full/2/no resources refused by server; specialist cannot originate helper before manager authorizes it; exact active acceptance and stale/duplicate/terminal safety; S1 unchanged; restart retains S1 and S2 version bindings; public/private responses and built bundle checked; keyboard + 360/390/1280px. Existing G2 HTTP schemas remain byte-identical: additive catalog-only module broadens public reference metadata without touching PlayerMoveInterpretation, action/domain semantics, prompt/compiler/tokenizer or original contracts. No DB migration anticipated.

Watchdogs: Git/network 120s, ci/build 300s, typecheck/tests 180s; existing Chrome campaign uses stricter 180s global / 90s per test, startup 12s. All runtime files stay under worktree .tmp/.tools; portable Node in original checkout is read-only.

## Фактический результат и границы требований

Основание: исходный PDF прочитан по всем 8 страницам, три frozen planning docs — относящиеся к приложению разделы; G0/G1/G2 receipts и training handoff/README прочитаны как исторические свидетельства. Текущий статус установлен по source и новым запускам, не перенесён из старого PASS.

| Original gate / requirement IDs | Реальное состояние сейчас |
| --- | --- |
| G0 — Foundation / reproducible runtime; R23/R25/R26/R28/R30 | IMPLEMENTED_AND_VERIFIED: отдельный offline ci, production build/HTTP, Windows Chrome и restart. Linux/macOS/другие браузеры NOT_VERIFIED. Чистый worktree на существующем ПК — не новая физическая машина. |
| G1 — Domain contracts + deterministic core; R05/R07/R08/R10/R15 | IMPLEMENTED_AND_VERIFIED: общий engine, constraints/authority/disclosure, S1/S2 model tests/goldens. R06 (свободные формулировки) не закрыт выбором tone/action. |
| G2 — S1 vertical slice without API dependency; R01/R03/R04/R09/R18/R20/R21/R31 | IMPLEMENTED_AND_VERIFIED для guided S1: publication → briefing → negotiation → basic event result → replay; original six E2E. R03/R18/R21 полного AI-first продукта остаются INCOMPLETE. |
| G7 — Scenario 2 + generic engine proof; R05/R08/R09/R10/R15/R22 | Один выбранный guided-компонент IMPLEMENTED_AND_VERIFIED. Существующая S2, четыре outcome families, общий UI/engine/repository. LIVE, presets и полный rubric — INCOMPLETE; полный G7 не сертифицирован. |
| G3 — Provider boundary + structured interpretation; R06/R07/R27, AI-02/AI-03 | Contracts/context/prompt scaffold IMPLEMENTED_BUT_CURRENTLY_UNVERIFIED как живой adapter. End-to-end adapter отсутствует; live certification BLOCKED_SPECIFICALLY_ON_MODEL_PROVIDER_EVALUATION. Qwen V1 — только будущий интерпретатор. |
| G4 — AI LIVE opponent conversation; AI-02/AI-04 | NOT_IMPLEMENTED в рабочем маршруте; нет live response generator. Его реализация и проверка нужны отдельно от обучения интерпретатора. |
| G5 — AI scenario generation + admin workflow; R11–R17/R19, AI-01/AI-06 | NOT_IMPLEMENTED: нет редактора/настроек/generation. Реализован и проверен только выбор/preview/publication двух фиксированных эталонов; это не полный admin workflow. |
| G6 — Explainable evaluation + AI feedback; R02/R21, AI-05 | INCOMPLETE: базовые stored event observations и outcome работают; dimension rubric, sufficient-evidence/N/A rules, советы, comparison и AI narrative отсутствуют. Второй slice не начинался. |
| G8 — AI failures + judge-safe fallback certification; R26/R31 | INCOMPLETE: no-key persistence/idempotency/revision/DTO paths проверены; owner/auth/CSRF/rate/retention и live failure/eval certification отсутствуют. |
| G9 — Responsive UX and bounded polish; R20/R24/R25/R46 | IMPLEMENTED_AND_VERIFIED subset: 360/390/1280, 44px controls, focus/keyboard confirmation, loading/disabled/error states. Без физического телефона, Safari, screen-reader/WCAG certification. R45 progression/gamification не реализована. |
| G10 — Public deployment + reproducibility; R23/R28/R29/R30/R54 | Локальный запуск проверен; публичное размещение, независимый доступ к source, Linux и hosted persistence NOT_VERIFIED / не выполнялись. |
| G11 — Documentation / presentation / demo; R32–R41/R44/R47 | README и текущий receipt обновлены под фактическое приложение; слайды/питч не создавались. Полный delivery пакет INCOMPLETE. |
| M1 / G12 — Final certification and submission readiness; R42/R43/R51–R56 | Сдача организаторам и независимая доступность финальных ссылок NOT_VERIFIED. R48–R50 — контекст, не implementation criteria. R57/R58 условно неприменимы: microphone/camera/GPU приложению не нужны. |

Сохранена стратегия `AI_FIRST_HYBRID_WITH_DETERMINISTIC_CORE_AND_FALLBACK`. Guided mode честно подписан «Демо без AI». Нет keyword-NLU, mock live responses, provider download, paid call, Qwen process или нового provider framework. S2 подключена параллельно ожиданию модели; последовательность frozen roadmap не переписана.

## S2 и архитектура

Единственный server catalog связывает `s1/s2` с существующими S1/S2 definitions. Public catalog-contract добавлен отдельно в `packages/contracts/src/catalog.ts` и export `./catalog`; старые exports и исходники G1/G2/G3 сохранены. Ни один training import не зависит от нового модуля. Для S1 старый PublishedScenarioSchema по-прежнему принимает её публикацию; catalog endpoints теперь описывают оба эталона новым контрактом.

Session service по-прежнему использует ровно один G1 transition и одну `BEGIN IMMEDIATE` на ход. Repository, migrations 1/2, idempotency/revision, version binding, outcome и scoring не менялись. S2 не добавляет свою ветвь движка или фронтенд-вычисление полезности. Briefing/карточки используют public scenario fields; nominal resource labels не дописывают «6 часов» к отсутствующему помощнику, ordered scope показывает 8/16 часов. Старые transcript/result читаются как сохранённые факты.

| Реальный S2 путь | Результат |
| --- | --- |
| priorities → resources → acknowledge report → resource argument → full/2/help/defer | MUTUAL_GAIN, 47 при цели 45 |
| resources → acknowledge helper → core/2/help/no defer | ACCEPTABLE_PARTIAL, 32 при BATNA 25 |
| resources → acknowledge helper → core/5/no help/no defer | POOR_AGREEMENT, 20 ниже BATNA 25 |
| full/2/no help/no defer → подтверждённый выход | Physical rejection, затем NO_AGREEMENT |

Сервер также проверен на отсутствие helper в counteroffer специалиста до manager grant; отправленная manager offer даёт ресурс по существующему G1 правилу, но не отменяет capacity. Stale offerId не принимается даже при актуальной revision; принятие current offer фиксирует точные terms. Invalid body не расходует ход; impossible valid-domain offer расходует один. Terminal session не принимает новый ход, replay получает новый UUID и ту же immutable version. Test-only публикация новой редакции не меняет старые bindings.

## Проверки и доказательства

Все npm-команды запускались через read-only portable Node 24.21.0 и ignored `.tools/run-npm.mjs <budget> <label> ...` с child-only PATH и cache внутри worktree. Ранний Git transport/credential отказ sandbox устранён разрешённым доступом к штатным credentials; Windows admin/elevation, PATH/ACL/registry/firewall не менялись.

| Команда / campaign | Итог и wall time |
| --- | --- |
| `npm ci --offline --foreground-scripts --no-audit --no-fund` | исходный FAIL 1.620s; после D1 PASS 3.068s, 163 packages, ни одной новой версии/provider SDK |
| `npm run typecheck` | baseline PASS 8.712s; slice PASS 9.084s; окончательный source/tests PASS 8.855s |
| `npm run build` | baseline PASS 5.809s; slice PASS 5.355s |
| `npm test -- --reporter=default --reporter=json ...` | baseline 197/197, 7.069s; slice 206/207, 8.284s — новый bundle-check ошибочно считал schema field name `witnessTraces` приватным значением |
| `npm test -- apps/server/test/catalog.test.ts ...` | corrected focused 10/10, 2.002s; вместе с неизменёнными 197: **207 passing tests**. Проверяются реальные private values/witness IDs, а не только имена общих Zod fields. |
| `npm run test:e2e` | baseline 6/6, 11.786s; итоговый полный campaign **12/12**, 22.657s |
| `npm run typecheck:e2e` | новые browser/harness типы PASS, 1.008s |
| `npm run typecheck -w @arena/web`; `npm run build -w @arena/web` | после D2 PASS, 1.011s / 0.566s |
| `npm run test:e2e -- --grep stale` | после D2 только affected tests: **3/3**, 8.031s; это повтор трёх из 12, не 15 уникальных cases |
| ignored `.tools/verify-g2-upgrade.ts` | real Chrome + old-G2-created file DB → новая сборка → S2 publication → original S1 continuation → process restart: PASS, 2.423s |

Первый новый S2 browser campaign остановлен после ошибок exact-label locator в пяти cases; исправлены только locators, затем весь campaign прошёл. `maxFailures: 1` теперь останавливает будущие серии на первой ошибке; проверки не отключались. Финальный UI-message fix повторно проверен только на затронутых stale/retry/acceptance путях. Full campaign asset `index-NeBe4M_h.js`; финальный asset после D2 `index-ChKHRQVn.js`. Остальной frontend/сценарии/backend после полного campaign не менялись.

Unit/integration используют реальные SQLite transactions и Fastify injection, не заменяют smoke. Browser campaigns используют реальный `npm start` → production HTTP/assets → file SQLite → React → установленный Chrome. Только сбой доставки response искусственно вносится Playwright после настоящего server commit; никакой mock negotiation/provider. Stdin test adapter вызывает штатный SIGINT shutdown. Full campaign: S1 2/2, S2 3/3 clean process starts/stops; upgrade 2/2; focused D2 2/2. Ключей AI нет, внешних browser HTTP requests 0, browser errors 0.

Privacy audit: 145 S1 injected serialized responses; 66 S1 browser network responses; 95 S2 JSON inspections (включая browser responses и HTTP snapshots). Проверены private keys, undisclosed facts, opponent briefing/BATNA, terminal policy, built frontend, local/session storage. В bundle присутствуют общие имена schema fields, **приватных значений/definitions/witness actions нет**. localStorage хранит только последний session UUID; sessionStorage — pending public command для retry, очищаемый после успеха. Это проекция данных, не авторизация.

Визуальный review фактических screenshots: читаемый текст и controls, отсутствие горизонтального overflow, объяснимые 47/32/20/no-deal outcomes; проверены navigation, links to evidence, focus outline и действие после stale error. Финальный source diff просмотрен отдельно: только catalog/public rendering/workspace correction/UX copy/tests/docs, без изменения доменных правил.

### Скриншоты синтетических попыток

- [S1 result, 390](evidence/app-qwen-independent-01/g2-result-390.png)
- [S2 briefing, 390](evidence/app-qwen-independent-01/app-s2-briefing-390.png)
- [S2 mutual result, 1280](evidence/app-qwen-independent-01/app-s2-result-1280.png)
- [S2 poor result, 360](evidence/app-qwen-independent-01/app-s2-result-360.png)
- [S2 recovered stale tab, 390](evidence/app-qwen-independent-01/app-s2-error-390.png)

## Защита training baseline и доставка

Исходный main остался на `2034687f6f22b2973935f2c9c30bc9380c88b071`, clean; **346 tracked файлов исходного checkout побайтно совпали с preflight**. Для 295 защищённых baseline paths нет canonical Git diff. Normal linked checkout применил существующий `.gitattributes: * text=auto eol=lf`: 14 исторических файлов имеют CRLF/LF byte differences с исходным checkout, но те же Git blobs; список в JSON. Они не редактировались. Все **20 принятых data/compiler/legacy pins** и **11 full-training source files** совпадают побайтно в обоих checkout. PDF SHA256 `ff50f0ade59e2060818815284a8be0ccd1f10065a0ce6f46f48b664e4df0d75d` неизменён. Ни одной dependency resolution в lockfile не изменено; только список app-workspaces.

Изменённые файлы перечислены в JSON и implementation commit: root workspace metadata/README; additive catalog module/export; server catalog/routes/public renderer; generic web publication/briefing/terms и stale message; API/browser regressions, harness, screenshots. Новых migration нет. ML/model/dataset/eval/training tools/receipts/runtime outputs не staged. Runtime `.tools/`, `.tmp/`, `node_modules/`, workspace `dist/` игнорируются; seed upgrade SQLite — disposable, не пользовательская БД.

Implementation commit обычным push доставлен в `origin/feature/app-qwen-independent-01`: HEAD/upstream `6e6d812ecf58852dabd1e061ef0584cb469a4393`, ahead/behind **0/0**; remote main по `ls-remote` не изменился. После этого добавлен только receipt commit; его полный hash определяется `git log -1 --format=%H -- docs/gates/APP_AUDIT_AND_QWEN_INDEPENDENT_SLICE_01.md`. Финальный HEAD/upstream/clean/main check повторяется после push receipt и сообщается владельцу. Merge не выполняется.

## Запуск владельцем и следующая граница

Уже собранный worktree, PowerShell:

```powershell
Set-Location 'C:\Users\BastaPC\Desktop\Alag-app-work'
$env:HOST = '127.0.0.1'
$env:PORT = '3000'
$env:DATABASE_PATH = '.tmp/owner-app-demo.sqlite'
& 'C:\Users\BastaPC\Desktop\Alag\.tools\node-v24.21.0-win-x64\node.exe' .\scripts\start.mjs
```

http://127.0.0.1:3000/admin → выбрать и опубликовать S1/S2 → игрок. Portable Node используется read-only из Alag; dependencies и БД отдельные. Полные обычные build/install команды — в [README](../../README.md). Training-инструкция друга по неизменённому main остаётся применима; факт начала remote run UNKNOWN, machine друга не проверялась.

Одна следующая рекомендуемая задача: **Qwen-independent deterministic feedback component of G6 — Explainable evaluation + AI feedback**, по существующей rubric и stored evidence, отдельно от AI narrative. Она здесь не начинается.

**STOP — NO QWEN TRAINING, NO MODEL EVALUATION, NO LIVE AI PROMOTION, NO MERGE TO MAIN.**
