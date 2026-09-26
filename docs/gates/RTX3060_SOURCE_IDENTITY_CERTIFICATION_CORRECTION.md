# RTX3060 source-identity certification correction

Verdict: **RTX3060_SOURCE_IDENTITY_CERTIFICATION_CORRECTION_PASS** (tooling correction and bounded owner validation). Remote re-packaging/certification of the existing raw records is still required. This receipt does not claim that a corrected hardware ZIP has already been returned.

**The GPU campaign was NOT rerun. Full training remains NOT STARTED.** No phase 04 training, model/reload computation, dataset selection, evaluation, package installation, model/adapter modification or campaign-marker deletion was performed. Owner tests use CPU/stdlib fixtures and PowerShell dry-run/mocked dispatch. DEV / INTERNAL_TEST / tuning eval / A01-A16 were not evaluated or modified; Git source objects are used only for byte integrity checks.

Training source commit: `1c270adba77545720fa33bcee0e24f7d6f46e55d`.

Original result: `RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_RESULT.zip`, 60,659 bytes.

Original ZIP SHA256: `07D2ABFC00D188A469B1A18E6BC370C7040AA0E7A22F091FFC553ECFF68E2CBF`.

Canonical original evidence SHA256 (sorted keys, compact separators, ASCII JSON): `e8a2314894204b10ddadc5372fea4d34887f66842c9a8cd8413e9269c8d12906`.

Packaging/verifier correction commit: `8cab2c3aae1bdfdc87d1d9c68326c9564d629852`, following initial implementation commit `8712861a731e46a53f8c99ba86e7987cdea11631`. This receipt is a separate documentation commit, avoiding a self-referential commit hash. Certification recomputes the ancestry proof through the actual packaging HEAD, including this receipt commit.

The original ZIP was inspected without alteration. Archive integrity passed; its old evidence still returns `NOT_CERTIFIED`, `certified_training_pass: false`, and only `source_identity` in failed checks. Its reported hardware verdict is `RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_SMOKE_PASS`: two optimizer updates; boundary CUDA free 3933 and 1160.6484375 MiB; external minimum free 1002 MiB; return code 0; 144 adapter tensors changed; fresh-process reload, tensor equality and finite logits passed. No OOM or monitor stop was reported. These are observations of the original record, not new measurements.

The owner supplied the friend's independent post-run Git attestation: clean `main`, training HEAD above, authoritative origin `https://github.com/AiratBastanov/TalkNFace.git`, ahead/behind 0/0. The friend's raw scratch records are not available on the owner machine. The remote command checks those records directly; no origin is reconstructed from `http<local-path>`.

The root cause was reproduced from the original implementation. In `package_result.scrub_text`, the unbounded drive-path expression `(?i)[a-z]:[\\/][^\r\n\"\']*` matches **`s://github.com/AiratBastanov/TalkNFace.git`** inside the HTTPS URL. Replacing that match leaves **`http<local-path>`**. The same defect erases wheel HTTPS URLs. This is a drive-letter match, not a UNC matcher. `control.assert_git_safe()` obtains and validates the raw origin through Git before packaging; its implementation is unchanged.

The correction parses URL spans separately from filesystem paths. Canonical public HTTPS origin survives; userinfo (including username-only credentials), query/fragment URLs and non-HTTP schemes are redacted. Windows, UNC, home and POSIX paths, structured secrets, bearer/HF/GitHub tokens and secret assignments remain redacted. Private example payloads remain prohibited. A frozen legacy projection exists solely to bind the corrected diagnostic to the known original evidence digest; it never emits new evidence or supplies a successful identity.

The typed source verifier requires matching historical commit/origin/clean claims and the real clean `main` checkout with the authoritative fetch and push origins. Schema 3 records `training_source_commit` separately from `packaging_git.commit`. It validates the exact original before/after snapshot against historical Git blobs and model-lock pins, not against changed tooling at HEAD. All original training acceptance and archive integrity checks remain in force. Different origins, commits, dirty state, missing/malformed identity, contradictory provenance or altered campaign metrics fail.

Load-bearing proof was executed against the real repository, without mocking Git:

