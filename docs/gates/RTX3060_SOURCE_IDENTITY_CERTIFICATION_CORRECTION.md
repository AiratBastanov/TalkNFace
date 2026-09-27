# RTX3060 source-identity certification correction

Verdict: **RTX3060_LEGACY_PROJECTION_CERTIFICATION_CORRECTION_PASS** (tooling correction, actual remote raw evidence and bounded owner validation). The real returned evidence passes the corrected verifier in the clean owner checkout with recomputed packaging provenance. The friend must still run PackageOnly to produce the final remote ZIP; no new hardware ZIP is claimed here.

**The GPU campaign was NOT rerun. Full training remains NOT STARTED.** No phase 00-04, CUDA/model/reload computation, dataset selection, evaluation, package installation, model/adapter modification or campaign-marker deletion was performed. Owner tests use CPU/stdlib fixtures, read-only real ZIP/raw inputs and PowerShell mocked dispatch. DEV / INTERNAL_TEST / tuning eval / A01-A16 were not evaluated or modified; Git source objects are used only for byte integrity checks.

Training source commit: `1c270adba77545720fa33bcee0e24f7d6f46e55d`.

Original result: `RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_RESULT.zip`, 60,659 bytes.

Original ZIP SHA256: `07D2ABFC00D188A469B1A18E6BC370C7040AA0E7A22F091FFC553ECFF68E2CBF`.

Canonical original evidence SHA256 (sorted keys, compact separators, ASCII JSON): `e8a2314894204b10ddadc5372fea4d34887f66842c9a8cd8413e9269c8d12906`.

Legacy-projection correction commit: **`a41776bf55a6e7c9c13aae7904d7c04f9bfcb882`**. It normally descends from `d356d10ddb26af39fd3f2102e63b6c1eed3581c2`, preserving the prior implementation commits `8712861a731e46a53f8c99ba86e7987cdea11631` and `8cab2c3aae1bdfdc87d1d9c68326c9564d629852`. This existing receipt is updated in a separate normal documentation commit so it can record the exact implementation hash without self-reference. Certification recomputes the ancestry proof through the actual packaging HEAD, including the receipt commit.

The first corrected/repackaged ZIP is 65,122 bytes, SHA256 `9C04661BD9959B8EB73015C36D479B5CACC5BF9CEAE90C412582DAB70B014FDA`.

The actual remote raw supplement is `RTX3060_LEGACY_RAW_CAMPAIGN_EVIDENCE.zip`, SHA256 `7FC6E17E924457E845C73D560AA7749B3830877B01F821609FE9B2FBC9F46B60`. Transport SHA256, exact entry coverage, CRC and all four file hashes were independently verified:

| Raw file | Bytes | SHA256 |
| --- | ---: | --- |
| `wheel-provenance.json` | 18,952 | `966a1308be3a6c29f750b58ed32c8210a3a1ae4b15c89dbde6c75bdc13846a7f` |
| `prepared-ready.json` | 1,270 | `ee3ce3b90c122e033b40d9d1fbc1b74ab99c8ae2b9da6450f9c306fe656ca63d` |
| `integrity-before.json` | 55,783 | `2b26fe3ca441cf13d61b34de3864e3f84f30ed7df9f028391b763c8cd29f0101` |
| `outcome.json` | 183,231 | `1375e39da1b86fdb0785e4a84a2204bbdd69ea9cbeff025d6db3ba8b62697607` |

All three input ZIPs remain unchanged and outside Git. Private raw records and machine paths are not committed. The supplement provides the actual raw wheel/preparation/outcome records and the byte-pinned pre-campaign snapshot; other diagnostic fields come unchanged from the existing result ZIPs. No model, adapter weights or dataset/example payloads were requested or opened.

The original ZIP was inspected without alteration. Archive integrity passed; its old evidence still returns `NOT_CERTIFIED`, `certified_training_pass: false`, and only `source_identity` in failed checks. Its reported hardware verdict is `RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_SMOKE_PASS`: two optimizer updates; boundary CUDA free 3933 and 1160.6484375 MiB; external minimum free 1002 MiB; return code 0; 144 adapter tensors changed; fresh-process reload, tensor equality and finite logits passed. No OOM or monitor stop was reported. These are observations of the original record, not new measurements.

The received raw preparation, pre-campaign and outcome Git records agree on the training commit, authoritative origin `https://github.com/AiratBastanov/TalkNFace.git` and clean state. The raw `integrity-before.json` bytes match the original prepared SHA256. No origin is reconstructed from `http<local-path>`. The remaining prepared files stay on the friend PC and remain subject to the existing PackageOnly hash checks.

