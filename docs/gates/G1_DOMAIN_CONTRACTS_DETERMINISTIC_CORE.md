# Verdict

**G1_DOMAIN_CONTRACTS_DETERMINISTIC_CORE_PASS**

Проверено 2026-09-16 в `C:\Users\BastaPC\Desktop\Alag`, Windows x64, project-local **Node 24.21.0 / npm 11.19.0**. Выполнен только G1. **171 tests passed / 0 failed**; GS1–GS7 **7/7**, GT1–GT6 **6/6**, W1/A1 **PASS**, четыре семейства исходов в каждом reference.

**TARGET_LINUX_RUNTIME_SMOKE = NOT_VERIFIED.** Это перенесённая предпосылка G0; G1 не означает полной сертификации V12.

# Scope executed

Реализованы runtime domain contracts, ScenarioDefinition v1, отдельная semantic validation, конечный каталог пакетов, generic utility/constraints/authority, pure reducer, disclosure, social state, anti-farming, aspiration, жизненный цикл оферт, детерминированный counteroffer, domain outcome и evidence, строгая player projection. S1/S2 — декларативные reference definitions с проверенными witnesses; golden fixtures и полный audit 54/16 пакетов.

Изменены только внутренние packages, необходимая workspace-сборка/test discovery, lockfile, статус README и материалы G1. Артефакты:

- [Полный расчёт моделей и пошаговые machine-readable traces](evidence/G1_MODEL_AUDIT.json).
- [Verification: hashes, scope, команды, tests, smoke](evidence/G1_VERIFICATION.json).
- [Машиночитаемые golden fixtures](../../packages/scenarios/test/goldens.ts).
- [Генератор audit](../../packages/scenarios/test/generate-audit.ts).

Таблицы ниже сформированы из результатов **реального общего engine** в G1_MODEL_AUDIT.json. Fixtures не выдаются за готовый игровой прототип.

# Previous gate dependency

Предыдущий verdict: **G0_FOUNDATION_REPRODUCIBLE_RUNTIME_PASS_WITH_LINUX_PREREQUISITE** ([receipt](G0_FOUNDATION_REPRODUCIBLE_RUNTIME.md)). G0 Windows foundation подтверждён; Linux остаётся NOT_VERIFIED. Новых native dependencies или платформенных механизмов в G1 нет.

Перед изменением кода полностью прочитаны 00/01/02 и G0 receipt, просмотрены текущие source/config/runtime files, прочитан исходный PDF. Зафиксирован baseline в `.tools/g1-preflight.json`; точный project runtime проверен как v24.21.0. Системный Node не использовался для команд проекта.

Pre/post SHA-256:

| Защищённый файл | SHA-256 до G1 | После G1 |
|---|---|---|
| 9. ОЭЗ ППТ Алабуга.pdf | `FF50F0ADE59E2060818815284A8BE0CCD1F10065A0CE6F46F48B664E4DF0D75D` | MATCH |
| docs/00_REQUIREMENTS_AND_SCORING_MATRIX.md | `DD380424D50900C4BB3B6550DC69654226BC89ECA45E8FFFFF9AC1435BF27460` | MATCH |
| docs/01_PRODUCT_AND_ARCHITECTURE_DECISION.md | `F3535762A93BE4FCA1322F8F8AB5AFC1BC980F3918EF4D5F9F55C1D03F25725D` | MATCH |
| docs/02_MASTER_IMPLEMENTATION_PLAN.md | `D514CC920AC66749EAEDE4E443F589A1DFAA26C5F6AFB8F9D7498AF595B20E57` | MATCH |
| docs/gates/G0_FOUNDATION_REPRODUCIBLE_RUNTIME.md | `3D27D5D022FD8ECA384BC0510E493D836B4BB17A2F621A37EC55542DE8824B67` | MATCH |

Lockfile до G1: `785ACC78667D7E740865963BF1CAB5B02C89DA441841FA352F7868A4C2C0FDED`.
Lockfile после G1: `7CE5CC85C537D687D21F84F72D44BFEDCD38ADCEB5E751496014EAE18189588C`.

