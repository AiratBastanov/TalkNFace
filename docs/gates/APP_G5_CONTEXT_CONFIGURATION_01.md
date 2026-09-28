# APP_G5_CONTEXT_CONFIGURATION_01

**VERDICT: APP_G5_CONTEXT_CONFIGURATION_01_PASS. REAL_APPLICATION_SMOKE = PASS.**

Implemented and verified the deterministic reference-configuration component of G5. This is not complete G5, live AI generation, or FULL_AI_MVP certification. Implementation: `da27e5571209824b77f08a4e421305f576bb1a18`, normally pushed to `origin/feature/app-qwen-independent-01` and verified at 0/0. [Machine receipt](evidence/APP_G5_CONTEXT_CONFIGURATION_01.json). Review: implementer's focused self-review, not an independent reviewer/certification.

## Baseline and external requirements

Actual clean feature baseline matched the reported `c40ebbbf09ed279239c093efa5c290c0e46f58bb`; no unfinished edits from the blocked attempt were lost. Existing worktree reused. Original checkout and remote main remained `2034687f6f22b2973935f2c9c30bc9380c88b071`. Origin: https://github.com/AiratBastanov/TalkNFace.git. No applicable AGENTS.md found.

All eight pages of the original PDF were read; the page numbers here are PDF pages, including the cover. Frozen architecture reading was limited to **Admin UX**, **Scenario generation**, **Scenario validation**, **Shared scenario schema**. Master-plan reading was limited to **G5 — AI scenario generation + admin workflow**, ending at the next same-level heading. The G6 receipt and relevant audit/status/admin-gap sections were read.

| PDF authority | Delivered mapping |
| --- | --- |
| p3, §2 “Что нужно сделать”, items 2–3 | Actual /admin form: sphere, topic, difficulty, opponent tone/role/goals; deterministic scenario selection/configuration and explicit publication |
| p4, §3.2 | Local browser application with restart persistence; no AI service, keys or special hardware required for this path. PDF makes AI optional; our stronger AI-first product intent remains |
| p5, §4 | Reproducible configure → validate → preview → publish → play → feedback demonstration |
| p7, §7.2 and §8.2; p8, §8.3–8.4 | Both S1/S2 branching families, factual setting effects, guided player journey, useful saved-evidence G6 feedback and replay |

No free-text goal interpreter, raw JSON editor, third family, formula language, AI button or new provider framework.

## Six controls: capability and controlled evidence

The capability/effect table and finite proof limits were recorded before implementation. Final exact bindings are below. All comparisons use independent application fixtures; a different title/hash alone is never the proof.

| Field / option IDs | Existing binding and verified effect | Valid controlled comparison / boundary |
| --- | --- | --- |
| sphere: `supply / team` | Clone frozen S1 vs S2; 3 price/delivery/prepay issues vs 4 scope/days/helper/report issues, different units/interests | Normal/neutral family defaults both validate; S2 full/2/no helper exceeds actual capacity. Sphere change clears topic/role/goals for explicit reselection |
| topic: `launch / planned`; `urgent / reprioritize` | Planned adds all14 to the allowed delivery set and updates its public fact/briefing. Reprioritize forbids HELP=1 and reduces urgent player values by 10, retaining target45 | Same S1 110/all14/0 package: physically rejected for launch, feasible for planned; both contexts have valid target witnesses. Reprioritize is an explicitly rejected request in this slice: unavailable resources cannot reach unchanged target45 |
| difficulty: `beginner / normal / advanced` | Frozen disclosure thresholds35/45/55 and premiums8/15/20; 8 turns, same rubric | Initial S1 95/split/50 yields opponent27: beginner accepts at threshold26, normal rejects at33. Same first logistics question reaches trust54: normal discloses, advanced does not |
| tone: `friendly / neutral / skeptical` | Frozen initial trust/tension60/10,50/20,40/30; skeptical acknowledgement repair2 vs4 | Normal neutral question discloses; skeptical does not. Acknowledging public launch fact leaves tension16 vs28. Both settings have playable witnesses |
| opponentRole: `director / account_manager`; `specialist / team_lead` | S1 authority floor90 vs100; S2 helper proposal authorization required vs self-authorized | Identical S1 price95 accepted by director authority, rejected by manager authority. S2 counteroffer without player grant contains HELP=0 for specialist, HELP=1 for lead. Both normal/cashflow S1 roles and both urgent S2 roles have valid configurations |
| opponentGoals: `cashflow / margin`; `protect_load / deliver_scope` | S1 PREPAY utility0/8/20 vs0/4/18; reservation=BATNA20 vs22. S2 full-scope utility +8; reservation=BATNA25 vs27; associated facts/interests/briefing updated | Same S1 95/split/50 opponent utility27 vs25; same S2 full/2/help/defer30 vs38. Both goal options validate with default roles/normal/neutral. Player action semantics and rubric weights are unchanged |