- All **319** historical tracked-file SHA256/size pairs match the Git blobs at the training commit. All **10** model pins match the unchanged lock: **329** snapshot entries, zero mismatches.
- Every intermediate commit must have exactly the previous commit as its single parent. Its changed paths must be a subset of the exact ten-file packaging/verifier/tests/documentation allowlist. Merges, unrelated additions and even reverted training edits fail.
- **313 protected paths** have identical Git objects, modes and sizes at training and correction commits. No training/model/data/configuration/selection/threshold/monitor/verdict source changed. All PowerShell entrypoints, `Remote.Common.ps1`, `control.py`, campaign admission and training/reload implementation are unchanged.
- Protected-tree digest: `e6bec130c1205e0cc8307c065714cee2e7eddb1972b40b3ba73f4eb71fbf8bcd`. Historical-tree digest: `c0f2cfe8a7c0b68e5c2515d0758e056b38662215e71c663fa1b8a51d7227348a`. These hash canonical JSON maps of path to Git object/mode/size; the JSON receipt includes the commit-by-commit proof and selected training SHA256 pins.
- Current file contents are also checked, catching `assume-unchanged`/`skip-worktree` concealment. Only the existing Git `text=auto eol=lf` policy's CRLF-to-LF conversion is accepted for index-classified LF text. Fourteen pre-existing owner worktree files have only that conversion; they were not edited. Binary files and historical campaign hashes never receive normalization. No external Git clean/smudge filter runs.

Changed files (relative to the repository):

- `tools/windows-rtx3060-12gb-1536/package_result.py`: structural redaction; immutable original binding; safe archive history; automatic verification/exit status.
- `tools/windows-rtx3060-12gb-1536/verify_result.py`: schema 3 and strict historical source verifier delegation; archive checks retained.
- `tools/windows-rtx3060-12gb-1536/source_identity.py`: typed Git identity, pinned original receipt, raw preparation checks, historical hashes, linear tooling-only ancestry and current checkout validation.
- `tools/windows-rtx3060-12gb-1536/test_source_identity.py`: 40 focused regressions with real temporary Git histories, synthetic evidence, and PowerShell PackageOnly dispatch.
- `tools/windows-rtx3060-12gb-1536/test_workflow_result.py`: replaces the obsolete mocked HEAD-only source test with the new real-history tests; existing archive/workflow tests retained.
- `tools/windows-rtx3060-12gb-1536/run_owner_tests.py`: includes the new bounded regression group.
- `tools/windows-rtx3060-12gb-1536/README.md` and `START_HERE_RU.md`: completed-campaign correction instructions and provenance contract.
- This Markdown receipt and `docs/gates/evidence/RTX3060_SOURCE_IDENTITY_CERTIFICATION_CORRECTION.json`.

Validation: **74/74 tests passed**: 40 source/privacy/packaging regressions, 23 existing workflow/archive regressions, 11 PowerShell regressions. Each group had a 180-second watchdog; final measured durations are in the JSON receipt. New cases cover HTTPS versus drive/UNC paths, credentials and secrets, correct and incorrect Git identities, dirty/missing/malformed evidence, history drift and reverted drift, original ZIP substitution, prepared-artifact mutation, archive preservation/reuse, no ML imports, PackageOnly phase-05-only dispatch and verification failure propagation. Existing duplicate/extra/missing-entry, hash/coverage, CRC/truncation and contradictory-evidence checks still pass. `git diff --check` passed.

Remote action, in the friend's existing checkout with its original scratch and result ZIP:

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'git pull failed' }
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\windows-rtx3060-12gb-1536\RUN-RTX3060-12GB-REMOTE.ps1 -RepoRoot . -PackageOnly
```

PackageOnly dispatches only phase 05; the Python packager now verifies its output. It performs no CUDA queries or model loads. It reads the original raw Git records and checks the frozen preparation hashes and original ZIP/evidence digest. Missing or conflicting records stop certification rather than being repaired. All completed campaign JSON, selection, measurements, adapter and markers are preserved. Before replacement, the old ZIP is copied to `.tmp/rtx3060-12gb-targeted-1536-smoke/packaged-history/<sha256>.zip`, checked and announced as `PRESERVED`. The original must exist at the standard result path or that history path. Repeated packaging safely reuses an identical archive and prints its SHA256.

Return the new `handoff-results/RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_RESULT.zip` and printed SHA256. Expected verification is archive `PASS`, original training verdict, and `certified_training_pass: true`. That remote outcome remains pending until the command runs. A failure does not authorize any training retry. Full training remains **NOT STARTED**.
