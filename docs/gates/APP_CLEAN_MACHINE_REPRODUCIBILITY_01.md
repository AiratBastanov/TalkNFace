# APP_CLEAN_MACHINE_REPRODUCIBILITY_01

**VERDICT: APP_CLEAN_MACHINE_REPRODUCIBILITY_01_PASS. REAL_APPLICATION_SMOKE = PASS. CLEAN_SOURCE_SMOKE = PASS.**

Certified: the guided/no-AI Windows x64 **local loopback** demo, from fresh authoritative feature source, through setup, production build, real Chrome use and persisted restart. This is an isolated clean-source simulation on the available PC, not a second physical machine, full G8, public deployment, HTTPS/proxy, Linux/macOS, live AI or final hackathon submission. [Machine evidence](evidence/APP_CLEAN_MACHINE_REPRODUCIBILITY_01.json).

Exact certified source: **`46d2a519e26dd36f5dfa48675dc00b7699455bf3`**, normally pushed to `origin/feature/app-qwen-independent-01` and verified upstream 0/0. This following documentation commit records the tested source; its SHA is resolved with `git log -1 --format=%H -- docs/gates/APP_CLEAN_MACHINE_REPRODUCIBILITY_01.md`. Final receipt HEAD/upstream/clean/main verification is performed after its normal push and reported to the user.

## Baseline, authority and protection

Actual baseline was the requested clean `13f2fda624eb15725849445d4ddcd5d786ab02ab`, branch/upstream `feature/app-qwen-independent-01`, origin `https://github.com/AiratBastanov/TalkNFace.git`. Accepted G5 `da27e557…`, G6 `00e90a19…`, G8 `dfaa7f23…` and protected main/handoff `2034687f6f22b2973935f2c9c30bc9380c88b071` are ancestors. The three requested gate receipts, actual manifests/lock, scripts, ignore rules, README, local demo, environment parsing and migration5 were inspected before implementation. No applicable AGENTS.md was found.

The old README required manual portable-runtime acquisition and showed the owner's original checkout path. Existing runtime scripts themselves had no absolute owner path, but the owner shortcut used `.tmp/owner-app-demo.sqlite` and optional `.env`. The new judge path uses only its own checkout. Existing developer commands remain supported. No application/domain/contract/migration/security source was modified, and package.json/package-lock.json remain byte-identical to baseline.

Original requirements PDF: SHA256 `ff50f0ade59e2060818815284a8be0ccd1f10065a0ce6f46f48b664e4df0d75d`; PDF pp3–5, sections2/3.2/4/5 used only for the local/public launch alternative, working prototype, administrator context, restart persistence, negotiation/feedback and reproducible documentation. No additional AI requirements were inferred.

Before/after byte-only protection: **346 original tracked files**, **418 unchanged pre-existing feature files**, **31 training pins**, no mismatch in bytes/size/mtime. Original checkout and main/handoff remain `2034687…`; remote main was checked again. Historical [APP_AUDIT_AND_QWEN_INDEPENDENT_SLICE_01 PARTIAL](APP_AUDIT_AND_QWEN_INDEPENDENT_SLICE_01.md) remains byte-identical and exactly as recorded; it is neither erased nor reopened, nor recast as proof of gradient-training contamination. Initial filename-only discovery returned some ML README pathnames; their contents were not opened. Subsequent content searches were application-scoped. No TRAIN/DEV/tuning-eval/INTERNAL_TEST/A01–A16 example contents were read or used. Remote training execution remains UNKNOWN; this task made zero model/provider/GPU/training calls.

## Delivered Windows workflow

