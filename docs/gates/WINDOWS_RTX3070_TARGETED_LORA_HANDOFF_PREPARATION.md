# WINDOWS_RTX3070_TARGETED_LORA_HANDOFF_PREPARATION

**VERDICT: WINDOWS_RTX3070_TARGETED_LORA_HANDOFF_PREPARATION_PASS**

The portable manual Windows handoff is implemented and cheaply validated. **No Qwen3-4B training, inference, evaluation, local CUDA probe, package installation or model download occurred in this preparation.** No data/model was uploaded to the target and no cloud resource was provisioned. This PASS certifies the handoff, not RTX 3070 memory fit or quality.

The preceding targeted q/v-r8 gate was `LOCAL_QWEN_TARGETED_LORA_GPU_ENVIRONMENT_BLOCKED`: 5101 MiB nvidia-smi free versus historical 5396 MiB, before any model load. **q/v-r8 training remains untested**; it has not failed a memory campaign.

## Deliverable and manual workflow

The beginner-facing **Russian README** is [tools/windows-rtx3070/README.md](../../tools/windows-rtx3070/README.md). It covers checking NVIDIA, installing Git/Python manually if absent, reopening PowerShell, cloning/entering the repository, each phase, closing GPU-heavy apps, packaging, and manually returning only the ZIP. No Codex or Git write access is required.

| Script | Action |
|---|---|
| `00-preflight.ps1` | Read-only Windows x86-64 desktop, NVIDIA name/capacity/free/driver, RAM and repository-volume free-space checks |
| `01-setup-python-env.ps1` | Create the private venv with `py -3.12 -m venv`; exact binary/hash-pinned installation; pip receipts; tiny CUDA NF4 forward only |
| `02-download-and-verify-model.ps1` | Official immutable Qwen3-4B snapshot; verify all model/tokenizer/index pins; reuse a verified existing model |
| `03-prepare-smoke.ps1` | Reproduce frozen TRAIN IDs/order/lengths; complete JSON/EOS and prompt masks; no 4B load |
| `04-run-targeted-memory-smoke.ps1` | Fresh resources; one claimed campaign, eight microbatches/two updates; adapter-only save and fresh-process reload |
| `05-package-result.ps1` | Explicit allowlisted text/JSON diagnostics ZIP; no automatic upload or Git write operation |

All six scripts set strict mode and terminating error policy, resolve the root relative to their own files, print a phase, expose a read-only `-DryRun`, propagate nonzero native exit status and reject missing prerequisites. Windows PowerShell 5.1 argument quoting was exercised with spaces, embedded quotes, trailing backslashes and Cyrillic text. Child processes use hidden windows, bounded waits and termination restricted to descendants started by the gate.

Paths are relative to the clone: `.venv-qlora-remote`, `AlagModels/Qwen3-4B`, `.tmp/rtx3070-targeted-smoke`, `AlagModels/adapters/rtx3070-targeted-smoke/1024`, and `handoff-results/RTX3070_TARGETED_LORA_SMOKE_RESULT.zip`. No fixed username or original repository directory appears in the handoff. Existing raw datasets and historical adapters are not required on the friend's PC.

## Pinned environment and official sources

Python **3.12.10 x64**; torch **2.14.0+cu126**, Transformers **5.17.0**, bitsandbytes **0.50.2**, PEFT **0.21.0**, TRL **1.13.0**, accelerate **1.15.0**, datasets **5.0.1**, safetensors **0.8.0**, psutil **7.2.2**. All **61** packages, including transitive dependencies and pip, retain exact historical versions and wheel SHA-256 values. The ensurepip source is interpreter-relative, not an original-machine path.