Точная проверка lock diff: из нового JSON удалены только четыре записи workspace links/packages для domain/scenarios и direct dependency `contracts → zod@4.6.5`. Сериализованный результат **побитово восстанавливает SHA-256 исходного lockfile**. Новых или изменённых внешних пакетов нет.

Три fingerprints системных Node22/npm совпадают с G0. Permanent PATH, registry, WSL, Docker, Visual Studio, Python, firewall и services не менялись. Git metadata отсутствовали; Git не инициализировался.

# Files created / modified

Главные группы: `packages/contracts`, `packages/domain`, `packages/scenarios`; root `package.json`, `package-lock.json`, `vitest.config.ts`, `README.md`. Старый `packages/contracts/src/index.d.ts` заменён на runtime `index.ts`, сохраняющий HealthResponse/ReadinessResponse.

Проверенный список source/config/model files:

- `README.md`
- `docs/gates/evidence/G1_MODEL_AUDIT.json`
- `package-lock.json`
- `package.json`
- `packages/contracts/package.json`
- `packages/contracts/src/action.ts`
- `packages/contracts/src/common.ts`
- `packages/contracts/src/event.ts`
- `packages/contracts/src/index.ts`
- `packages/contracts/src/outcome.ts`
- `packages/contracts/src/projection.ts`
- `packages/contracts/src/scenario.ts`
- `packages/contracts/src/session.ts`
- `packages/contracts/test/schemas.test.ts`
- `packages/contracts/tsconfig.json`
- `packages/domain/package.json`
- `packages/domain/src/action-validation.ts`
- `packages/domain/src/authority.ts`
- `packages/domain/src/constraints.ts`
- `packages/domain/src/disclosure.ts`
- `packages/domain/src/enumerate.ts`
- `packages/domain/src/index.ts`
- `packages/domain/src/offers.ts`
- `packages/domain/src/outcomes.ts`
- `packages/domain/src/policy.ts`
- `packages/domain/src/projection.ts`
- `packages/domain/src/reducer.ts`
- `packages/domain/src/utility.ts`
- `packages/domain/src/validation.ts`
- `packages/domain/test/offers.test.ts`
- `packages/domain/test/policy.test.ts`
- `packages/domain/test/projection.test.ts`
- `packages/domain/test/validation.test.ts`
- `packages/domain/tsconfig.build.json`
- `packages/domain/tsconfig.json`
- `packages/scenarios/package.json`
- `packages/scenarios/src/index.ts`
- `packages/scenarios/src/reference-actions.ts`
- `packages/scenarios/src/s1-supply-launch.ts`
- `packages/scenarios/src/s2-workload-urgent.ts`
- `packages/scenarios/test/generate-audit.ts`
- `packages/scenarios/test/goldens.test.ts`
- `packages/scenarios/test/goldens.ts`
- `packages/scenarios/test/helpers.ts`
- `packages/scenarios/test/models.test.ts`
- `packages/scenarios/tsconfig.build.json`
- `packages/scenarios/tsconfig.json`
- `vitest.config.ts`
- `docs/gates/G1_DOMAIN_CONTRACTS_DETERMINISTIC_CORE.md` — этот receipt.
- `docs/gates/evidence/G1_VERIFICATION.json` — проверка артефактов; собственный hash не включается рекурсивно.

Ignored gate evidence: `.tools/g1-preflight.json`, `.tools/g1-final-audit.mjs`, `.tools/g1-tests*.json`, `.tools/logs/g1-*`; generated package `dist/` и npm workspace links. Все `apps/**` и исходные `scripts/**` сохранены по baseline hashes.

# Contract inventory

| Контракт | Boundary |
|---|---|
| ScenarioDefinitionSchema | Строгая сериализуемая версия мира; без функций/expressions |
| CanonicalActionSchema / CommandSchema | Discriminated union; expectedRevision, requestId, tone, compound fact/argument bindings, evidence refs |
| NegotiationStateSchema | Только deterministic session/domain state, pinned versions, offers, events |
| OfferSchema / EventPayloadSchema / DomainEventSchema | Stable IDs, turn/sequence, typed consequences и причины |
| OutcomeSchema | Отдельные terminal reason и family; private utility/BATNA comparisons |
| PublicScenarioSchema / PublicProjectionSchema | Новый allowlisted объект для игрока |
| DomainErrorSchema / EvidenceRefSchema | Stable code/path/ref/message; сохранение source ID и UTF-16 span |

