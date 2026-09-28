# APP_G8_ACCESS_BOUNDARY_01

**VERDICT: APP_G8_ACCESS_BOUNDARY_01_PASS. REAL_APPLICATION_SMOKE = PASS.** This certifies the bounded, no-AI access component in the tested local environment, not full G8, public deployment, production hardening or live AI. [Machine receipt](evidence/APP_G8_ACCESS_BOUNDARY_01.json).

Implementation commit: `dfaa7f2388d6ab7ab1af267a85e6f11bbf9cb5c0`, normally pushed and verified at feature upstream0/0 with a clean worktree. This following receipt commit records that exact verification; final delivery is checked again after its push.

## Baseline and security model (written before implementation)

Worktree `C:\Users\BastaPC\Desktop\Alag-app-work`, branch `feature/app-qwen-independent-01`, exact Git HEAD/upstream `720a2e8ea79ac17be965c5d6fd1617a73d5b47c9`, clean. Authoritative origin `https://github.com/AiratBastanov/TalkNFace.git`. Original checkout and remote main `2034687f6f22b2973935f2c9c30bc9380c88b071`. No applicable AGENTS.md found in ancestors or application directories. Actual latest migration: 4. Runtime Node24.21.0, Fastify5.12.5, SQLite/better-sqlite3 12.11.1; existing lockfile inspected.

Current gap: **a UUID or knowledge of a route identifier is not authorization**. Admin configuration/publication, player sessions, reports and replay currently lack authentication, ownership and CSRF checks. Existing public/private projection, immutable publications and G5/G6 semantics remain authorities.

Historical [APP_AUDIT_AND_QWEN_INDEPENDENT_SLICE_01 PARTIAL](APP_AUDIT_AND_QWEN_INDEPENDENT_SLICE_01.md) remains exactly as recorded. It is neither erased nor reopened. Current reading: three requested gate reports; only master-plan G8 through the next same-level heading; architecture Deployment, Logging/privacy and ADR-09. No ML example contents are used; protected files are verified by byte-only hashing.

Actors and assets: public browser has only catalog/assets/health/bootstrap; a registration-free player principal owns its attempts, turns, preparation, results, reports and replays; administrator authenticates one deployment secret and can configure/publish the shared draft, but can inspect only its own player attempts. Unrelated browsers cannot acquire ownership by supplying IDs. Future public hosting requires explicit HTTPS origin and secure cookies, and has a separate certification boundary.

Design: 256-bit cryptographic opaque bearer; only SHA256 digest persisted. Separate stable principal ID survives privilege rotation; access-session role is player/admin. CSRF synchronizer tied to the access session, returned by same-origin auth endpoint and sent as `X-CSRF-Token`; no bearer in DTO, URL or browser storage. Derive CSRF from the bearer with HMAC-SHA256 domain separation, persist its digest. Player lifetime: 24h idle, 7d absolute; admin: 30min idle, 8h absolute. Only validated unsafe API activity may refresh idle time, at most once per 5min. GET/HEAD never write, including auth inspection. SQLite unixepoch is the lifecycle clock. Logout revokes persisted access and explicitly deletes cookie; privilege elevation atomically revokes and rotates token and CSRF, with recheck after password verification. Closing a tab cannot extend absolute expiry. Expired/revoked credentials never become valid after restart.

Cookie: HttpOnly; SameSite=Strict; Path=/; no Domain; fixed absolute Max-Age. Local profile only on loopback HTTP, `arena_session`, Secure=false. Future public profile requires explicit HTTPS APP_ORIGIN and `__Host-arena_session`, Secure=true. Unsafe Origin must exactly match configured origin; reject cross-site/same-site Fetch Metadata, null/missing/foreign Origin. Clients without Fetch Metadata must still supply exact Origin and CSRF. No CORS reflection. Initial POST bootstrap has no preceding CSRF token: requires exact Origin, JSON and `X-Arena-Bootstrap: 1`; it cannot elevate, accept caller identity, rotate a valid session or bind legacy data. Safe auth GET only reads an existing session.

IDOR checks query ownership before loading protected data. Unknown, legacy and foreign IDs return the same safe 404. Comparison checks both attempt and predecessor ownership. Missing/expired access is 401; insufficient admin privilege / CSRF / origin is 403; existing revision/idempotency conflicts remain 409. All routes require an explicit access classification; static shell contains no protected data. No administrator override for other players.

Admin: environment-only `ADMIN_PASSWORD_HASH`, standard Node scrypt (N=32768,r=8,p=1,32-byte output,16-byte random salt), constant-time digest comparison. Missing hash disables login/admin access; malformed hash fails startup without echo. No username. Durable single-node global login budget (10 attempts per 15min, including successes) bounds verification and survives restart; no distributed rate-limit claim. No OAuth/MFA/reset/identity SDK. HttpOnly reduces credential theft through script reads, but same-origin XSS/compromised device or plaintext loopback interception remain outside its guarantee. Browser credentials are never logged; framework error bodies are replaced by fixed safe messages. Security logs use event/class/coarse reason only.