The root cause was reproduced from the original implementation. In `package_result.scrub_text`, the unbounded drive-path expression `(?i)[a-z]:[\\/][^\r\n\"\']*` matches **`s://github.com/AiratBastanov/TalkNFace.git`** inside the HTTPS URL. Replacing that match leaves **`http<local-path>`**. The same defect erases wheel HTTPS URLs. This is a drive-letter match, not a UNC matcher. `control.assert_git_safe()` obtains and validates the raw origin through Git before packaging; its implementation is unchanged.

The second failure was reproduced on the delivered `d356d10` checkout: the first repackage passed archive integrity but failed only `source_identity`, and `collect_provenance()` raised `Completed campaign differs from the immutable original result` when given its already sanitized evidence. The proposed explanation that modern URL parsing shields all wheel URLs from the injected legacy scrubber was disproved by the actual code and evidence: **59 wheel URLs already reproject correctly**. The sole residual mismatch is the `hf-xet` URL.

The exact actual raw public URL, read from `wheel-provenance.json`, is:

```text
https://files.pythonhosted.org/packages/98/b7/8c59a66d15205024662f1d66968136f13893f96df1ddc5087e2e281fc95f/hf_xet-1.6.0-cp38-abi3-win_amd64.whl
```

It has no credentials, query or fragment. The modern token expression matches `hf_xet` in the filename and emits `<redacted-url>`. Historically, the broken drive regex ran first and consumed the HTTPS tail, producing `http<local-path>`. Applying the old scrubber to an already redacted marker cannot recover the historical output. No raw URL is inferred from either archive or substituted from a runtime lock.

Recursive ZIP comparison found **64 differing fields**: `schema_version`, the added `source_provenance` object (counted once), `prepared.git.origin`, `outcome.integrity.git.origin`, and `wheel_provenance.wheels_installed_this_setup[0..59].url`. After schema/provenance/origins are accounted for, 60 wheel URL differences remain; after the baseline legacy projection, only the hf-xet URL remains. The JSON receipt lists every path. All other training metrics, selection, model pins, adapter diagnostics, memory measurements, commits and campaign results are equal. Raw outcome differences are the expected eight private-path redactions and two omitted pip log fields. All supplied raw sections reproduce their original and modern ZIP sections exactly under the respective sanitizers.

The frozen `legacy_sanitize()` copies the original recursive key handling and string-transform order from the actual training Git blob `d023c6eb6868fe896441593ca261234d950c9475` (SHA256 `e3f64d99c476b80ca9f5da88a37864b8634fabb302c0528ef76b47153307730c`). Historical source is parsed/read, never dynamically executed. An AST regression checks the complete frozen behavior against that blob. Its secret/private/omitted key sets are independent of modern policy; legacy traversal previously shared the expanded modern secret-key set. The real raw supplement plus unchanged remaining archive diagnostics projects to **byte-identical canonical original evidence**, digest `e8a2314894204b10ddadc5372fea4d34887f66842c9a8cd8413e9269c8d12906`, with zero unexplained structural differences.

Modern `scrub_text`, `sanitize`, URL/token patterns and privacy key sets are **unchanged**, confirmed by an AST comparison with `d356d10`. Canonical GitHub, normal PyPI and PyTorch URLs survive; credentials, query/fragment secrets, private filesystem paths and structured secrets remain redacted. Private example payloads remain prohibited. Legacy-sanitized values never enter schema-3 output.

Raw packaging now requires **both** the frozen original digest and the independently verified modern campaign digest `d5ba0e4a5ab44d76b957abfa92e4795eb61ddee3594e37288dd6a712c737ecd7`. Both canonical campaign digests remove `source_provenance`, normalize `schema_version` to 2 and hash sorted-key compact ASCII JSON. Schema-3 verification compares its exact published campaign directly with that modern pin; it never attempts to invert redaction. This also rejects public wheel URL changes which the old lossy digest alone could hide. Provenance sub-schema 2 records both digests and recomputes all Git checks. The outer result schema remains 3.

The original owner fixture left `wheel_provenance` null, so Git-origin tests and synthetic archive round trips never exercised a wheel that modern sanitization redacts differently. The new always-available fixture includes the exact privacy-safe raw hf-xet row, and optional real-input regressions verify all three pinned ZIPs; all were present and ran in this validation.

The typed source verifier requires matching historical commit/origin/clean claims and the real clean `main` checkout with the authoritative fetch and push origins. Schema 3 records `training_source_commit` separately from `packaging_git.commit`. It validates the exact original before/after snapshot against historical Git blobs and model-lock pins, not against changed tooling at HEAD. All original training acceptance and archive integrity checks remain in force. Different origins, commits, dirty state, missing/malformed identity, contradictory provenance or altered campaign metrics fail.