Объекты используют `z.strictObject`; лишние поля отклоняются. Numeric data — finite safe integers. Сериализованные контракты не содержат Date/Map/Set/BigInt. Все перечисленные основные runtime schemas экспортируются через `z.toJSONSchema` в тесте; experimental `z.fromJSONSchema` не используется.

Evidence spans на G1 сохраняются и проверяются по границам start/end. Проверка по реальному исходному тексту и NLU принадлежат будущему G3. requestId переносится в events; exactly-once registry/commit **не реализован и не заявляется**.

# ScenarioDefinition v1

Ровно player/opponent; 1–3 goals/interests на сторону; own/private brief, target, BATNA/reservation; 2–4 issues по 2–6 unique values; максимум 1296 пакетов; 2–6 hidden facts; public topics/argument bindings; up to two pair tables **на сторону**; maxTurns=8 и фиксированная training policy version.

Schema validation отделена от semantics. Semantic validator проверяет namespaces/references, полное unary/pair/constraint coverage, authority values, disclosure triggers, interest/package bindings, BATNA=reservation, target≥reservation, итоговую utility −100…200 и размах по physical feasible packages 20…100. Проверяет наличие минимум двух individually rational пакетов и достижимость player target. Ошибки детерминированы и ограничены 128 entries; player получает только SCENARIO_UNAVAILABLE без private diagnostics.

Опциональные witnesses проверяются тем же reducer; при наличии нужны минимум два разных пути и хотя бы один target-reaching result. В обоих references присутствуют два исполняемых witnesses. Полный AI authoring/compiler/admin workflow не входит в G1.

# Reducer/state model

Чистые `createInitialState` / `transition`: scenario/state/action не мутируются; IDs и version IDs передаются вызывающим кодом. Нет clock, random, database или внешних сервисов.

Последовательность: strict command/revision/phase → pre-state fact/argument bindings → social effect → turn/revision increment → primary-topic disclosure → максимум один unique credit → resource authorization → package aspiration и offer decision → deterministic counteroffer → terminal precedence → events и allowlisted projection.

Фазы: briefing, exploring, bargaining; terminal agreed, player_walkaway, opponent_walkaway, round_limit. awaiting_confirmation отсутствует в authoritative state machine.

Malformed, out-of-domain, stale revision/offerId, unknown/unavailable bindings и terminal command сохраняют тот же state без хода. Полный valid-domain, но physically impossible offer расходует ход и получает rejection evidence. Warning + damaging move завершает разговор до новой package evaluation/offer/resource commitment.

# Utility engine

`evaluateUtility` использует base + полные unary lookups + pair interactions из данных. Все 70 reference packages независимо сверены с формулами 01, включая infeasible варианты. Missing cells — semantic validation errors; permissive fallback к нулю отсутствует.

Границы −100…200 относятся к **итоговой** simulation utility. Вклады ограничены отдельным целочисленным диапазоном: например, вклад цены −115 корректен, а итог Ub остаётся на шкале. Это не изменение формулы S1.

S1: base/unary data. S2: manager scope×deadline и employee scope×help pair tables; прочие contributions — unary. Нет сценарных условий в evaluator.

# Constraint engine

Поддерживаются ровно `allowed_values`, `forbid_combination`, `linear_lte`. Результат — feasible и structured violations с ruleId/reasonCode/explanationFactId. Prose engine не генерирует.

S1 launch: allowed DELIVERY = all7 или split40at7_rest14. S2 capacity: work − dayCapacity − helpCapacity − deferCapacity ≤0 из lookup contributions. Generic forbid_combination отдельно проверен. Ни trust, ни argument не отменяют constraint.

# Authority model

Authority отделена от physics и aspiration. Проверяются allowed values и generic resource-authorization rules. S1 director разрешает P≥90; контрольный account-manager variant — P≥100. P95/split/A50 остаётся physically possible, но получает PRICE_AUTHORITY_FLOOR.

S2 specialist может **принять** HELP1 в отправленном предложении руководителя, но не инициировать его в counteroffer до authorization. Team lead отличается значением generic permission flag. Resource grants сохраняются в state/events; проверка capacity от роли не меняется.