Exact numerical opponent policy/utility bindings above are review evidence, not player DTOs or bundled UI data. UI descriptions do not disclose private price floors. Public issue prices/units and the player's own target/BATNA remain visible as before.

Finite coverage audit: **144 family-consistent configurations**, **78 accepted / 66 rejected**, 707ms total, maximum single compilation48ms on this PC. These are application configuration checks, not model evaluation or 144 extra test cases. Each accepted candidate executes its witnesses through G1. Matrix is included in the machine receipt:

- S1, either topic: director/cashflow accepts all9 difficulty-tone pairs; director/margin accepts8, excluding advanced/skeptical.
- S1 account_manager/cashflow: beginner with all3 tones, normal/friendly or normal/neutral; other pairs fail the bounded target proof.
- S1 account_manager/margin: all9 pairs rejected for each topic.
- S2 urgent, either role: deliver_scope accepts all9; protect_load accepts8, excluding advanced/skeptical.
- S2 reprioritize, either role/goal: all36 rejected. No helper is added and target45 is not lowered.
- Cross-family IDs, missing dependent choices, unknown IDs/fields and malformed/oversized input are rejected. A bounded witness failure is not a completeness claim about all conceivable dialogues.

## Compilation, validation, privacy and publication

`settings + immutable base hash + context-reference-v1 + context-witness-v1 + deterministic-core-v1 + training-policy-v1` determine the fingerprint. Derived template IDs are `G5-S1-<digest>` / `G5-S2-<digest>`; they never masquerade as unchanged references. Full candidate SHA256 also binds the exact stored definition and witness actions. Timestamps, request IDs, errors and UI state are excluded. Future changes to compiler/policy semantics must advance their versions.

Strict Zod settings and the existing domain validator check sizes/enums/finite values, complete utility tables, references, coherent reservation/BATNA, physical/resource/authority constraints, fact/disclosure/argument bindings and bounded packages. No user expressions or supplied definitions are compiled.

Limits: 2–4 issues, at most1296 packages, **2 deterministic preparation templates × at most64 final packages × at most8 turns**. Preparations ask approved topics, acknowledge available facts and apply known relevant arguments; no dialogue-tree search. At least two distinct mutually rational packages and one target package are required before attempting witnesses. Two different accepted final packages must then actually be reached through the same engine, one at full target. Guided-action availability and public rendering are checked while replaying the proof. An explicit walk-away route is executed separately. Domain validation replays the final stored witnesses again. Missing proof returns an editable invalid draft.

Package feasibility and current acceptance are separate: the manager/cashflow/advanced fixture has a mathematically feasible target package but fails current aspiration/turn-bounded proof. Engine policy is never adjusted to pass validation.

Forward migration4 adds a separate local draft and immutable request receipts; migrations1–3 remain byte-identical. Save binds expected revision and settings hash, increments revision and clears approval. Server validation runs outside the database write lock and atomically rechecks the exact revision before saving. Publication requires current compiler-policy approval, exact candidate hash and explicit `approved:true`; it revalidates the stored server candidate and rechecks revision/validation inside the publication transaction. Client “valid” flags, candidate JSON and stale-tab writes are refused. Repeated request IDs return the saved response; different bodies conflict. Identical candidate content also reuses its immutable publication.

