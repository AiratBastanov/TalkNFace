# Verdict

**G0_FOUNDATION_REPRODUCIBLE_RUNTIME_PASS_WITH_LINUX_PREREQUISITE**

Checked 2026-09-16. Final Windows G0 passes with better-sqlite3 **12.11.1** and the final frozen lockfile. Linux runtime is **NOT_VERIFIED**. This is not G0_FULL_PASS or full V12 certification. G1 is not started or authorized.

# Previous blocker

G0_BLOCKER_NODE24_RUNTIME: only system Node 22.20.0 / npm 10.9.3 was available. The previous attempt changed no files and installed no dependencies. The user separately authorized official portable Node24 inside the project and continuation of the same G0.

# Blocker resolution

| Item | Evidence |
|---|---|
| Official ZIP | https://nodejs.org/download/release/v24.21.0/node-v24.21.0-win-x64.zip |
| Official checksums | https://nodejs.org/download/release/v24.21.0/SHASUMS256.txt |
| Filename | node-v24.21.0-win-x64.zip |
| Downloaded size | 37,618,919 bytes |
| Expected SHA256, independently read from downloaded SHASUMS256 | 158f7685b44de51f6c0df1d153526cbcd3e1bc739a8dfc607721cef75de9e541 |
| Actual SHA256 of downloaded ZIP | 158f7685b44de51f6c0df1d153526cbcd3e1bc739a8dfc607721cef75de9e541 |
| Verification | **PASS**; also agrees with user-provided hash |
| Extraction directory | C:\Users\BastaPC\Desktop\Alag\.tools\node-v24.21.0-win-x64 |
| Explicit portable node.exe --version | **v24.21.0** |
| Explicit portable npm.cmd --version | **11.19.0** |

System curl failed before downloading SHASUMS (exit 35, Schannel SEC_E_NO_CREDENTIALS). Existing Git curl also uses Schannel. One concrete transport correction used the already-installed Node22 HTTPS fetch for **bootstrap download only**. TLS verification stayed enabled, redirects were rejected, both URLs were on nodejs.org, and one 120-second AbortSignal bounded the combined downloads. Both files downloaded and the ZIP hash matched in **1.953 seconds**, before extraction/execution. tar.exe extraction succeeded.

After bootstrap, **all project npm/node commands used portable Node 24.21.0**. System Node22 was subsequently invoked only for read-only version checks. No MSI, global runtime installation or version manager was used.

Runtime fencing: ignored .tools/run-npm.mjs asserts the exact version and invokes npm CLI with process.execPath (portable Node), prefixing PATH only in its child process. Important command logs record runtime/version/path. Root preinstall/build/typecheck/test/dev/start also check the Node24 major through scripts/check-runtime.mjs. README documents full-path portable npm.cmd and process-local PATH.

Stored ignored evidence: .tools/node-bootstrap-evidence.json, .tools/SHASUMS256-v24.21.0.txt, verified ZIP and extracted runtime. System where node continues to report D:\nodejs\node.exe; project execution does not rely on it.

# Environment

- OS: Windows kernel **10.0.26100**; platform **win32**, architecture **x64**.
- Actual gate Node: **24.21.0**, npm **11.19.0**, Node ABI **137**, N-API **10**.
- Executable: C:\Users\BastaPC\Desktop\Alag\.tools\node-v24.21.0-win-x64\node.exe.
- Existing system Node: D:\nodejs\node.exe, **22.20.0**, npm.cmd **10.9.3**.
- PowerShell blocks npm.ps1 by execution policy; npm.cmd/npm CLI were used without changing that policy.
- Initial inventory: original PDF plus three planning Markdown files. No prior application, dependency directories or root Git metadata.

Preflight and final SHA256 values agree:

| Unchanged file | SHA256 |
|---|---|
| Original PDF | FF50F0ADE59E2060818815284A8BE0CCD1F10065A0CE6F46F48B664E4DF0D75D |
| docs/00_REQUIREMENTS_AND_SCORING_MATRIX.md | DD380424D50900C4BB3B6550DC69654226BC89ECA45E8FFFFF9AC1435BF27460 |
| docs/01_PRODUCT_AND_ARCHITECTURE_DECISION.md | F3535762A93BE4FCA1322F8F8AB5AFC1BC980F3918EF4D5F9F55C1D03F25725D |
| docs/02_MASTER_IMPLEMENTATION_PLAN.md | D514CC920AC66749EAEDE4E443F589A1DFAA26C5F6AFB8F9D7498AF595B20E57 |
| D:\nodejs\node.exe | FDDDBF4581E046B8102815D56208D6A248950BB554570B81519A8A5DACFEE95D |
| D:\nodejs\npm.cmd | 21B46C69AD6E2F231F02A9E120F4BA6C8E75FEF5A45637103002EAB99F888AB8 |
| D:\nodejs\node_modules\npm\package.json | 972586791BD0E1ED4848ADDBB457889CDC5A45F4A3AFC5911B1CD233F0D87458 |