Load-bearing proof was executed against the real repository, without mocking Git:

- All **319** historical tracked-file SHA256/size pairs match the Git blobs at the training commit. All **10** model pins match the unchanged lock: **329** snapshot entries, zero mismatches.
- Every intermediate commit must have exactly the previous commit as its single parent. Its changed paths must be a subset of the exact ten-file packaging/verifier/tests/documentation allowlist. Merges, unrelated additions and even reverted training edits fail.
- **313 protected paths** have identical Git objects, modes and sizes at training and correction commits. No training/model/data/configuration/selection/threshold/monitor/verdict source changed. All PowerShell entrypoints, `Remote.Common.ps1`, `control.py`, campaign admission and training/reload implementation are unchanged.
- Protected-tree digest: `e6bec130c1205e0cc8307c065714cee2e7eddb1972b40b3ba73f4eb71fbf8bcd`. Historical-tree digest: `c0f2cfe8a7c0b68e5c2515d0758e056b38662215e71c663fa1b8a51d7227348a`. These hash canonical JSON maps of path to Git object/mode/size; the JSON receipt includes the commit-by-commit proof and selected training SHA256 pins.
- Current file contents are also checked, catching `assume-unchanged`/`skip-worktree` concealment. Only the existing Git `text=auto eol=lf` policy's CRLF-to-LF conversion is accepted for index-classified LF text. Fourteen pre-existing owner worktree files have only that conversion; they were not edited. Binary files and historical campaign hashes never receive normalization. No external Git clean/smudge filter runs.

Changed files in this follow-up (the correction allowlist is unchanged):

- `tools/windows-rtx3060-12gb-1536/package_result.py`: independent, frozen schema-2 traversal; modern sanitizer unchanged.
- `tools/windows-rtx3060-12gb-1536/source_identity.py`: raw dual-projection binding and exact sanitized campaign verification; no URL reconstruction.
- `tools/windows-rtx3060-12gb-1536/test_source_identity.py`: real raw hf-xet, whole-evidence/AST regressions and archive preservation checks.
- This Markdown receipt and `docs/gates/evidence/RTX3060_SOURCE_IDENTITY_CERTIFICATION_CORRECTION.json`.

Validation: **94/94 tests passed, zero skips**: 60 source/privacy/packaging regressions (36.156 seconds), 23 existing workflow/archive regressions (0.734 seconds), 11 PowerShell regressions (12.328 seconds). Each group had a fixed 180-second watchdog. Wrong origins/commits, dirty state, load-bearing and reverted history changes, altered raw/archived metrics, original ZIP substitution, malformed archives, credentials and private payloads still fail. Two prior archive generations are preserved before replacement; identical packaging is reused. PackageOnly remains phase-05-only and the import guard forbids torch/transformers/peft/bitsandbytes. `git diff --check` passed.

After the implementation commit, the full verifier was run without mocking Git against an in-memory schema-3 view of the real returned campaign with recomputed current provenance. It returned `archive_integrity: PASS`, `training_gate: RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_SMOKE_PASS`, `certified_training_pass: true`, `failed_checks: []`. Both raw-projection and published-evidence branches agree. All 329 historical snapshot entries and 313 protected paths remain valid. This read-only owner validation creates no replacement hardware ZIP and performs no GPU or model work.

Remote action, in the friend's existing checkout with its original scratch and result ZIP:

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'git pull failed' }
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\windows-rtx3060-12gb-1536\RUN-RTX3060-12GB-REMOTE.ps1 -RepoRoot . -PackageOnly
```

PackageOnly dispatches only phase 05; the Python packager verifies its output. It performs no CUDA queries or model loads. It reads the original raw Git records and checks the frozen preparation hashes, original ZIP/legacy evidence digest and modern campaign digest. Missing or conflicting records stop certification rather than being repaired. All completed campaign JSON, selection, measurements, adapter and markers are preserved. Before replacement, the first corrected ZIP is copied to `.tmp/rtx3060-12gb-targeted-1536-smoke/packaged-history/<sha256>.zip`, checked and announced as `PRESERVED`; the original hardware ZIP remains preserved there from the preceding packaging. The original must exist at the standard result path or its history path. Repeated packaging safely reuses an identical archive and prints its SHA256.

Return the new `handoff-results/RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_RESULT.zip` and printed SHA256. Expected verification is archive `PASS`, original training verdict, and `certified_training_pass: true`. That remote outcome remains pending until the command runs. A failure does not authorize any training retry. Full training remains **NOT STARTED**.