# Disclosure model

Threshold beginner/normal/advanced = 35/45/55 по trust **после** social effect. За ход работает только primary topic; secondary topic не раскрывает факт и не награждается отдельно. Grounding/acknowledgement используют только знание **до** хода.

Physical/authority explanations раскрываются по запросу/нарушению без trust lock. `opponent_commitment_contains` разрешён для фактов доступности ресурсов: counteroffer/accept с HELP1 или DEFER_REPORT1 раскрывает соответствующий S2 факт, без question-credit. Повторный вопрос не даёт discovery заново. S1 предоплата не раскрывает cashflow автоматически. Подтверждены корректные fact/interest/predicate references и запрет раскрывать мотивацию через resource trigger.

# Social/aspiration policy

Это **авторская учебная deterministic policy**, не психологическая шкала.

- Initial neutral/friendly/skeptical: 50/20, 60/10, 40/30.
- Новый primary-topic question: trust +4 один раз; точный known-fact acknowledgement: +6 и tension −4 (skeptical −2), один раз.
- Grounded argument: trust +4 один раз; positive compound delta ≤6.
- Accusation: −8/+10; threat: −15/+20; установленное contradiction: −10/0. Выбирается один наиболее сильный отрицательный эффект.
- Damaging turn исключает положительный social/repair effect, новый credit и новый argument discount. Прежние применимые аргументы остаются.
- Clip 0…100; tension≥80 предупреждает; следующий damaging move даёт opponent_walkaway. Только доступный, ещё не использованный exact constraint acknowledgement ремонтирует warning; пустая clarification и повторный ack не помогают.
- Credits ≤5 и ≤1/turn: discovery, constraint acknowledgement, grounded opponent-interest argument, первый feasible/authority-valid offer, новый reciprocal conditional exchange.
- Event identities устойчивы. Учтены повтор topic/fact/claim, одинаковая оферта и цикл через промежуточную оферту. Первая feasible оферта — одноразовая возможность, включая damaging turn; повтор не восстанавливает suppressed credit. Compound one-time opportunities записываются даже при срабатывании per-turn cap.

`aspiration(p) = max(R, R + premium − 2*c − argumentDiscount(p) − floor(max(trust−50,0)/10))`.

Premium = 8/15/20. Discount = 2 за применимый grounded interest binding, максимум 4; считается заново для **каждого** пакета. Удаление split/предоплаты/ресурса снимает только соответствующую экономическую применимость. Время и номер хода не снижают aspiration. Reference starting aspirations получены формулой: S1=35, S2=40.

# Offer lifecycle

Полная оферта содержит ровно один value на issue. Normalization идёт по scenario issue order; logical equality/canonical key не зависят от insertion order входного объекта/terms. Вне домена нет округления.

Отдельны shape/domain, physics, authority и strategic acceptance. Active opponent offer переживает вопросы. Замена создаёт новый stable ID, supersedesId и offer_closed; agreement/terminal закрывает активную оферту. Accept требует точного ID. Исполняется уже выданное допустимое обязательство; **текущая aspiration не перепроверяется**.

Отдельный тест проходит реальный friendly trace: counteroffer90/split/A50, затем threat поднимает aspiration выше utility этого counteroffer, точный accept на ходе8 всё равно исполняется. round_limit не перезаписывает agreement или explicit walkaway.

# Counteroffer policy

Каталог: scenario issue order × issue value order, explicit zero-based index. Candidates проходят physical constraints, opponent proposal authority и Uopponent≥aspiration(candidate). Player BATNA/utility не участвуют в выборе.

Distance: число шагов ordered values; 0/1 для nominal/boolean. Минимальная distance → максимальная opponent utility → минимальный catalog index. Нет random/locale/database ordering. Отсутствие кандидата даёт NO_ACCEPTABLE_CANDIDATE, не новый придуманный term.

На каждом reference package проверена минимальность/validity/repeatability при 18 комбинациях difficulty/trust/credit и применимых arguments/resources. GT5 отдельно фиксирует равный distance/utility: core/2/HELP1/DEFER1 выигрывает по index перед core/5/HELP1/DEFER0.

# Outcome classification