## Explicit route/access matrix

| Route | Access | Unsafe requirements |
| --- | --- | --- |
| GET/HEAD static assets and SPA shell, /health, /ready | Public; shell includes /admin login | No writes |
| GET/HEAD /api/reference-scenarios, /api/scenarios | Existing public projections | No writes |
| POST /api/auth/bootstrap | Public -> fresh player if no valid session | Exact Origin, Fetch Metadata check, JSON, bootstrap header |
| GET/HEAD /api/auth/session | Existing player/admin session, returns role/configuration/CSRF | No writes |
| POST /api/auth/login | Existing pre-auth player/admin -> rotated admin | Origin + session CSRF + login budget + password |
| POST /api/auth/logout | Existing principal -> revoke/delete cookie | Origin + session CSRF |
| GET/HEAD /api/admin/reference-scenarios/:key, /api/admin/context-draft | Admin | No writes |
| POST /api/admin/reference-scenarios/:key/publish, /api/admin/context-draft/{save,validate,publish} | Admin | Origin + CSRF |
| POST /api/sessions | Player or admin, creates own attempt | Origin + CSRF; atomic owner insert |
| GET/HEAD /api/sessions/:sessionId, /result, /preparation, /feedback | Owner, including admin's own attempts only | No writes |
| GET/HEAD /api/sessions/:sessionId/feedback/comparison | Owner of both attempts | No writes; existing replay relationship rules |
| POST /api/sessions/:sessionId/{turns,preparation,replay} | Owner | Origin + CSRF; replay inherits same owner |
| Any unclassified API/route/method | Deny | No mutation |

## Migration and legacy policy

One additive migration5 after actual migration4: principals, revocable access sessions, immutable attempt ownership and durable login budget. Migrations1–4 byte-identical. No backfill or first-UUID-claim mechanism. All prior attempts remain unowned/inaccessible through player APIs, while publications, session/turn/preparation/draft/request bytes and derivable reports remain intact in SQLite. No administrative archival endpoint is needed for this demo. New attempts and replays receive owners atomically. Losing/revoking the only cookie has no account recovery in this MVP; published scenarios can be played again under a fresh principal.

Verification plan: focused independent authorization expectations, real production Chrome with disposable file SQLite and separate browser contexts, both configured G5/G6 journeys and all existing guided flows, fresh/migration2/3/4 upgrades and immutable bytes, cookies in loopback and injected TLS profile, restart/expiry/revocation/CSRF/IDOR/login throttling/redacted errors. Budgets: Git/network120s, tests/typecheck180s, build300s, start12s, Chrome campaign180s/test90s. No provider/model/GPU/training/public deployment or merge.

## Delivered boundary and review

One `AccessBoundary` hook classifies exact HTTP method/route templates and checks identity before protected objects load. It does not grant admin a bypass over player ownership. Session creation and replay wrap the unchanged negotiation service in a transaction that inserts ownership atomically. Comparison checks both IDs before the existing relationship validation. The domain/repository/feedback/compiler algorithms and old contracts are byte-identical. Only a new app-only access contract/export adds error codes and auth DTOs.

SQLite contains SHA256 bearer and CSRF digests, never raw credentials. The random bearer is a 32-byte base64url value. CSRF is a domain-separated HMAC-SHA256 of that bearer, checked against its persisted digest; it cannot authenticate without the cookie. Login invalidates the prior session atomically and rechecks expiry/revocation after asynchronous scrypt. The stored admin credential fingerprint also invalidates old admin sessions after deployment-hash replacement/removal. Logout and expiry survive a real restart. Revoked/expired rows are retained, not automatically repaired or deleted.

The SPA has one API path for CSRF. It keeps the CSRF only in module memory, uses browser-managed same-origin cookies and differentiates 401, 403 and existing 409 codes. A 403 from a rotated/logged-out tab refreshes its identity without automatically replaying the mutation. The login form clears its password after submission; no password or bearer enters browser storage. Existing localStorage last-attempt UUID and sessionStorage pending public commands remain navigation/retry data. Admin logout clears those app keys; loss/expiry of the only cookie has no recovery path in this registration-free MVP.

Framework request logging is disabled, error serializers omit raw request/error content, and API errors use fixed Russian messages. Security events contain event/time/route class/coarse reason only. API responses are no-store; referrer policy is no-referrer. Playwright traces are disabled because traces would capture authentication headers. Tests use fresh in-memory random credentials and separate explicit cookie jars, never a production test bypass.