From the source root, these exact README commands were executed, including the real hidden password prompt and confirmation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Prepare
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Start -Port 3100
```

URL: **http://127.0.0.1:3100/admin**. Player path: `/`, registration-free. Default port without `-Port` is3000; the owner's existing listener on3000 was left untouched, and the occupied-port refusal was observed. Stop/Start retains `.local/arena-demo/arena.sqlite`; config is separate at `.local/arena-config/admin.json`. Both are Git-ignored.

Prepare accepts exact Node24.21.0 x64/npm11.19.0 from PATH or explicit NodePath, otherwise obtains the [official pinned ZIP](https://nodejs.org/download/release/v24.21.0/node-v24.21.0-win-x64.zip). SHA256 **`158f7685b44de51f6c0df1d153526cbcd3e1bc739a8dfc607721cef75de9e541`** was checked against [official SHASUMS](https://nodejs.org/download/release/v24.21.0/SHASUMS256.txt) and the pinned value before extraction. It validates paths, Windows aliases, entry types, duplicates and size limits; refuses links/traversal/unexpected layout; extracts only into ignored local tooling. Incomplete staging is not a usable runtime. Reuse checks local files against the verified ZIP. The machine's system Node22.20.0 was rejected, not silently used.

Dependencies: `npm ci --ignore-scripts --include=dev --no-audit --no-fund`, then the pinned better-sqlite3 prebuilt installer **without its node-gyp/Python fallback**. The Windows hook allowlist is checked before installation. Both npm configs and cache are repository-local; fresh online tests started with no cache. `npm ls --all --include=dev --json`, locked installed versions/workspace links, native SQLite load, production build and source/lock fingerprints passed. The lock contains215 entries; Windows installs160 external packages plus5 workspace links. No AI/provider workspace, global install, upgrade or audit-fix was introduced.

Both build and server explicitly use `NODE_ENV=production`; the acceptance runner checks the actual managed server metadata and production React artifact. Final production JS is376,233 bytes, SHA256 `a84825003bb00824c510336966ec565532c74d46030aaf702f63b1b7b6411900`; it is byte-identical between the fresh Git clone and source-without-.git at different paths. No watch mode or Git metadata is needed to launch.

Password schema: `{"schema":1,"adminPasswordHash":"<generated supported scrypt hash>"}`. Existing G8 scrypt is reused; no default password, plaintext file, password argument or printed hash. Existing config is preserved by Prepare. Explicit SetAdminPassword works while stopped; changing the deployment hash invalidates old admin sessions. Missing/malformed config refuses Start. The launcher ignores deployment `.env`/external HOST, DB and admin-hash overrides. The source-archive smoke used documented stdin automation with a random password held only in memory; the principal clone used the actual interactive prompt.

Start binds only127.0.0.1, serves the real Fastify/React production app, checks source/build/dependencies/config/DB and fails on an occupied port. A per-checkout command mutex prevents overlapping lifecycle commands. A per-checkout local named pipe manages graceful shutdown; Status is read-only. Persisted PID metadata never authorizes killing a process. There is no HTTP stop route, proxy trust, TLS installation, registry/ACL/firewall edit, permanent PATH or execution-policy change. Tool sandbox authorization for network/outside-worktree/Git did not install anything system-wide or request Windows elevation.

## Certified clean source and timings

Real HTTPS clone of the feature branch, not a filesystem clone:

`C:\Users\BastaPC\Desktop\Alag-clean-demo-test-20260928-cm03\Reviewer Jane\Negotiation Arena`

Before setup: no node_modules (including server-local), `.tools`, `.tmp`, `.local`, `.env`, application/package dist, model or dataset runtime directories. No alternate Git object store. No runtime/cache/DB/env/build/model artifact copied from the owner worktree. The clone's tracked status stayed clean. Bootstrap also ran with empty, process-local USERPROFILE/APPDATA/LOCALAPPDATA directories named Reviewer Profile; paths contain spaces. No actual second Windows account was created, and no different physical PC is claimed.

Source acquisition has a separate boundary: an anonymous GitHub read without credential helpers failed. The successful authoritative clone used authorized repository access. A reviewer needs repository permission or a normal source ZIP supplied by the owner. **The application/bootstrap does not need Git or GitHub credentials once the source is obtained.** Repository visibility was not changed.

Machine: Windows11 IoT Enterprise LTSC, build10.0.26100, x64; PowerShell5.1.26100.9444; AMD Ryzen7 5700X3D,16 logical processors. Node24.21.0/npm11.19.0; installed Chrome153.0.8010.53 through Playwright1.63.0, fresh contexts/profiles. No GPU work.

| Measured step | Seconds |
| --- | ---: |
| Authoritative Git clone | 6.077 |
| Node acquisition, SHA/layout checks and extraction | 14.237 |
| Fresh npm ci, empty workspace cache | 4.744 |
| SQLite native prebuilt download/install | 1.327 |
| Dependency-tree verification | 0.591 |
| Production build | 6.261 |
| Prepare including real hidden input/operator pauses | 60.375 |
| First Start, whole process measured by harness | 5.744 |
| First Start's internal PowerShell stopwatch | 5.513 |
| Node phase to ready, after PowerShell runtime verification | 0.671 |
| Prepare + Start, sum of measured commands | 66.119 |
| Clone + Prepare + Start, sum of measured steps | 72.196 |

Two launch commands and two hidden password entries after source acquisition; clone and Set-Location are acquisition steps. Idle gaps between separate commands are excluded, while pauses inside the interactive Prepare are included. This supports a few-minute setup **on this tested PC/network**, not a universal speed guarantee. The 3–5 minute [Russian demo guide](../DEMO_GUIDE_RU.md) describes the presentation after installation.

## Real Chrome journey and persistence

Five bounded cases ran on the final clean clone, using its own runtime, dependencies, production assets and new file SQLite. All passed, no mocks of application/domain/publication/report data and no seeded attempts:

1. S1: admin login with newly configured password → all six G5 settings explicitly selected → save → validate → preview → explicit approval/publication → independent registration-free player → preparation before first turn → guided negotiation → G6/evidence link → replay. Utility64, prepared process100.
2. Other family S2: configured team/urgent/advanced/friendly/team_lead/deliver_scope → complete corresponding flow, utility47/process100, saved-evidence link and immutable-version replay.
3. Actual Stop/Start with the same documented command: publication catalog, admin draft/access, original S1 G6 report and replay remain equivalent; the same player cookie continues replay and records another real turn after restart.
4. Live SQLite backup, integrity verification, stopped restore and restart: the attempt/report remain equivalent, previous DB is preserved, logout remains revoked and the login budget is not rolled back by restoring an older snapshot.
5. A real foreign-origin Chrome fetch and authenticated wrong-CSRF request both receive403 without publication mutation.

Foreign browser exact UUID, report and replay return404; player admin access403; missing CSRF403 without mutation. Admin cookie rotates on login, remains HttpOnly/SameSite=Strict/Path=/, local Secure=false, inaccessible to document.cookie. Password/hash/bearer/CSRF values are absent from localStorage, sessionStorage and source bundle. Gameplay observed **zero external application HTTP requests**, no page errors and no model/provider path. Trace capture is disabled. The intentionally foreign loopback security fixture is separate from gameplay-network observations. G8 authorization/ownership/cookie/origin/expiry/logging source remains byte-identical.

SQLite backup uses [better-sqlite3's supported backup API](https://github.com/WiseLibs/better-sqlite3/blob/master/docs/api.md#backupdestination-options---promise), not a mid-write file copy. Backups and restore candidates pass integrity_check, foreign_key_check and schema verification. Restore requires a stopped managed server, preserves previous DB, carries forward revocations/missing-access denial and conservative expiry/activity/login limits. Explicit reset preserves password and a previous-state backup and refuses junction escape. Ordinary launch never resets data. Unexpected task-owned process termination/restart was tested with a persisted SQLite sentinel. Old attempts, G6 records/relationships and access policy remain unchanged; account/cookie-loss recovery is still absent.

## Source archive without Git

An independent standard `git archive` export of the same commit had **all428 tracked files byte-verified**, no `.git` and none of the ignored runtime artifacts. It was tested at `…\cm03\Source ZIP Space`, using fresh Node/dependency downloads and another empty profile. Prepare/build/Start/Chrome admin authentication/readiness passed. This is a compatibility check, not a new distribution format.

Archive timings: Node acquisition13.753s, npm ci5.221s, native prebuilt1.549s, build7.241s; whole Prepare30.252s, Start6.197s. The full product campaign was not unnecessarily repeated in the archive: its bounded case checks acquisition/build/start/authentication. The final clone and archive production bundle bytes match.

## Failures, review and honest counts

**91 unique named automated cases, 130 executions, 39 reruns.** Setup/build/typecheck, provenance/hash checks and manual launcher experiments are recorded separately, not inflated into new cases.

| Group | Unique | Executions | Reruns |
| --- | ---: | ---: | ---: |
| Existing focused G8/access migration/database/env/password unit/integration | 66 | 66 | 0 |
| New failure/lifecycle group | 19 | 41 | 22 |
| Chrome clean-source/product/archive cases | 6 | 23 | 17 |

Final failure group: 19/19 in 39.543s. It covers pristine read-only Status; unsupported Node; no network on first Node acquisition and empty-cache dependency install; lock disagreement; incomplete/corrupt/tampered runtime; missing/malformed config; interrupted preparation/build; occupied port; locked/inaccessible DB; junction escape; stale PID that names an unrelated process; unexpected server termination/recovery; explicit reset preserving password/verified backup. Network loss is simulated with a process-local unavailable proxy, not a Windows firewall change. No working user data is automatically deleted as recovery.

Earlier failure runs:2pass/1fail,11pass/1fail,4pass/1fail, then2pass; the final19 passed together. The failures were PowerShell test-switch quoting, premature startup-control timeout during SQLite's busy wait, and a Windows harness waiting for inherited stream closure instead of launcher exit. Fixes kept the original limits. The initial PowerShell5.1 stdin property incompatibility was a setup check, not a named case.

Chrome history: warm5, first preliminary clone5/archive1, second preliminary clone5/archive1, final clone5/archive1 =23 executions of6 identities. Preliminary `1db9c34…` and `b2f7c99…` runs are **not production certification**: self-review later found development React due to NODE_ENV, and strengthened restore activity/login-budget preservation. Final `46d2a51…` explicitly uses production and asserts its artifact/environment; only its clean clone/archive support this PASS. This was implementer's self-review, not an independent security audit. No broader historical30-E2E campaign was rerun or counted.

Typecheck, JavaScript syntax, git diff checks and the focused66 cases passed. The application/type/security sources checked by those66 remain unchanged. Budgets stayed Git120s; Node download300s/extract120s; ci+native300s; build300s; startup20s; focused group180s; browser300s global/90s per case; backup/restore60s. No timeout was increased to hide a hang.

## Screenshots and delivery boundary

Actual synthetic demo UI, no credentials, cookies, CSRF or raw session records. Screenshots at390/1280 and overflow assertions passed; selected final screens were visually inspected. This is not a physical-device/WCAG certification.

- [Administrator login](evidence/app-clean-machine-reproducibility-01/clean-admin-login.png)
- [Configured S1 preview](evidence/app-clean-machine-reproducibility-01/clean-preview-S1.png), [configured S2 preview](evidence/app-clean-machine-reproducibility-01/clean-preview-S2.png)
- [Foreign UUID denied](evidence/app-clean-machine-reproducibility-01/clean-foreign-uuid.png)
- [S1 G6 feedback](evidence/app-clean-machine-reproducibility-01/clean-feedback-S1.png), [S2 G6 feedback](evidence/app-clean-machine-reproducibility-01/clean-feedback-S2.png)
- [Continued after restart](evidence/app-clean-machine-reproducibility-01/clean-continued-after-restart.png)
- [Source-without-Git admin ready](evidence/app-clean-machine-reproducibility-01/archive-admin-ready.png)

All task-owned servers/Chrome processes were closed. Task-created warm demo/config were moved, not deleted, into ignored `.local/gate-clean-machine-01`; the working checkout's next Prepare prompts for the owner's own password. Original owner DB/listener and protected original checkout were untouched. Node/cache/DB/config/backups/browser profiles/fresh clones are not committed. Delivery uses explicit source/doc/test paths, normal commits and normal pushes only to the feature branch; no merge or force push.

Remaining: authorized source acquisition; other physical PCs/accounts, Windows10/ARM/Linux/macOS and other browsers; public host/HTTPS/reverse proxy; live AI; full G8 and final submission. Next recommended task: arrange reviewer source access and rehearse these exact commands on another Windows PC. No next gate starts automatically.

**STOP — NO QWEN TRAINING, NO MODEL EVALUATION, NO PROVIDER CALLS, NO PUBLIC DEPLOYMENT, NO MERGE TO MAIN.**