Torch is installed in its own phase using only the [official CUDA 12.6 index](https://download.pytorch.org/whl/cu126/torch/), which lists the pinned CPython 3.12 Windows wheel. Other packages use [PyPI](https://pypi.org/simple). `--only-binary=:all:`, `--require-hashes`, `--no-deps`, explicit indexes and isolated pip configuration prevent source builds and unreviewed dependency resolution. No compiler, CUDA Toolkit or global packages are installed. The runner captures pip version/freeze/check, exact installed versions and verified wheel provenance. Official [pip installation options](https://pip.pypa.io/en/stable/cli/pip_install/) and pinned package metadata were checked; full URLs are in JSON evidence.

After setup, a separate target process verifies CUDA availability, runtime 12.6, GPU name, actual CUDA capacity and capability **8.6**. It checks the loaded NVIDIA bitsandbytes backend and executes a tiny **CUDA NF4/double-quant/FP16 forward** with finite output. It does no backward/update and loads no Qwen checkpoint. Driver failure stops with a manual NVIDIA driver action; it never recommends installing a toolkit as a routine fix. [Official bitsandbytes support](https://huggingface.co/docs/bitsandbytes/installation).

## Model identity

Source: [official Qwen/Qwen3-4B revision `1cfa9a7208912126459214e8b04321603b3df60c`](https://huggingface.co/Qwen/Qwen3-4B/tree/1cfa9a7208912126459214e8b04321603b3df60c). The downloader uses `snapshot_download`, `token=False`, exact `allow_patterns` and the immutable revision; no login or second package manager is needed. It never chooses GGUF, Base or another model size. [Official download API](https://huggingface.co/docs/huggingface_hub/guides/download).

The local byte-only validation passed all ten pinned files: three shards plus config, generation config, index, tokenizer JSON/config, vocabulary and merges. The index must reference exactly all three shards and the expected architecture is asserted. A matching model is reused without network transfer; any existing mismatching file fails closed without being overwritten.

```text
model-00001-of-00003.safetensors 328a91d3122359d5547f9d79521205bc0a46e1f79a792dfe650e99fc2d651223
model-00002-of-00003.safetensors 6cd087b316306a68c562436b5492edbcf6e16c6dba3a1308279caa5a58e21ca5
model-00003-of-00003.safetensors e4bf436957184f4eeb86a80e9db394503f1f56446b2e6b7edeac5b81470f4ca1
```

## Frozen architecture, data and memory policy

The architecture decision's `next_experiment` is the source for the exact 32 TRAIN IDs, their order/lengths, first eight optimizer IDs and unused reload row. The configuration retains explicit **q_proj/v_proj r8**, alpha 16, dropout .05, bias none and CAUSAL_LM, with **2,949,120 trainable parameters and 72 A + 72 B tensors** asserted before forward. NF4 double quant, FP16 compute, CUDA:0 base/adapters, paged_adamw_8bit, batch 1, accumulation 4, two updates, lr 2e-4, seeds 20260917 and completion-only supervision stay fixed.

The proven Transformers checkpoint activation offload to pinned host RAM is preserved with reentrant=True and every_n_layers=1. No second TRL offload manager, CPU model-weight placement, auto device map, rank/target/optimizer/quantization change or sequence-length retry is present. Cheap preparation uses the accepted compiler and real tokenizer/TRL collator, supervises full canonical JSON plus EOS, masks prompt/padding with -100 and excludes thinking content. It never truncates targets or loads 4B for tests.

Configured max length is **1024**; the selected maximum is **974** and first-eight maximum **962**. This does not establish the accepted TRAIN maximum **1421** or a **1536** envelope. Only eight TRAIN rows can provide gradients. No epoch, full 8000-row training, DEV, INTERNAL_TEST, tuning eval or A01–A16 evaluation is allowed.

Preconditions: 8192 MiB-class GPU (reported capacity ≥8000 MiB), capability 8.6, **≥12 GiB available RAM**, **≥30 GiB disk before model download**. Before the campaign require **≥7168 MiB nvidia-smi free**, **≥6656 MiB CUDA free**, and 5 GiB disk. The expected RTX 3070 name is recorded; OEM prefix differences are accepted. 32 GiB total RAM is recommended, not imposed as a new requirement.

The independent ~200 ms supervisor records host availability, process RSS/working set/private commit, native pagefile use, nvidia-smi used/free/utilization and optional per-process dedicated/shared counters. It stops its own worker if physical RAM falls below **6 GiB** or native pagefile growth exceeds **256 MiB**. The historical sampler is reused with explicit GPU-0 selection and this active pagefile stop. All original base weights remain on CUDA; host offload concerns checkpoint activations.

`PASS` requires every correctness/integrity/isolation/save/reload check, two finite non-skipped updates, changed adapter tensors, no OOM, peak allocated strictly below actual CUDA capacity and **≥512 MiB CUDA free at both optimizer boundaries**. **[256,512) MiB** yields `PASS_TIGHT_MEMORY`; **<256 MiB**, capacity overflow, OOM or host/pagefile pressure yields `MEMORY_FAIL`. Reserved memory is reported without equating it to physical residency.

The atomically created `campaign-started.json` survives failures/restarts and blocks another real campaign. Only a documented external GPU race **before any model load** can archive its unused reservation, preserving evidence and allowing a fresh precondition check. A started model load or any gradient work is never retried. Load/forward-backward/campaign/reload watchdogs are 300/600/1800/600 seconds. Native setup/download are separately bounded to 1800/3600 seconds. No timeout is inflated after failure and no user application is killed.

## Result package and failure handling

Expected archive: **`handoff-results/RTX3070_TARGETED_LORA_SMOKE_RESULT.zip`**. It contains concise `RESULT.txt`, machine-readable evidence, an archive SHA-256/size manifest and explicit metadata/log files: runtime, pip freeze/check, package provenance, model verification, frozen IDs, training/memory summaries, adapter metadata/hashes and diagnostics. The before/after model-hash status is reported separately; an unverified post-run hash is never shown as a passed final audit. Failure after completed updates preserves those metrics. If Python setup never worked, PowerShell can produce a minimal diagnostic ZIP.

The packager does not recursively archive the repo or scratch. It excludes weights, adapter binaries, all corpus/evaluation rows, raw datasets, venv and HF caches. It rejects example-content fields and redacts credential-like strings, URL queries and user paths. An existing result ZIP is not overwritten. Packaging waits for a live supervisor to exit; an interrupted dead supervisor yields a failure receipt. Nothing is uploaded automatically.

Remote verdicts are exactly: `RTX3070_TARGETED_LORA_MEMORY_SMOKE_PASS`, `...PASS_TIGHT_MEMORY`, `...GPU_ENVIRONMENT_BLOCKED`, `...RUNTIME_BLOCKED`, `...MODEL_INTEGRITY_FAIL`, `...MEMORY_FAIL`, or `...FAIL`. The friend sends the ZIP manually and needs no Codex or Git write permission.

## Local validation and protected state

**17 focused tests PASS in 10.946 seconds** under a 120-second test watchdog. Coverage: PowerShell parsing, all six dry runs relocated to a path with spaces/Cyrillic with no filesystem changes, native quoting and nonzero exit propagation, own-child watchdog, Python syntax, no fixed user paths, exact wheel locks, frozen selection/config/count formula, ten real model file hashes without loading, verified-model reuse/mismatch refusal, eval-open denial, atomic campaign marker, fixture-only supervisor lifecycle/resource block/post-run integrity failure, exact memory verdict boundaries, fixture ZIP contents/redaction and Git exclusions.

The tests found and corrected the PowerShell 5.1 fast-child ExitCode behavior and an inherited absolute ensurepip source path. Final failure-path review added preservation of completed metrics when the post-run integrity audit fails. Any PASS printed by a supervisor unit test is **fixture-only**, not a remote GPU result. No ML package or environment was created/installed locally and no CUDA or Qwen inference/training call ran.

**286 pre-existing files are byte-identical**, including model, corpus, external data, eval files, historical adapters/receipts/sources, application/contracts and planning. Both original environment inventories are unchanged. The only intentional pre-existing file edit is appending `handoff-results/` to `.gitignore`. `.venv*`, `.tmp`, AlagModels, AlagDatasets and result archives remain untracked. Separate supervisor hashes read protected bytes without parsing held-out examples. DEV/INTERNAL_TEST/tuning-eval/A01–A16 content exposure remains **0**. Python audit hooks cover Python IO; native model IO is additionally covered by hashes, not claimed to be an OS sandbox.

**REAL_APPLICATION_SMOKE = NOT_APPLICABLE_WITH_REASON:** remote R&D/training tooling only; application UI/API/product behavior is unchanged. No browser E2E or G3 was started. No registry, permanent PATH, global execution-policy, driver, pagefile, firewall, antivirus or TLS settings are changed by project scripts.

## Git delivery and next action

Initial `main` was clean at `813a356814080e18796e68ccdfb0b8bc3e19501e`; exact origin `https://github.com/AiratBastanov/TalkNFace.git` was fetched and ahead/behind verified **0/0** before writes. Delivery is limited to the new tools, this receipt/evidence and the result-folder ignore rule. Resolve the self-referential delivery commit with `git log -1 --format=%H -- docs/gates/WINDOWS_RTX3070_TARGETED_LORA_HANDOFF_PREPARATION.md`; normal push and final HEAD/origin/main/remote-main equality, clean status and 0/0 are verified after committing and reported to the user.

**Next:** the friend follows the Russian README manually, beginning with `nvidia-smi`. After a remote PASS, recommend only `RTX3070_TARGETED_LORA_1536_ENVELOPE_SMOKE`; after remote memory failure recommend only `QWEN3_4B_LARGER_GPU_TRAINING_ARCHITECTURE`. Neither gate nor full training is started by this preparation.

STOP — REMOTE RTX 3070 TRAINING SMOKE NOT STARTED.