Review: implementer's focused self-review, not an independent audit. It added a real two-tab logout regression and an asynchronous login/logout race check, corrected password-generator stdout to contain only the hash, and chose a Node launcher that works without changing Windows PowerShell execution policy. No unsafe request is retried automatically after an auth failure. No approval, scoring, ownership or privacy rule was relaxed to pass a test.

## Verification results and honest counts

**321 unique unit/integration cases pass: 272 existing + 49 new.** Total406 executed case runs, including85 repeated runs and two initial failed expectations. First42 access cases:41 pass/1 failed because the test requested an invalid report revision0 before ownership checking; revision1 corrected the fixture. Next45 access/migration cases passed. Existing272:271 pass/1 obsolete migration-count expectation failed; the single corrected migration test passed. Review46:44 access + password-command + owner-launch passed. Existing domain tests are not new security cases. Typecheck/build failures during implementation were compile checks, not additional test cases.

**30 unique Chrome E2E pass: 25 existing + 5 new; 36 executed case runs, including6 reruns.** First new campaign:2 configured journeys pass, foreign-origin inspection fails, expiry not run. Foreign-origin repeated once with an unavailable header assertion, then passed using HTTP403 + actual foreign page origin + the server's ORIGIN_REJECTED event + unchanged publications. Expiry passed separately. All25 prior flows passed in one campaign (73.916s wrapper). Final five security flows, after client review, passed together (17.625s wrapper). One Windows npm regex-pipe quoting error executed zero tests. No test timeout was increased; the production server had rejected the foreign-origin mutation on every attempt.

Final typecheck10.759s, production build5.931s, focused security/command/owner-launch group7.372s, production lifecycle smoke1.261s. Node24.21.0 / npm11.19.0, Chrome153.0.8010.53 / Playwright1.63.0, production Fastify with actual React assets and disposable file-backed SQLite. Auxiliary accepted-G2 fixture verification is separate from test-case counts. All task-owned server processes shut down cleanly; the old owner/demo database was not used.

Representative independently expected negatives:

| Attempt | Expected and observed |
| --- | --- |
| Anonymous admin API; expired/revoked old admin bearer after restart | 401; no protected DTO or publication |
| Player admin draft/mutation, even with valid player CSRF | 403; no draft/publication mutation |
| Browser B exact A UUID: read/turn/preparation/result/report/replay; unrelated admin | Uniform404; no existence/owner/private-state details |
| Own replay + foreign predecessor | 404 before feedback records load |
| Missing/wrong/another-session CSRF; login/logout CSRF; old CSRF after rotation | 403; no domain mutation |
| Correct cookie/CSRF with wrong/null/missing Origin, cross-site or same-site Fetch Metadata | 403; no CORS reflection |
| Real Chrome request from another loopback origin/site | 403 ORIGIN_REJECTED logged; publications unchanged |
| Ten login attempts, fresh browser, process restart, eleventh attempt | 429; still player; succeeds only after budget window expires |
| Logout while password verification is in flight | Pending elevation401; no live admin session created |
| Duplicate turn request / stale revision / reused ID with different body | Identical saved response and one turn / 409 / 409 |
| GET/HEAD auth, session, catalog, health/readiness | No SQLite writes or lifetime extension |

G5/G6: both configured journeys reached unchanged own utility64 (S1) /47 (S2), prepared process100, exact saved-evidence keyboard links and immutable-version replay. Existing early-exit, poor-agreement44.12, grounded no-agreement70, insufficient observations, conditional concession, different-version comparison, lost response, stale tabs and all four S2 outcomes still pass. Refresh and actual production-process restart preserve a valid player's cookie-bound attempt. document.cookie cannot read the admin bearer; Set-Cookie attributes and absence from browser storage were verified. Simulated HTTPS injection verifies Secure/__Host/Strict/Path/no-Domain plus logout deletion; no public listener/TLS service was created.

