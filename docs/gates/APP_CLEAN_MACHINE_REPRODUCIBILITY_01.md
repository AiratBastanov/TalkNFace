# APP_CLEAN_MACHINE_REPRODUCIBILITY_01

Status: implementation and verification in progress; no PASS is asserted by this intermediate source commit.

Baseline `13f2fda624eb15725849445d4ddcd5d786ab02ab`, branch `feature/app-qwen-independent-01`, authoritative origin `https://github.com/AiratBastanov/TalkNFace.git`, upstream equal and initially clean. G5 implementation `da27e5571209824b77f08a4e421305f576bb1a18`, G6 `00e90a19527ab2b74986e542cebf40378059faf4`, G8 `dfaa7f2388d6ab7ab1af267a85e6f11bbf9cb5c0` are ancestors. Latest migration is 5; G8/app/domain behavior is unchanged.

Before implementation: actual package/lock/scripts/ignore/README/local demo inspected; five application workspaces, 215 lockfile entries, no external registry sources except npm, AI workspace excluded. Developer system Node is 22.20.0 and is not accepted by the new launcher. Previous documented owner shortcut used portable Node in the original checkout and `.tmp/owner-app-demo.sqlite`. Runtime scripts themselves contained no absolute owner path; existing start/dev loaded optional `.env`. These remain developer paths; Windows demo has independent deterministic config and data paths.

Original requirements PDF was consulted for the requested local/public launch alternative, working prototype, persistence across restart, six administrator settings, negotiation/feedback demonstration and reproducible documentation (PDF pp3–5, sections 2, 3.2, 4, 5). No additional product/AI requirements are inferred. Historical APP_AUDIT_AND_QWEN_INDEPENDENT_SLICE_01 remains PARTIAL, byte-identically; its recorded read-boundary incident is not erased, reopened or recast as proof of gradient-training contamination.

Protection captured before source edits: 346 original tracked files, 420 feature tracked files, 31 training pins, byte hashes/size/mtime only. Original checkout, local main and remote main all pin `2034687f6f22b2973935f2c9c30bc9380c88b071`. Protected example contents are not used. No training/model evaluation/GPU/provider calls/public deployment/merge are authorized by this gate.

Windows entry: `scripts/windows-demo.ps1`. Exact Node24.21.0 x64/npm11.19.0; official nodejs.org SHA256 verified. Local data `.local/arena-demo`, separate hash-only config `.local/arena-config/admin.json`. Named-pipe control identifies this checkout rather than trusting PID files. npm ci disables lifecycle hooks; only the pinned Windows SQLite prebuilt installer runs, with no Python/node-gyp fallback. Production build and source fingerprints must match before Start. SQLite backup API verifies integrity; stopped restore carries forward access revocation/expiry and preserves previous DB. No application auth hook, migration, score, ownership policy or cookie is weakened.

Predeclared validation budgets: Git120s, Node download300s/extract120s, npm ci+prebuilt300s, build300s, startup20s, focused regression180s, Chrome300s global/90s per case, backup/restore60s. Real authoritative-branch clean clone and source archive without `.git` are required before PASS. Unique cases and reruns will be recorded separately. A warm worktree bootstrap is development feedback only.

Final receipt will replace this status after clean-clone acceptance. The receipt is a subsequent normal commit so the exact tested implementation commit can be named without a self-referential SHA.
