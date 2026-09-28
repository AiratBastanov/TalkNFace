# APP_G6_DETERMINISTIC_FEEDBACK_01

Status: independently verified deterministic component; complete G6 remains pending. Baseline: `4b388743d8ec56a0431e076d6cd121c752f932e3`.
Implementation commit: `00e90a19527ab2b74986e542cebf40378059faf4`. [Machine receipt](evidence/APP_G6_DETERMINISTIC_FEEDBACK_01.json).

Selected subset: server deterministic evidence/rubric, preparation record, public report, validated rule suggestion and direct replay comparison. Live AI and complete G6 remain pending.

## Formalization recorded before implementation

Authority: architecture “Evaluation architecture” (lines 226–249), “Feedback generation” (250–257), master plan G6 (284–315), each bounded by the next heading of its level. No adjacent cases read.

Four layers remain separate: immutable hard outcome, committed behavioral events, versioned pedagogical checks, future AI narrative. This slice has no narrative provider. The following resolves underspecified predicates without changing domain policy:

| Check | Opportunity and pass predicate |
| --- | --- |
| Preparation / goal (15 dimension weight) | Explicit app-only pre-start choice of public target or own BATNA, recorded at revision 0; chosen threshold must have a physically and authoritatively feasible package with both parties at least BATNA and player at least threshold. Enumerate the existing bounded package catalog, never dialogue trees. Missing record is unobservable, never default credit. |
| Preparation / boundary | Explicit acknowledgement of the player's exact own BATNA value before first committed move, bound to session/version; missing record is unobservable. |
| Interests / discovery (25) | Initial approved question flow makes this an available opportunity in S1/S2. Pass on a committed disclosure of an opponent private interest (including an interest-linked resource), through an approved domain disclosure. Duplicates add nothing. |
| Interests / use | A committed acknowledgement of a known specific fact must precede or accompany a player's feasible proposal/acceptance that implements its binding. Binding: scenario argument condition referencing that fact; or satisfaction of a constraint/authority rule whose explanation fact is exactly that fact. Shared issue IDs alone do not establish a link. Available known acknowledgement facts constitute opportunity; skipping discovery does not remove the initial public-fact opportunity. |
| Argument / grounded (20) | Committed grounded-argument event, known prerequisite facts before that turn, nonempty objective condition. Selecting an arbitrary tone has no credit. Opportunity exists if a binding is already available or can be discovered through the approved initial question flow; missing the question is failure, not N/A. |
| Argument / objection | A recorded physical, authority or aspiration rejection followed by a player decision slot is opportunity. Pass requires a later feasible own proposal or exact active acceptance resolving the rejected rule(s); for aspiration, a strictly improved opponent utility relative to that rejected offer, or accepting the counteroffer produced for it. Link the actual rejection and response. No rejection or no subsequent slot is N/A. No inference from natural language. |
| Value / mutual (15) | Opportunity exists from the initial model's feasible package space. Pass on an actually proposed, feasible and authorized own package with both utilities ≥ BATNA; agreement is unnecessary. Acceptance alone is not a proposal. |
| Value / Pareto | After an own offer, a subsequent decision slot with at least one feasible authorized package improving one utility without worsening the other is opportunity. Pass compares a later own offer to its immediately preceding own offer using exact domain utilities. Otherwise fail; if no such objective opportunity, N/A. |
| Concession / reciprocal (15) | After an own offer, a subsequent slot with a feasible package satisfying existing `qualifiesConditionalExchange` is opportunity (testing its actual term as a potential bound condition). Pass requires a committed feasible own offer with genuine recorded `conditionalOn` satisfying that same predicate; a decorative condition fails. |
| Concession / discipline | Available solution = most recent feasible own package meeting both BATNAs, otherwise an active binding opponent package meeting both BATNAs. Inspect subsequent decision windows. Empty or decorative conditions do not establish reciprocity. Fail on an unconditional own proposal/acceptance lowering own utility without increasing the opponent's relative to that recorded solution. No available solution with a subsequent slot is N/A. |
| Relationships / pressure (10) | All committed action slots are the inspection window. Pass if no damaging-tone event. This is a property of this teaching model, not a personality inference; it cannot alone unlock an overall score. |
| Relationships / repair | Recorded increased tension/warning with a subsequent slot is opportunity. A domain `tension_repaired` alone proves warning removal, not cause-specific repair. Pass only when its fact ID matches an explicitly contradicted fact on the originating tension action. No repair event after an available slot fails; a repair event lacking that causal binding is unobservable. No tension/response slot is N/A. Missing cause instrumentation is a disclosed limitation. |