- **MUTUAL_GAIN:** agreement, player≥target и обе стороны≥BATNA/reservation.
- **ACCEPTABLE_PARTIAL:** agreement, player≥BATNA, но ниже target.
- **POOR_AGREEMENT:** допустимое соглашение с player<BATNA; engine не запрещает учебную ошибку.
- **NO_AGREEMENT:** player_walkaway, opponent_walkaway или round_limit.

Terminal reason хранится отдельно. Проверены все четыре семейства **для каждого** reference. Outcome helper отклоняет impossible/authority-invalid agreement и utility оппонента ниже reservation. Full feedback/rubric/narrative отсутствуют.

# Public/private projection boundary

`projectPlayer` создаёт новый объект по allowlist: public brief/issues/topics, собственная роль/цели/BATNA/reservation, публичная роль/initial position оппонента, known facts, доступные обоснования, offers, observable stance, phase/turns и собственный итог.

Не сериализуются opponent utility/reservation/BATNA, undisclosed facts/interests, witnesses, trust/tension numbers, earned keys, internal events или ненужные version/config metadata. Даже terminal DTO не выдаёт private opponent metrics. `projectPrivateState` предназначен только для доверенного server/evidence контекста.

Тесты проверяют сериализованный JSON, private numeric/text sentinels, unknown attached fields, selective disclosure и отсутствие shared mutable nested objects. Frontend не импортирует domain/scenarios; исходник и build shell G0 сохранены.

# S1 model audit

Общие counts непосредственно из engine. Authority-valid ниже означает physically feasible и absolute authority-valid; proposal resource permissions учитываются отдельно в runtime.

| Model | Raw | Physical feasible | Authority-valid feasible | Individually rational | Player target + rational | Poor agreement representable |
|---|---:|---:|---:|---:|---:|---:|
| S1-SUPPLY-LAUNCH | 54 | 36 | 36 | 7 | 3 | 8 |
| S2-WORKLOAD-URGENT | 16 | 11 | 11 | 6 | 1 | 5 |

S1: P / DELIVERY / PREPAY. Utility Ub/Us:

| Catalog index | Все individually rational пакеты | Ub | Us |
|---:|---|---:|---:|
| 5 | 90 / split40at7_rest14 / 50 | 69 | 22 |
| 14 | 95 / split40at7_rest14 / 50 | 64 | 27 |
| 22 | 100 / split40at7_rest14 / 30 | 62 | 20 |
| 23 | 100 / split40at7_rest14 / 50 | 59 | 32 |
| 29 | 105 / all7 / 50 | 59 | 21 |
| 31 | 105 / split40at7_rest14 / 30 | 57 | 25 |
| 39 | 110 / split40at7_rest14 / 0 | 55 | 22 |

Default rational Pareto frontier:

| Catalog index | Пакет | Ub | Us |
|---:|---|---:|---:|
| 5 | 90 / split40at7_rest14 / 50 | 69 | 22 |
| 14 | 95 / split40at7_rest14 / 50 | 64 | 27 |
| 23 | 100 / split40at7_rest14 / 50 | 59 | 32 |

Все пять обязательных арифметических примеров из запроса проверены, включая 90/all7/0 → 80/−14. Frontier совпал с 01.

Примеры из реальных переходов: GS1/GS7 mutual gain; GS2 partial; GS4/GS5 poor; GS3 opponent walkaway; GS6 round_limit. Physical rejection:95/all14/50 → LAUNCH_MINIMUM_40_PERCENT. Account-manager P95 → PRICE_AUTHORITY_FLOOR. Первый O90/all7/0: Us−14 < aspiration33 после первого offer credit → aspiration rejection.

# S2 model audit

S2: SCOPE / DEADLINE / HELP / DEFER_REPORT. Полные 16 строк, feasibility и utilities — в JSON audit; counts приведены выше.

| Catalog index | Все individually rational пакеты | Um | Ue |
|---:|---|---:|---:|
| 1 | core / 2 / 0 / 1 | 30 | 34 |
| 2 | core / 2 / 1 / 0 | 32 | 36 |
| 11 | full / 2 / 1 / 1 | 47 | 30 |
| 13 | full / 5 / 0 / 1 | 35 | 28 |
| 14 | full / 5 / 1 / 0 | 37 | 30 |
| 15 | full / 5 / 1 / 1 | 27 | 40 |