**SYSTEM_NODE22 = UNCHANGED**: these fingerprints, versions and the default PATH lookup were checked again. No write command targeted D:\nodejs. No permanent PATH, registry, global npm configuration, firewall or machine configuration change was made.

# Scope executed

G0 only: npm workspace, minimal React shell, Fastify construction/listen separation, same-origin static serving, health/readiness, four typed environment fields, SQLite connection/migrations/lifecycle, persistence tests, reproducible build/install, dev/start/smoke commands, README, ignores and this receipt.

No domain model, negotiation UI, scenarios, admin flow, AI integration, auth, CSRF, rate limiting, deployment, cloud resources or paid calls.

# Dependency versions

Direct dependencies are exact pins; transitive resolutions/integrities are frozen in one root package-lock.json. Runtime hint: .node-version = 24.21.0. engines accepts Node24 only; packageManager is npm@11.19.0.

| Package | Final version | Current G0 purpose |
|---|---|---|
| react | 19.3.0 | Minimal shell |
| react-dom | 19.3.0 | Browser rendering |
| vite | 8.3.0 | Dev and production SPA build |
| @vitejs/plugin-react | 6.1.1 | Official React integration |
| typescript | 7.0.2 | Strict typecheck/compile |
| fastify | 5.12.5 | HTTP application |
| @fastify/static | 10.1.3 | Production assets/SPA |
| zod | 4.6.5 | Server environment validation |
| better-sqlite3 | **12.11.1** | Verified compatibility fallback |
| vitest | 5.0.1 | Focused G0 tests |
| @types/node | 24.13.5 | Runtime-matched declarations |
| @types/react | 19.3.0 | React declarations |
| @types/react-dom | 19.3.0 | React DOM declarations |
| @types/better-sqlite3 | 9.6.0 | SQLite driver declarations |

Actual final SQLite: **3.53.2**. Private workspaces @arena/server, @arena/web, @arena/contracts are version 0.0.0. Contracts contain health/readiness declarations only, with no unused runtime JavaScript.

Registry metadata was fetched immediately before selection and the final tree verified by npm ls --depth=0, exit 0. No prerelease direct dependencies. Native Node TS execution avoids tsx; built-in child_process and Vite API avoid another process-runner package.

Final lock SHA256 before/after successful npm ci:
**785ACC78667D7E740865963BF1CAB5B02C89DA441841FA352F7868A4C2C0FDED**.

# External compatibility evidence

All sources checked **2026-09-16**. Upstream evidence supports selection; it does not replace actual runtime execution.