Statuses are passed, failed, not applicable (objective opportunity absent), unobservable (required evidence missing). Applicability and evidence sufficiency are separate fields. Incomplete event instrumentation cannot prove successful behavior or absence of bad behavior. Each absence finding identifies its inspected turn window.

Dimension = 100 × passed/applicable. A dimension with any required missing evidence has no numeric score. Overall normalizes the approved weights over applicable dimensions, and requires ≥6 applicable checks, ≥3 unique accepted progress-credit events, and no required unobservable check. Otherwise “Недостаточно наблюдений”. No hard-outcome bonus; no turn-count, duplicate, politeness or phrase-copy bonus. Round only the final displayed numbers, not intermediate arithmetic.

## Storage, identity and privacy policy

Pure server derivation over immutable terminal session/version/turn/action/event/saved public transcript records, in one read transaction. No report queue or report migration. Forward migration 3 adds only immutable pre-start preparation records; migrations 1/2 and all frozen contracts stay unchanged. Historical sessions retain their records. Reports explicitly name the computation's evaluator version, concrete rubric version plus the scenario's declared rubric version, definition hash/configHash, terminal revision and evidence digest. They do not claim to have existed at original completion.

Quotes use exact saved guided phrases, never current render templates; full-string UTF-16 spans are checked against surrogate boundaries. Structured events and inspection windows are labelled, without fabricated quotes. Evidence carries session/version/turn/request/event references; malformed or cross-session links are rejected. No private event payloads, opponent utility/BATNA numbers, hidden facts, definitions or witness traces are returned. Only the approved rubric conclusion is public.

One deterministic next focus: bind to a failed check (or explicitly absent preparation), validate a proposed canonical action on the actual pre-turn snapshot using domain context, physical and authority predicates and public projection. Proposed wording is labelled an alternative; it does not predict agreement. No counterfactual simulation. Report GET failures and presentation state never enter the evidence digest.

Replay remains a separate session. Only its immediate recorded predecessor is accepted. Require terminal attempts and compatible configHash, definition hash, rubric and evaluator policy. Compare shared observed applicable checks; differing opportunities and missing evidence are explained. Do not subtract unrelated overall scores or call a difference skill improvement. Noncomparable reports retain separate factual outcomes.

## Protected boundaries

Original checkout and remote main: `2034687f6f22b2973935f2c9c30bc9380c88b071`. Before writes, captured byte-only SHA256 and metadata for 346 original and 357 feature tracked files; 31 recorded training pins verified. Original portable Node is read-only. All disposable DBs, logs, dependencies and builds stay in the application worktree.

Historical gate `APP_AUDIT_AND_QWEN_INDEPENDENT_SLICE_01` remains PARTIAL: its broad search exposed two frozen-eval rows; the receipt says they were not used in implementation/tests. This is not proof of Qwen gradient-training contamination. No cases reopened or changed. This task's access status is recorded separately at completion.

Auth/ownership/CSRF remains OPEN; UUIDs are not authorization. Demo is loopback-only. No public deployment, training, model evaluation, friend's computer access, or merge. Remote training execution UNKNOWN.

## Verification and delivery

Pre-implementation validation plan (current results below). Finite budgets: Git/network 120s, typecheck/tests 180s, build 300s, each browser campaign 180s global/90s per test, startup 12s. Planned browser groups: existing S1/S2 regression (12 unique); new feedback acceptance; legacy migration acceptance if needed. Reruns will be counted separately.

## Delivered behavior and validation

**VERDICT: APP_G6_DETERMINISTIC_FEEDBACK_01_PASS. REAL_APPLICATION_SMOKE = PASS.**
Only the independently implemented deterministic component is certified. No FULL_G6_PASS, FULL_G7_PASS or FULL_AI_MVP_PASS.

The player can explicitly record preparation, finish either existing guided scenario, read the unchanged agreement/no-agreement result separately from process checks, open exact saved actions, use one validated next focus, start a separate replay and compare its common observed checks with the immediate predecessor. The offer form now exposes the already-existing canonical reciprocal-condition field. No domain transitions or utility changed.