Rational Pareto frontier:

| Catalog index | Пакет | Um | Ue |
|---:|---|---:|---:|
| 2 | core / 2 / 1 / 0 | 32 | 36 |
| 11 | full / 2 / 1 / 1 | 47 | 30 |
| 15 | full / 5 / 1 / 1 | 27 | 40 |

Обязательные проверки: full/2/1/1 → capacity16, Um47/Ue30; core/2/1/0 → capacity10, 32/36; full/5/0/1 →35/28; full/2/0/0 → work16>capacity4; core/5/0/0 →20/34. Формулы сверены независимо для **всех 16** пакетов.

GT1/GT3 mutual gain; GT2/GT5 partial; GT6 poor; GT4 explicit walkaway. Physical rejection → WORK_EXCEEDS_CAPACITY. Specialist HELP1 proposal без grant → HELP_REQUIRES_MANAGER_RESOURCE. Первая core/2/1/0: Ue36 < aspiration38 после первого offer credit; counteroffer core/2/1/1 имеет Ue46.

# Golden traces

Generated final values; T/tension/c — private audit, не player UI. Для no-deal без agreement package, d/aspiration при наличии последней собственной оферты показаны именно для неё.

| Trace | Turns | T/tension | c | d | Aspiration | Agreement package | Player / opponent utility | Family / terminal reason |
|---|---:|---:|---:|---:|---:|---|---|---|
| GS1 | 5 | 68/16 | 5 | 2 | 22 | 95 / split40at7_rest14 / 50 | 64 / 27 | MUTUAL_GAIN / agreed |
| GS2 | 7 | 78/12 | 5 | 2 | 21 | 105 / all7 / 50 | 59 / 21 | ACCEPTABLE_PARTIAL / agreed |
| GS3 | 5 | 0/100 | 1 | 0 | 33 | — | — | NO_AGREEMENT / opponent_walkaway |
| GS4 | 5 | 68/16 | 5 | 0 | 24 | 110 / all7 / 50 | 54 / 26 | POOR_AGREEMENT / agreed |
| GS5 | 2 | 54/20 | 2 | 0 | 31 | 115 / all7 / 50 | 49 / 31 | POOR_AGREEMENT / agreed |
| GS6 | 8 | 54/20 | 2 | 0 | 31 | — | — | NO_AGREEMENT / round_limit |
| GS7 | 5 | 68/16 | 5 | 2 | 22 | 90 / split40at7_rest14 / 50 | 69 / 22 | MUTUAL_GAIN / agreed |
| GT1 | 5 | 68/16 | 5 | 2 | 27 | full / 2 / 1 / 1 | 47 / 30 | MUTUAL_GAIN / agreed |
| GT2 | 3 | 60/16 | 3 | 0 | 33 | core / 2 / 1 / 0 | 32 / 36 | ACCEPTABLE_PARTIAL / agreed |
| GT3 | 8 | 59/32 | 5 | 2 | 28 | full / 2 / 1 / 1 | 47 / 30 | MUTUAL_GAIN / agreed |
| GT4 | 1 | 50/20 | 0 | — | — | — | — | NO_AGREEMENT / player_walkaway |
| GT5 | 4 | 60/16 | 2 | 0 | 35 | core / 2 / 1 / 0 | 32 / 36 | ACCEPTABLE_PARTIAL / agreed |
| GT6 | 5 | 68/16 | 5 | 0 | 29 | core / 5 / 0 / 0 | 20 / 34 | POOR_AGREEMENT / agreed |

- **GS1–GS7: 7/7 PASS; GT1–GT6: 6/6 PASS.** Каждый replay дважды сравнен целиком по state/events/offers/outcome; deep-frozen inputs не мутируются.
- **W1 PASS:** open/respectful T54/tension20, logistics reveal; accusatory T42/tension30, no reveal.
- **A1 PASS:** одинаковые90/split/50. Без Alog: T64, c4, d0, aspiration26 → reject Us22. С Alog: T68, c5, d2, aspiration22 → accept.
- W1 доказывает последствия **уже нормализованного tone**, не понимание русского языка. A1 не отменяет feasibility/authority.
- GT3 фиксирует agreement на ходе8; GT5 — disclosure через counteroffer без повторного discovery credit. Active commitment и explicit last-turn walkaway имеют отдельные regression tests.
- Наблюдения/score для короткого GT4 не выдумываются: G1 даёт только hard outcome/events; full process score — будущий G6.