| Official source | Relevance |
|---|---|
| [Node 24.21.0 release](https://nodejs.org/en/blog/release/v24.21.0) | Official LTS release dated 2026-09-08; archive/checksums independently verified above |
| [npm registry](https://registry.npmjs.org/) | Each package's latest metadata, engines, peers and dist were queried; full lists selected Node24 declarations and the latest stable v12 driver |
| [Vite guide](https://vite.dev/guide/) | Runtime floor 20.19 / 22.12; Node24 satisfies Vite 8.3.0 and React plugin 6.1.1 registry engines |
| [Official react-ts template](https://github.com/vitejs/vite/blob/main/packages/create-vite/template-react-ts/package.json) | React19/Vite8 structure; template snapshot still uses earlier React/TS minors, so final stable 19.3.0/7.0.2 were verified independently by peers/typecheck/build |
| [Fastify 5.x CI](https://raw.githubusercontent.com/fastify/fastify/5.x/.github/workflows/ci.yml) | Node24 explicitly included with Windows/Ubuntu/macOS |
| [fastify-static compatibility](https://github.com/fastify/fastify-static#compatibility) | Plugin >=8.x supports Fastify5; final 10.1.3/5.12.5 actually tested |
| [Zod requirements](https://zod.dev/#requirements) | Strict mode, TypeScript >=5.5; final combination passes strict checks |
| [TypeScript docs](https://www.typescriptlang.org/docs/) | NodeNext/type-only imports; registry verifies stable 7.0.2 engines, and actual compilation verifies the chosen config |
| [Vitest guide](https://vitest.dev/guide/) | Registry 5.0.1 engines include Node24 and peers include Vite8 |
| [better-sqlite3 13.0.3 package](https://raw.githubusercontent.com/WiseLibs/better-sqlite3/v13.0.3/package.json) | Node >=22, bundled prebuilds and gypfile=false; actual initial load passed, clean ci did not |
| [13.0.3 build workflow](https://raw.githubusercontent.com/WiseLibs/better-sqlite3/v13.0.3/.github/workflows/build.yml) | Windows/Linux x64 prebuild targets and Node24 CI |
| [12.11.1 package](https://raw.githubusercontent.com/WiseLibs/better-sqlite3/v12.11.1/package.json) | Non-deprecated stable v12 release; engines explicitly include 24.x; compatible synchronous G0 API |
| [12.11.1 workflow](https://raw.githubusercontent.com/WiseLibs/better-sqlite3/v12.11.1/.github/workflows/build.yml) | Node24 Windows/Linux build/test targets |
| [Official v12.11.1 release assets](https://api.github.com/repos/WiseLibs/better-sqlite3/releases/tags/v12.11.1) | Exact node-v137 Windows/Linux x64 prebuilds and SHA256 digests |
| [Render disks](https://render.com/docs/disks) | Runtime-only, paid, single-instance persistent storage; ordinary service filesystem is insufficient |

Registry/asset snapshots are retained under ignored .tools/dependency-evidence.json and .tools/sqlite-v12-prebuild-evidence.json. Registry snapshot records initial latest 13.0.3; the final fallback selection is documented here and in the lockfile.

# better-sqlite3 compatibility decision

1. **Stable 13.0.3 attempted first.** Initial install succeeded and loaded node_modules/better-sqlite3/prebuilds/win32-x64.node under Node24/ABI137. SQLite 3.53.4 worked, 22 tests and production restart smoke passed. No node-gyp ran on the first install.
2. **Clean ci failed.** After removing the owned root node_modules, npm ci with the unchanged initial lock invoked a synthesized node-gyp rebuild for 13.0.3. node-gyp 12.4.0 actually ran and failed at header-cache creation with EPERM (...\AppData\Local\node-gyp). Existing Python was discovered automatically; no Python/VS/build tool installation or repair occurred. No unchanged native-build retry was made. The precise npm internal cause is **not claimed proven**; official package metadata has gypfile=false and no explicit install script.
3. **One authorized version correction: 12.11.1.** Registry identified it as the latest non-deprecated stable v12, not an arbitrary old version. Official engines and release assets explicitly cover Node24 Windows/Linux x64. No SQLite architecture or application API change was required.
4. **Fallback install and clean ci both passed with prebuilt.** The printed lifecycle command contains "prebuild-install || node-gyp rebuild --release", but only the first branch ran: neither v12 log contains node-gyp execution diagnostics. Cached Windows prebuild archive hash matches the official asset digest:
   **4ee5e653174d6ddd301605d351798cdae2613da06c4f37ecdce263021fcf1255**.
5. Final loaded binary: apps/server/node_modules/better-sqlite3/build/Release/better_sqlite3.node; SQLite **3.53.2**. This workspace-local npm placement is valid and used by actual source and compiled DB modules.

**prebuilt = YES; fallback = 12.11.1; node-gyp invoked during this gate = YES (rejected v13 ci), final v12 install/ci = NO.**

Maintenance limitation: v12's prebuild-install@7.1.3 is deprecated. That advisory, its fs.R_OK warning and npm's allowScripts advisory are retained in logs; install/load succeeded. Keep the compatibility pin until a separately verified newer driver passes clean ci. No machine toolchain is required for the verified path.

# Files created/modified

36 G0 text/placeholder files, including this receipt. Existing four source assets were preserved.

- Root: package.json, package-lock.json, .node-version, tsconfig.base.json, vitest.config.ts, .gitignore, .env.example, README.md.
- apps/web: package.json, tsconfig.json, vite.config.ts, index.html, src/main.tsx, src/style.css.
- apps/server: package.json, tsconfig.json, tsconfig.build.json; src/{app,database,env,main,paths}.ts; test/{app,database,env,static}.test.ts and test/helpers.ts.
- packages/contracts: package.json, tsconfig.json, src/index.d.ts.
- scripts: check-runtime.mjs, dev.mjs, start.mjs, smoke-production.mjs.
- data/.gitkeep.
- docs/gates/G0_FOUNDATION_REPRODUCIBLE_RUNTIME.md.

Generated/ignored: .tools portable runtime/checksums/cache/evidence/validation helpers/logs, root/workspace node_modules, apps/server/dist, apps/web/dist and Vite cache. Temporary .tmp databases and isolated Git audit metadata were removed. Root Git metadata were not created. No real .env exists; data contains only .gitkeep.

# Runtime architecture

Development runs Vite and a native-TypeScript Fastify entry. Frontend hot updates work; backend changes require a dev restart. Vite proxies health/readiness to the configured backend. No CORS integration.

Production: npm start → node scripts/start.mjs → compiled apps/server/dist/main.js, **one application Node process**. Fastify serves SPA/assets and API on one port. buildApp constructs an injectable app without listening. startServer owns listen and graceful signal/IPC shutdown.

Only NODE_ENV, HOST, PORT and DATABASE_PATH are validated. Zod returns a numeric port; relative database paths resolve against repository root independently of cwd. Invalid field names are reported without echoing values. No AI fields. npm start forces production even if local .env says development.

Health is process liveness; readiness executes a real foundation_metadata query and returns 503 on SQLite failure. HTML fallback accepts GET/HEAD navigation only, excludes reserved paths, and never replaces unknown API routes or missing assets with SPA HTML.

# SQLite implementation

Real file connection and parent-directory creation; foreign_keys=ON, busy_timeout=5000, journal_mode=WAL verified. Ordered migrations run in an immediate transaction before readiness. Only schema_migrations and foundation_metadata exist.

Migration 1 is recorded once; repeated startup retains data and the original migration record. An unknown newer schema fails without deleting metadata. No automatic reset or product tables.

Fastify onClose closes its owned database. SIGINT, SIGTERM and optional parent IPC use the same shutdown path, with a 10-second failure watchdog. Runtime smoke verifies clean exit and removal of WAL/SHM after final close. No active WAL copying or backup certification.

# Commands executed

All ran from project root. **NODE24** below means the exact portable executable recorded above. For rows starting "...", the command prefix is **NODE24 .tools/run-npm.mjs**. This runner executes the actual adjacent npm CLI. Bounded logs live in ignored .tools/logs.

| Important command / operation | Result | Bounded evidence |
|---|---|---|
| Inventory, G0 reread, Get-FileHash, system node/npm --version | 0 | Existing assets/runtime recorded |
| curl SHASUMS request, max-time 30 | 35 | Schannel failure before download |
| Bootstrap HTTPS fetch/hash, shared 120 s budget | 0 | Official digest match; 1.953 s |
| tar.exe -xf .tools/node-v24.21.0-win-x64.zip -C .tools | 0 | Verified extraction |
| Full-path portable node.exe/npm.cmd --version | 0 | v24.21.0 / 11.19.0 |
| Registry and official GitHub release-asset fetches, 30 s/request | 0 | Stable versions, engines, peers, exact assets |
| ... 180 install install --foreground-scripts --no-audit --no-fund | 0 | v13 initial install; 19.806 s |
| Initial real application DB/native probe | 0 | v13 Windows prebuilt, SQLite 3.53.4 |
| ... 120 typecheck-initial run typecheck | 1 | Zod pipe type mismatch; corrected explicit numeric transform |
| ... 120 typecheck run typecheck | 0 | All workspaces; 2.495 s |
| ... 180 build run build | 0 | Server JS + Vite assets; 1.985 s |
| ... 120 tests test | 0 | Initial 22/0; later corrected Fastify logging deprecation |
| ... 60 smoke-initial run smoke | 0 | Initial real production restart; 1.125 s |
| Verified-path Remove-Item of owned node_modules; ... 180 ci ci --foreground-scripts --no-audit --no-fund | 1 | v13 native regression; 4.103 s; no unchanged retry |
| Latest-v12 registry selection and official release asset inspection | 0 | v12.11.1 and both Node24 target assets |
| ... 180 install-v12 install --foreground-scripts --no-audit --no-fund | 0 | Authorized fallback prebuilt; 6.762 s |
| Native metadata probe assuming root hoisting | Diagnostic failure | DB opened; metadata resolution corrected to server workspace |
| Verified-path removal of owned node_modules; ... 180 ci-v12 ci --foreground-scripts --no-audit --no-fund | **0** | 158 packages; **3.958 s**; lock unchanged |
| Corrected native probe with server-based createRequire | **0** | 12.11.1, SQLite3.53.2, loaded binary/cache digest |
| ... 120 typecheck-final run typecheck | **0** | Final strict typecheck; **2.478 s** |
| ... 180 build-final run build | **0** | Final compiled server and SPA; **2.052 s** |
| ... 120 tests-final test | **0** | Final **22/0**, **2.043 s** |
| First interactive npm run dev smoke | HTTP pass; harness stop failed | Ctrl+C bytes did not become Windows control events; correction below |
| NODE24 .tools/smoke-command.mjs dev | **0** | Actual npm run dev, page/proxy endpoints and clean DB close |
| NODE24 .tools/smoke-command.mjs start | **0** | Actual npm start, production HTTP and clean DB close |
| ... 60 smoke-final run smoke | **0** | Final two production starts/stops, persistence; **1.099 s** |
| ... 60 dependency-tree ls --depth=0 | 0 | Final dependency pins/tree verified |
| Git check-ignore in disposable .tools audit repository | 0 | 12 intended ignore/retain cases |
| Source/config/secret/scope audit and hashes | PASS | 36 files, zero matches, one lock, originals/Node22 unchanged |

# Validation

| Criterion | Final result |
|---|---|
| Official portable Node24 hash/runtime | PASS |
| npm ci / frozen-lock reproducibility | PASS with final v12 driver |
| TypeScript | PASS, all workspaces, strict and skipLibCheck=false |
| Focused tests | **22 passed / 0 failed**, four files |
| Production build | PASS |
| Actual npm start and npm run dev | PASS |
| Same-origin SPA/JavaScript assets | PASS |
| /health | PASS, 200 minimal JSON |
| /ready | PASS, 200 healthy; DB failure test proves 503 |
| Migration / non-destructive second startup | PASS |
| File reopen sentinel | PASS, two reopenings retain value and migration record |
| Production restart sentinel | PASS, same file, new process PID |
| Graceful HTTP/SQLite shutdown | PASS, exit 0, database.closed, WAL/SHM gone |
| Startup without AI credentials | PASS, minimal constructed environment |
| Windows | PASS |
| Linux | NOT_VERIFIED |

Test inventory: environment 15, SQLite 3, Fastify lifecycle/readiness 2, real static build/missing-build handling 2. No negotiation or decorative snapshot tests. Suites were rerun after load-bearing driver/lock/logging changes, not in an unchanged expensive loop.

# Real application smoke

Final npm run smoke executed **compiled production output** using the exact scripts/start.mjs entry of npm start in two separate real Windows processes. Each used the same isolated .tmp/g0-production-*/runtime.sqlite, and a minimal environment without AI credentials or NODE_OPTIONS.

1. Start production Fastify after migrations.
2. GET / and the referenced built /assets/*.js: 200 HTML/JavaScript.
3. GET /health: 200 status=ok; GET /ready: 200 status=ready; unknown /api: JSON404.
4. Open the same file through the **compiled application DB module**, insert a random infrastructure sentinel, and close that inspection connection.
5. Parent IPC invokes the real shutdown handler; HTTP/SQLite close, process exits 0, WAL/SHM disappear.
6. Restart the same production entry and SQLite path, require a different PID, repeat HTTP checks.
7. Read the identical sentinel through the real DB module; schema_migrations still has only version1.
8. Close inspection DB, shut server down cleanly again, remove isolated temporary data.

Result: **starts=2, cleanShutdowns=2, persistedSentinel=true, orphanProcesses=0**. Actual npm start/dev command checks are additional evidence, not substitutes for this test.

# Windows result

**VERIFIED / PASS**, Node24.21.0 and final better-sqlite3 12.11.1. Official native prebuilt loaded without machine-level tools. Root commands work. No application server is intentionally left running.

Terminal limitation is explicit: tool-delivered Ctrl+C bytes did not generate OS console events. A test-only ignored stdin adapter emits SIGINT inside the real entry to exercise its existing handler; both actual npm commands then exit0 and close SQLite. The principal production restart smoke uses ordinary parent IPC with no adapter. Physical keyboard Ctrl+C and full browser/mobile automation are not claimed.

# Linux result

**TARGET_LINUX_RUNTIME_SMOKE = NOT_VERIFIED.**

Existing wsl.exe --list --quiet returned Wsl/EnumerateDistros/Service/E_ACCESSDENIED. Existing Docker CLI could not access a running docker_engine pipe. This does not establish whether a distribution is installed; no Linux runtime was accessible to this run. No WSL/Docker installation, service startup, administrative changes or cloud/CI resources were attempted.

Official exact fallback asset: better-sqlite3-v12.11.1-node-v137-linux-x64.tar.gz.
SHA256: **99c43785639d5d3690c396ba245ee680ac8b469a46b19233a3546f0eb7f8e312**.
Its presence and CI matrix are upstream evidence only, not Linux execution.

# AI status

**AI_PROVIDER_ACCESS = UNCONFIRMED. AI integration NOT STARTED.**

No key requested; no AI env fields, SDK, prompts, provider code or AI calls. Minimal-environment production smoke starts without credentials. Source and lockfile audit found no AI SDK.

# Hosting status

**HOSTING_ACCESS = UNCONFIRMED. Deployment NOT STARTED.**

Read-only official documentation check only. Public SQLite requires persistent mounted storage and a single application instance, with DATABASE_PATH set at runtime. Ephemeral service storage is insufficient. No account, disk, web service, paid resource or deployment created. Deployment remains G10.

# Findings / corrections

- Schannel download issue: one concrete switch to existing Node HTTPS for bootstrap only; no TLS bypass.
- Zod port typing: replaced mismatched coercion pipe with explicit string-to-number transform; no any escape hatch.
- Fastify deprecated top-level logging option: replaced by documented LogController API; affected checks repeated.
- Initial driver load did not count as reproducibility: failed v13 ci preserved, one authorized latest-v12 correction passed clean ci and all affected checks.
- A metadata diagnostic assumed root-hoisted driver placement; corrected createRequire to the server workspace. Application imports already resolved correctly.
- First dev CLI check returned correct HTTP but ignored tool Ctrl+C. Its 60-second watchdog attempted taskkill, which did not stop the tree in this tool session; recorded lifetime was 110.580 seconds. Only known G0 server PID9380 was then terminated via Stop-Process, its parent exited, and temporary data were cleaned. No timeout was inflated and no unrelated process was killed. A concrete stdin/SIGINT adapter correction made repeated bounded command checks pass in about one second. Principal production smoke always stayed within its 60-second budget.
- Disposable audit transport fixes: PowerShell stdin lost a Cyrillic regex, and Git stdin retained CR; ASCII HTTP probe / explicit Git arguments fixed the checks. Product files are UTF-8 and production HTML checks passed.
- Documentation patch application was corrected after duplicate operations on one file were rejected; frozen documents were never targeted.
- No architecture rewrite, global install, system repair or G1 compensation.

# Scope audit

**G0 only = CONFIRMED.** Created source/config/receipt text was scanned for accidental API keys, tokens, passwords and private-key content; no findings. Application sources contain no domain contracts/product tables. Lockfile has no AI SDK. No real .env exists.

Exactly one authoritative project package-lock.json, at root; ignored npm/vendor internal lock metadata do not define the application. Git ignore was verified against 12 cases: .tools, dependencies, builds, env, SQLite/WAL/SHM, temporary artifacts ignored; .env.example, planning documents and data/.gitkeep retained.

Four original asset hashes and three Node22 fingerprints match preflight. No permanent PATH/registry/global npm change, cloud resource, paid call or deployment. Only project-local implementation/evidence/cache files were intentionally written.

# Remaining prerequisites

- **Actual Linux Node24 install/build/native-driver/runtime smoke using the final lock** before Linux certification; carry this forward, and do not mark V12 fully complete.
- Browser/mobile verification, backup/restore, AI access and public hosting are later-gate work, not implemented or certified G0 capabilities. The v12 prebuild download-helper maintenance warning is documented above.

# Gate conclusion

The original Node24 blocker is **RESOLVED** without changing system Node22. All final Windows G0 acceptance checks pass with an officially verified portable runtime and a reproducible driver fallback. Linux runtime verification remains the explicit prerequisite.

**STOP — G1 NOT STARTED.**