Migration proof: fresh schema5; synthetic application migration2/3/4 fixtures upgrade with old record bytes and derived G6 reports preserved; copied accepted migration2 fixture upgrades2→5 with publication/session/turn digests unchanged and zero owners. Migrations1–4 remain byte-identical (migration1's original inline definition is checked separately). The prior legacy Chrome comparison test first proves404 after migration, then uses an explicit **test-only DB owner fixture** to retain the noncomparable-report rendering regression. No normal API can claim those legacy rows.

## Screenshots inspected

Synthetic application screens, no credentials/CSRF/cookies, all opened for visual review. Russian labels, accessible input labels, keyboard evidence focus and 360/390/1280 layouts remain usable. This is not a physical-device or full WCAG certification.

- [Login390](evidence/app-g8-access-boundary-01/g8-login-S1.png)
- [Foreign UUID denied360](evidence/app-g8-access-boundary-01/g8-foreign-uuid-S1.png)
- [Configured publication390](evidence/app-g8-access-boundary-01/g8-published-S2.png)
- [S1 process390](evidence/app-g8-access-boundary-01/g8-process-S1.png), [S2 process390](evidence/app-g8-access-boundary-01/g8-process-S2.png)
- [Expired administrator1280](evidence/app-g8-access-boundary-01/g8-expired-admin.png)

## Dependencies, configuration and launch

Added only `@fastify/cookie@11.1.2` and its nested `cookie@2.0.1`; all previously locked external entries/versions unchanged, no unrelated upgrade or npm ci. Install used the existing Node24 runtime and workspace-local cache. The official [Fastify cookie compatibility table](https://github.com/fastify/fastify-cookie#compatibility) specifies Fastify5 for plugin10+; its dependency cookie2 requires Node22+, compatible with actual24.21.0. Standard [Node scrypt and timingSafeEqual](https://nodejs.org/docs/latest-v24.x/api/crypto.html) implement password verification; no custom password hash or auth framework was added.

`ADMIN_PASSWORD_HASH` is optional only for the player path. Missing configuration disables admin login and shows a Russian configuration state. Invalid hash format fails startup without echo. Generate with `node scripts/admin-password.mjs` (hidden interactive input) and pass the output through deployment/local environment. `--stdin` is explicit for automation; never put a plaintext password argument/literal into shell history. No real password/hash is included in .env.example, this receipt or screenshots. Generator and owner launcher are verified with freshly random UTF-8/Russian test credentials, kept only in process memory. Administrative sessions survive restart only while the deployment hash is unchanged.

Already built owner worktree, PowerShell:

```powershell
Set-Location 'C:\Users\BastaPC\Desktop\Alag-app-work'
& 'C:\Users\BastaPC\Desktop\Alag\.tools\node-v24.21.0-win-x64\node.exe' .\scripts\local-demo.mjs
```

URL: http://127.0.0.1:3000/admin (default PORT3000). This asks for a hidden12–256-character password unless ADMIN_PASSWORD_HASH is already configured; no password/hash is printed or saved. The demo binds127.0.0.1 and defaults to `.tmp/owner-app-demo.sqlite`. Set the same hash in the environment or ignored .env for stable admin access between launches; a fresh prompt generates a fresh salted hash. No PowerShell policy, ACL, registry, firewall or permanent PATH changes. Standard `npm run build` / `npm start` also remain supported with explicit configuration. For Vite use APP_ORIGIN=http://127.0.0.1:5173.

## Protection, delivery and remaining limits

Before/after byte and metadata proof:346 original tracked files and369 untouched feature baseline files unchanged;31 training pins,20 accepted pins and8 shared authority pins verified in both checkouts. Frozen domain/scenarios/contracts, AI context/prompts/compiler, model/runtime/training locks, datasets/evals, planning documents/PDF and every prior receipt remain unchanged. No ML module was executed or example contents opened. No new read-boundary incident. The historical PARTIAL is preserved exactly as recorded, without reopening it or inferring training contamination.

Normal commit/push only to origin/feature/app-qwen-independent-01; no merge. The machine receipt records the implementation commit and the exact upstream/main verification. The receipt delivery commit cannot contain its own SHA; resolve it using `git log -1 --format=%H -- docs/gates/APP_G8_ACCESS_BOUNDARY_01.md`. Final HEAD/upstream equality,0/0 and clean feature state are checked after its normal push and reported to the owner. Remote main and original main must remain2034687f6f22b2973935f2c9c30bc9380c88b071.

Remaining limits: real TLS/HTTPS, proxy trust/termination, hosted persistence/backup, clean-machine/public-host and Linux smoke remain unverified. No public deployment, full G8/AI-failure certification or live AI verification. Single-node global login throttling can temporarily deny all admin logins; it is not distributed limiting or broad DoS protection. HttpOnly does not neutralize same-origin XSS or a compromised local computer. Local HTTP assumes a trusted loopback host. Credential/attempt recovery, session revocation UI beyond logout, transcript retention/deletion, expired-auth-row cleanup and broader abuse controls are separate work; historical records intentionally remain intact. Logs must not be retrofitted with raw request/header/body logging. No PUBLIC_DEPLOYMENT_READY claim.

One recommended next task: a separate Qwen-independent HTTPS/proxy and persistent-host reproducibility gate, with backup/restart and clean-machine smoke, before any public release.

**STOP — NO QWEN TRAINING, NO MODEL EVALUATION, NO PROVIDER CALLS, NO PUBLIC DEPLOYMENT, NO MERGE TO MAIN.**