Immutable validation request receipts retain the settings/approval association; publications retain the complete exact definition. Reopening sessions uses that stored definition, not defaults. VersionB/draft edits do not change A, its actions/events/phrases, active replay or terminal G6 evidence. Witnesses, tables and undisclosed facts remain server-side; only requested settings, public player briefing and validation summary leave the configuration service. No administrator truth-view endpoint was added.

## Verification and review

**272 unique unit/integration cases passed:** 236 existing +36 new. First new group33 passed; after focused review, final36 passed (33 repeated +3 additional). Total305 executions; repeated33 are not new cases. Existing236 ran separately, all passed. This does not reuse historical63 reruns.

**25 unique Chrome E2E passed:** 19 existing +6 new. **11 repeated executions**, total36 executions including4 initial harness/expectation failures. Corrections: nested offer label locator; wait for actual replay navigation; legacy migration count3→4; former “zero admin controls” expectation→six selectors. No timeouts increased. The current11 repeats do not reuse the previous gate's8.

Campaigns: new6 first green17.220s; review-affected6 rerun17.547s; legacy first group11 passed/1 obsolete assertion failed in28.150s; next legacy group1 passed/1 obsolete assertion failed in9.241s; final bounded group8 passed in17.885s (the remaining7 unique legacy cases plus one S1 repeat for readable recovery/publication screenshots). Two earlier S1 harness failures took9.583s and5.163s including the npm wrapper. Machine receipt lists groups and current case identities.

Final typecheck9.077s, production build5.529s, new36 tests2.656s, existing236 tests9.907s (wrapper wall times). Production Fastify, installed Chrome153.0.8010.53 / Playwright1.63.0, Node24.21.0 / npm11.19.0, real React and disposable file-backed SQLite. No mocked compiler, validator, publication or report. The lost-publication test drops transport only after the real commit. Pending validation is a held real request. The old injected feedback GET failure still retries safely.

Verified: both configured full journeys; exact saved evidence links and keyboard focus; missing preparation/early exit keeps insufficient observations; current/different version comparisons; unchanged old S1/S2 behavior; stale saves/publications; same-ID conflicts/lost-response retry; two-connection races during validation and publication; draft/publication/active and terminal session restart; migration2/3 fixtures; legacy browser upgrade; public/private DTO and bundle boundaries; frozen object immutability. All task server starts ended in clean SQLite shutdown; browser workers exited. No owner demo DB used.

Focused self-review covered the actual diff and journey. It removed exact authority-floor hints from UI, replaced a long derived hash in preview with a family label, linked field errors, and added race/client-JSON/feasibility-versus-reachability checks. There was no independent reviewer. No score, rubric applicability, preparation check or missing-evidence rule was loosened.

## Real screenshots inspected

Viewport and full-page captures were opened and visually inspected: readable Russian labels, wrapping, visible keyboard outline, actionable validation/recovery, usable approval/publication controls; overflow assertions passed. No physical-device, Safari, screen-reader or full WCAG certification.

- [Initial controls and focus,360](evidence/app-g5-context-configuration-01/g5-initial-360-viewport.png), [all six controls,1280](evidence/app-g5-context-configuration-01/g5-initial-1280-viewport.png)
- [S2 preview,390](evidence/app-g5-context-configuration-01/g5-s2-preview-390-viewport.png), [effective S1 settings,1280](evidence/app-g5-context-configuration-01/g5-preview-1280-viewport.png)
- [Invalid resources,360](evidence/app-g5-context-configuration-01/g5-invalid-resources-360-viewport.png), [changed approval/save controls,390](evidence/app-g5-context-configuration-01/g5-stale-tab-390-viewport.png)
- [Lost publication response/retry,390](evidence/app-g5-context-configuration-01/g5-publication-retry-390.png), [explicit approval/publication,390](evidence/app-g5-context-configuration-01/g5-publication-controls-390.png)
- [Exact saved action focus,390](evidence/app-g5-context-configuration-01/g5-s1-evidence-390.png), [configured S2 G6 report,1280](evidence/app-g5-context-configuration-01/g5-s2-report-1280.png)