# Validation

Все npm команды выполнялись через существующий `.tools/run-npm.mjs`, который assert-ит exact v24.21.0, запускает соседний npm CLI через process.execPath и меняет PATH только дочернего процесса. В его историческом banner остаётся G0; labels/logs этого gate имеют префикс g1. Full logs сохраняются в ignored `.tools/logs`.

| Команда | Hard watchdog | Exit | Elapsed | Результат / log |
|---|---:|---:|---:|---|
| `npm ci --offline --foreground-scripts --no-audit --no-fund` | 180 s | 0 | 3.901 s | PASS; `.tools/logs/g1-ci.log` |
| `npm run typecheck` | 120 s | 0 | 7.327 s | PASS; `.tools/logs/g1-typecheck-certified.log` |
| `npm test -- --reporter=default --reporter=json --outputFile=.tools/g1-tests-final.json` | 120 s | 0 | 4.792 s | PASS; `.tools/logs/g1-tests-final.log` |
| `npm run build` | 180 s | 0 | 5.191 s | PASS; `.tools/logs/g1-production-build-final.log` |
| `npm run smoke` | 60 s | 0 | 1.084 s | PASS; `.tools/logs/g1-production-smoke.log` |
| `npm run audit:model -w @arena/scenarios` | 60 s | 0 | 0.461 s | PASS; `.tools/logs/g1-model-audit.log` |

`npm ci`: 160 packages, cached official Windows prebuilt; fallback к node-gyp не выполнялся. Сохранились G0 warnings о prebuild-install/fs.R_OK/allowScripts, без нового installation blocker. Lockfile после ci не менялся.

Tests: **171/0, 11 files** = 22 G0 + 149 G1. V01/V02 и canonical часть V06 подтверждены. Покрыты complete utility oracle, boundaries, counters/ties, disclosure, authority, credit cycle, offer commitments, last-turn priority, structural/semantic adversarial data, replay и serialization leaks. Числа проверяют training model; они не доказывают человеческое поведение.

Production regression smoke использовал настоящий compiled Fastify entry `scripts/start.mjs`, два отдельных процесса и одну isolated SQLite:
1. GET / и реальный Vite JavaScript asset; /health и /ready →200.
2. Реальный G0 DB module, запись sentinel, clean HTTP/SQLite shutdown.
3. Второй PID, те же HTTP проверки, sentinel сохранился, migration version1 осталась единственной.
4. Второй clean shutdown; WAL/SHM закрыты; временная тестовая БД удалена.
5. Итог: starts=2, cleanShutdowns=2, persistedSentinel=true, orphanProcesses=0.

Это **foundation real-app regression smoke**, не negotiation certification. Нет нового переговорного UI/API: все app/source hashes неизменны, сервер сохраняет только /health и /ready, SPA bundle имя осталось index-BSGBJhMd.js. Browser/mobile и Linux runtime здесь не сертифицируются.

# Generic-engine audit

**PASS: scenarioId/templateId branching = 0.** Поиск production domain source не нашёл S1/S2 IDs, switch(templateId), any, eval, Date.now, Math.random, database/network/filesystem calls. Оба reference используют одни и те же evaluateUtility/evaluateConstraints/evaluateAuthority/transition/selectCounteroffer/classifyOutcome.

Runtime ScenarioDefinition не содержит исполняемых функций. В definition source допустимы builders массивов; их результат — строгий сериализуемый data object. Root workspace exports используют built JS/declarations; TypeScript compiler programmatic API/AST tooling не добавлялись.

# Scope boundary

**G1 only = CONFIRMED.**

**AI NOT STARTED.**
**UI negotiation NOT STARTED.**
**domain persistence NOT STARTED.**
**G2 NOT STARTED.**

Нет negotiation HTTP routes, product DB tables/migrations, provider SDK/env/key, prompts, free-text interpretation, auth/cookies/CSRF/rate limiting, admin/player/feedback UI, deployment или infrastructure installs.