Observable in both S1/S2 guided modes: discovery, linked acknowledgement/use, grounded arguments, actual objection responses, feasible/mutual own offers, Pareto comparisons, genuine conditional exchange, concession discipline, damaging action absence. Preparation is observable only with the separate pre-start record. Cause-specific repair remains unobservable when warning removal lacks a binding to the actual cause. Legacy event gaps remain missing evidence, not success/N/A.

During final review, added completeness verification against existing domain social predicates (only to detect missing instrumentation, never to invent scored events), offer/credit record consistency and domain hard-outcome consistency. Exact saved phrases now accompany acknowledgements, arguments and damaging actions. One further suggestion can consider an already-issued active offer only if it was available before the original action and at least as useful as the player's own alternative. No new utility authority or simulated outcomes.

Synthetic application examples (independently reasoned, no model-eval fixtures):

| Attempt | Unchanged hard outcome | New deterministic process |
| --- | --- | --- |
| Prepared S1: discover logistics, acknowledge it, ground argument, discover payment, propose 95 / split / 50 | MUTUAL_GAIN, own utility 64 = 170 − 95 − 5 − 6 | 100; 7 applicable checks, 5 accepted credits; no concession opportunity |
| Prepared S2: priorities/resources, acknowledge report, resource argument, full / 2 / help / defer | MUTUAL_GAIN, own utility 47 = 65 − 8 − 10 | 100, with exact fact→package links |
| Prepared S2: resources, acknowledge helper, core / 5 / no help / no defer | POOR_AGREEMENT, own utility 20 | 44.12 = (15×100 + 25×50 + 20×0 + 15×0 + 10×100) / 85 |
| Prepared S1: propose mutual package before exploring, then discovery/ack/argument and exit | NO_AGREEMENT, own utility null | 70; mutual-package process credit is retained |
| Old session / early exit → separate prepared S1 replay | Original no agreement; replay own utility 64 | Original has no overall score. Shared discovery/use checks change from failure to pass; no subtraction of totals, no “skill improvement” claim. |

### Current test counts, not historical baseline counts

- **236 unique unit/integration cases verified**: 207 existing + 29 new application feedback cases. Full run initially 232/234; two failures were old migration-count expectations. Corrected affected G2/catalog group 36/36; final feedback group 29/29 (27 repeated + 2 new). **63 repeated case executions**, not new cases. Current total case executions: 299.
- **19 unique Playwright Chrome E2E**: 12 existing S1/S2 + 6 feedback flows + 1 new conditional-control flow. The existing 12 passed in 23.705s. Feedback six passed in 16.905s, then six affected cases passed after review in 16.576s. The conditional-control case passed in 4.145s. **8 repeated case executions** across the new group (two first-case harness failures and six post-review reruns), not eight new cases. A separate initial module-resolution failure executed zero cases.
- Harness failures corrected without increasing timeouts: server-local SQLite driver resolution; nested label/select locator; using real Tab navigation for `:focus-visible` instead of programmatic focus following a mouse click. Browser campaign stopped at first failure each time.
- **One additional standalone real Chrome legacy smoke**, on a copy of the pre-existing accepted G2 production SQLite (not a regenerated fixture): initial S1 snapshot/first turn/version preserved, continued through UI, report withheld unsupported preparation score, server restart preserved report byte-equivalent JSON. Original seed file unchanged. Separately, new E2E seeds migration-2 S1/S2 and a mismatched-version replay using app-only fixtures.
- Current final typecheck 9.040s; final production build 5.665s; final feedback tests 2.712s; added E2E typecheck 0.873s. No npm ci, dependency download, watch mode or timeout increase.
- Browser uses installed Chrome 153.0.8010.53, actual production `npm start`, file-backed isolated SQLite, real React/API. No mocked report, opponent or model. Only a feedback GET network failure is injected. No external browser HTTP requests or page errors. Task-owned processes close cleanly.
- Meaningful checks include immutable outcome/session after report errors; refresh/restart stability; missed/no/missing opportunities; retries/duplicates; genuine versus decorative reciprocal terms; actual objection/fact links; unavailable prior-state suggestions; Cyrillic/emoji and UTF-16 surrogate boundaries; stale/unrelated/cross-session IDs; terminal public projection and built-bundle privacy; comparison compatibility; migration survival.

The old gate's 207 tests, 12 Chrome cases and three affected reruns were historical evidence. They were not copied as current acceptance: all 207 existing tests and all 12 existing Chrome cases were executed here. Its three historical reruns are not counted above.

### Real screenshots and focused review

Screenshots contain only synthetic application attempts:

- [S2 report, 1280](evidence/app-g6-deterministic-feedback-01/g6-s2-report-1280.png)
- [Poor S2 report, 360](evidence/app-g6-deterministic-feedback-01/g6-poor-report-360.png)
- [Insufficient observations, 390](evidence/app-g6-deterministic-feedback-01/g6-insufficient-390.png)
- [Exact saved S1 evidence, 390](evidence/app-g6-deterministic-feedback-01/g6-s1-evidence-390.png)
- [No agreement with process credit, 360](evidence/app-g6-deterministic-feedback-01/g6-no-agreement-360.png)
- [Fetch error and retry, 390](evidence/app-g6-deterministic-feedback-01/g6-fetch-error-390.png)
- [Noncomparable replay, 1280](evidence/app-g6-deterministic-feedback-01/g6-noncomparable-1280.png)
- [Real reciprocal condition and saved phrase, 360](evidence/app-g6-deterministic-feedback-01/g6-reciprocal-360.png)

Images were opened and visually inspected at 360/390/1280: readable wrapping, no horizontal overflow, explanatory empty/error states, usable links. Real Tab/Enter navigation verifies visible keyboard focus and focus transfer to the exact saved turn. Dynamic loading/errors use status/alert; static report paragraphs are not live regions. No full WCAG, screen-reader, Safari or physical-device certification.

A separate post-implementation diff/user-flow review checked formula against fixed expectations, incomplete event handling, original-outcome consistency, missing preparation, causal links, private projection, current-template versus saved-phrase separation, immutable replay and forward migration. Review was performed as a separate pass by the implementing agent; no independent person/subagent review is claimed.

### Access boundary, protection and remaining work

**Historical incident:** the prior receipt remains byte-identical and PARTIAL. Two frozen-evaluation rows were exposed by its broad search; its recorded assertion is that they were not used for implementation/tests. This task neither reopens those rows nor claims they were never exposed. This is not proof of contamination of Qwen gradient-training data.

**This task:** bounded permitted architecture/G6 sections, application/domain source and app tests only; no TRAIN/DEV/tuning-eval/INTERNAL_TEST/A01–A16 examples read or used. Pin manifests inspected as metadata; protected dependencies hashed byte-only. No new read-boundary incident observed. No external CaSiNo/Job Interview material. No changes to evaluation sets or retraining.

Protected-file verification and implementation commit are recorded in the machine receipt. Original tracked checkout and main refs remain on 2034687; frozen source/plans/PDF, old receipts, training/smoke tools, models/runtime/candidate locks, ml/evals/data are unchanged. Root explicit application workspaces and external dependency versions are unchanged; only one additive contracts export was added. No raw sessions, DBs, credentials or private model/dataset material are committed.

Live AI narrative/classification and complete G6 remain pending. Cause-specific repair may need additive app instrumentation. Authorization/ownership/CSRF and public deployment remain OPEN; UUIDs are not authorization. Remote training execution is UNKNOWN; no friend's computer contact, Qwen, model evaluation, paid API, deployment or merge.

### Owner launch and delivery

Already built worktree, PowerShell:

~~~powershell
Set-Location 'C:\Users\BastaPC\Desktop\Alag-app-work'
$env:HOST = '127.0.0.1'
$env:PORT = '3000'
$env:DATABASE_PATH = '.tmp/owner-app-demo.sqlite'
& 'C:\Users\BastaPC\Desktop\Alag\.tools\node-v24.21.0-win-x64\node.exe' .\scripts\start.mjs
~~~

URL: http://127.0.0.1:3000/admin — publish/select S1 or S2, then record preparation explicitly before the first move. Portable Node remains read-only in the original checkout; app dependencies and SQLite live in the feature worktree.

Normal commit/push only to `origin/feature/app-qwen-independent-01`. The machine receipt names the implementation commit verified at upstream 0/0; this documentation is a following receipt commit. Its exact SHA is available with `git log -1 --format=%H -- docs/gates/APP_G6_DETERMINISTIC_FEEDBACK_01.md`. Final HEAD/upstream 0/0, clean worktree and unchanged remote main are checked again after that push and reported to the owner.

One recommended next task: close the app ownership/authentication/CSRF boundary as a separate G8 task before considering public deployment.

**STOP — NO QWEN TRAINING, NO MODEL EVALUATION, NO LIVE AI PROMOTION, NO PUBLIC DEPLOYMENT, NO MERGE TO MAIN.**