## Protection, remaining boundaries and owner demo

Byte-only before/after verification: all346 original tracked files and364 protected existing feature files unchanged, including metadata;31 prior training pins,20 accepted manifest pins and8 shared authority pins verified. Shared dependencies include frozen g3/action/common contracts, AI context/prompt, S1/S2 references and interpretation schema. G1, old contracts, ML compiler/prompts/data/splits/evaluation fixtures, locks/tools and previous receipts are unchanged. Original PDF SHA256: `ff50f0ade59e2060818815284a8be0ccd1f10065a0ce6f46f48b664e4df0d75d`. Root package/lock and explicit app workspaces unchanged; no install/upgrade. The app-only catalog contract was extended, with one new app-only contracts export.

**Historical boundary incident remains:** [previous PARTIAL receipt](APP_AUDIT_AND_QWEN_INDEPENDENT_SLICE_01.md) records two exposed evaluation rows. Those cases were not reopened or changed here. No inference of gradient-training contamination is made. Current task: no TRAIN/DEV/tuning-eval/INTERNAL_TEST/A01–A16 example content read or used; no new read-boundary incident observed. Frozen planning/PDF files remain unchanged.

The reopened session still inherited a sandbox that denied worktree writes; scoped sandbox approvals were used for app-worktree writes and the necessary linked-worktree Git operations. No Windows ACL, registry, firewall, UAC, permanent PATH or Git-directory changes. No reset/clean/stash/restore/rebase/amend/force push, merge, training, inference, model evaluation, GPU experiment, provider installation, paid call, tunnel or deployment.

Auth/ownership/CSRF remains **OPEN and required before public hosting**. One shared local admin draft is not a multi-user workspace; UUIDs and hidden links are not access control. Live scenario generation, free-language play and AI narrative remain future work. QwenV1's frozen interpreter contract is unchanged; these derived contexts are not certified for its accuracy. Later AI integration must pass the same domain/publication proof boundary and separately verify actual context support.

Reproducibility: existing pinned environment and owner launch verified on this PC; no fresh clean-machine install in this gate. Linux/macOS/other browsers, submission links, presentation/pitch and public delivery remain unverified/incomplete. One next recommended task: **authentication, session ownership and CSRF protection before any public hosting**.

Already built owner worktree, PowerShell:

~~~powershell
Set-Location 'C:\Users\BastaPC\Desktop\Alag-app-work'
$env:HOST = '127.0.0.1'
$env:PORT = '3000'
$env:DATABASE_PATH = '.tmp/owner-app-demo.sqlite'
& 'C:\Users\BastaPC\Desktop\Alag\.tools\node-v24.21.0-win-x64\node.exe' .\scripts\start.mjs
~~~

http://127.0.0.1:3000/admin. Configure supply/planned/normal/friendly/director/margin → save → validate → preview → explicitly approve/publish → start → save preparation → logistics question/acknowledgement/argument → payment question →95/split/50 → G6 evidence → replay. Checked result: player utility64, complete target; prepared process100. S2 urgent/advanced/friendly/team_lead/deliver_scope uses the normal priorities/resources/report acknowledgement/resource argument/full-2-help-defer path, utility47 and prepared process100. Early exit or missing preparation does not receive that score.

This receipt follows the implementation commit; resolve its exact commit with `git log -1 --format=%H -- docs/gates/APP_G5_CONTEXT_CONFIGURATION_01.md`. Final delivery must verify HEAD equals its own upstream,0/0, clean feature worktree and unchanged original/remote main; final SHA is reported to the owner.

**STOP — NO QWEN TRAINING, NO MODEL EVALUATION, NO LIVE AI PROMOTION, NO PUBLIC DEPLOYMENT, NO MERGE TO MAIN.**