Разрешение planning ambiguity записано явно: возможные имена ai/feedback в разделе G1 плана **не трактовались как разрешение** на ScenarioGenerationResult, PlayerMoveInterpretation, OpponentResponseResult, FeedbackNarrativeResult, provider interfaces или retries/status. Созданы только domain-neutral outcome/evidence primitives. Frozen планы не переписаны.

# External/source notes

Приоритет: исходный [PDF](../../9.%20ОЭЗ%20ППТ%20Алабуга.pdf) → [01: frozen semantics](../01_PRODUCT_AND_ARCHITECTURE_DECISION.md) → [02: gates/goldens](../02_MASTER_IMPLEMENTATION_PLAN.md) → G0 receipt. [00](../00_REQUIREMENTS_AND_SCORING_MATRIX.md) прочитан для requirement/acceptance mapping.

Только implementation mechanics сверялись с актуальными официальными [Zod API](https://zod.dev/api) и [JSON Schema export](https://zod.dev/json-schema), 2026-09-16: strict objects, safe integer runtime validation, discriminated unions и export. Внешние материалы не меняли модель продукта.

BATNA/reservation/aspiration/ZOPA — принятые в frozen плане понятия переговоров. **Конкретные utility, trust/tension deltas, progress credits, discounts, aspiration premiums и outcome thresholds — project-authored training model**, не научно валидированные коэффициенты, психодиагностика или прогноз реальных людей. Новое negotiation-theory исследование не требовалось.

# Findings / corrections

1. Первый typecheck выявил обращение к nullable previous offer; исправлено explicit null handling без any/casts.
2. Начальная schema ошибочно применяла итоговую шкалу utility к отдельным signed contributions. Вклад −115 разрешён отдельно; итоговые −100…200 и spread20…100 по-прежнему проверяет semantic validator. S1 arithmetic/policy не менялись.
3. Первый полный suite:164/164. Adversarial review выявил повторный conditional credit при цикле через иной промежуточный пакет. Добавлены historical offer identity и one-time first-feasible marker; regression tests подтверждают отсутствие farming.
4. Дополнены проверки resource-only commitment disclosure, constraint explanation binding и связи argument predicate с opponent interest. Примеры references не изменились.
5. Typecheck audit-generator выявил избыточный assertion, делавший error branch типом never. Убрана избыточная проверка, affected workspace прошёл; окончательный root typecheck тоже PASS.
6. Final suite:171/171. Повторные полный build/test выполнены после changes; неизменные G0 expensive diagnostics не повторялись. Watchdog не увеличивался, зависших gate-owned процессов не было.
7. Во входном PowerShell чтении потребовался explicit UTF-8; PDF extraction через установленный PyMuPDF выполнен с Python UTF-8 mode. Python/библиотеки не устанавливались и не менялись.
8. Frozen numeric contradiction не обнаружено. Указанные GS/GT/W1/A1 значения и S1 Pareto подтверждены фактическим engine.

# Remaining prerequisites

- **TARGET_LINUX_RUNTIME_SMOKE = NOT_VERIFIED** — carry forward unchanged; V12 полностью не закрыт. WSL/Docker/VM/Linux/cloud не устанавливались и не запускались ради G1.
- **AI_PROVIDER_ACCESS = UNCONFIRMED** — будущая зависимость G3, не реализованный G1 feature.
- **HOSTING_ACCESS = UNCONFIRMED** — будущая зависимость deployment; G1 не развёртывался.
- G2 и последующие gates требуют отдельного разрешения. Playable UI, session persistence и весь AI/admin/feedback flow остаются будущей работой.

# Gate conclusion

Все 34 обязательных критерия G1 подтверждены schema/semantic tests, 54/16 enumeration, exact arithmetic, generic-policy invariants, 13 golden traces, W1/A1, deterministic replay, leak tests, npm ci/typecheck/tests/build, foundation production regression smoke и hash/scope/secret audit. Новых внешних зависимостей и изменённых frozen документов нет.

**G1_DOMAIN_CONTRACTS_DETERMINISTIC_CORE_PASS**

**STOP — G2 NOT STARTED.**

