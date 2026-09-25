# Windows desktop RTX 3060 12 GB / accepted 1536 experiment

Start with [START_HERE_RU.md](START_HERE_RU.md). The friend needs ordinary Windows PowerShell 5.1, Git, Python **3.12.10 x64**, and a working NVIDIA driver. Codex is not required. The external `01-materialize-rtx3060-12gb-gate.ps1` is obsolete; all implementation is tracked here.

`RUN-RTX3060-12GB-REMOTE.ps1` supports `-RepoRoot`, `-ModelArchive`, `-PrepareOnly`, `-PackageOnly`, and `-DryRun`. The script location determines the checkout; an explicit RepoRoot must agree. `-AllowModelDownload` is an explicit, bounded fallback. `-TransportSha256` overrides the transport pin for a separately verified TAR. Normally the adjacent `Qwen3-4B.tar.sha256` supplies it; without either, the historical transport pin is used. Model identity always comes from the unchanged model-lock.

| Phase | Work | Fixed budget |
|---|---|---|
| 00 | Read-only Git/Python/Windows/GPU/RAM/disk prerequisites | 180 s |
| 01 | Create or validate private venv; locked binary wheels, exact versions, pip check, tiny CUDA/NF4 forward | 1800 s overall; setup child 1600, backend 180 |
| 02 | Existing model verification, TAR inspection/staging/import, or explicit download | 1800 s overall; child 1780 |
| 03 | Integrity supervisor; all 8000 TRAIN records; completion labels/metadata checks | measurement 600 s; cheap worker 180; wrapper 1200 |
| 04 | Fresh admission, one bounded campaign, fresh-process reload, integrity | preflight 180; load 300; each forward/backward 600; training worker 1800; reload worker 600; wrapper 3000 |
| 05 | Sanitized diagnostics and exact ZIP manifest | 180 s |

The OS-held lock prevents concurrent operations. A durable reservation precedes model loading; a second worker entry and model-load marker are exclusive and flushed to disk. Missing markers alone never authorize a retry: ledger, traces, recorded/live workers and adapter state are reconciled. Positively observed prerequisite refusals may retry; executed or ambiguous attempts only report/package. Interrupted gate-owned setup/preparation may resume without deleting evidence. A valid unmarked venv may be checked and reused; an unknown invalid directory is never repaired. Repeated packaging preserves a previous, different ZIP under this gate's ignored `packaged-history`.

The only training experiment is the accepted NF4/double-quant/FP16, CUDA:0, SDPA, q/v-r8, alpha16/dropout0.05/bias-none configuration. It retains the original seeds, paged_adamw_8bit, learning rate, reentrant gradient checkpointing and explicit pinned-host activation offload. The exact runtime/model locks and requirements are copied byte-for-byte from the historical handoff. No CPU model-weight offload, BF16, allocator change, packing or truncation is introduced.

All 8000 TRAIN records must fit at 1536, with frozen observed maximum 1421. Sorting is `(-length,id)`: ranks 5–8 run first (`1396,1393,1391,1388`), ranks 1–4 second (`1421,1408,1406,1402`); rank 9 is unused TRAIN reload (`1387` complete record; the reload forward uses its prompt only). The schema remains `observed_max_length`. No executed 1536-token example is claimed.

`config.json` is the single hardware-policy definition consumed by PowerShell, Python admission, monitoring and verdict logic. Both physical and CUDA capacities must be >=12000 MiB; only the normalized desktop RTX 3060 identity and sm86 are admitted. Startup thresholds: nvidia-smi free >=10800 MiB, CUDA free >=10500 MiB, available physical host RAM >=12 GiB. Stop floor: 6 GiB host RAM; maximum observed pagefile growth: 256 MiB. Both optimizer-boundary CUDA-free measurements >=512 MiB are eligible for PASS; [256,512) is PASS_TIGHT_MEMORY; below 256, OOM or correctness/resource failure fails. No verdict starts full training.

External GPU telemetry, CUDA free, PyTorch allocated/reserved, Windows shared/dedicated GPU counters, physical host RAM and pagefile use remain distinct. A missing safety measurement prevents certification. A low shared-memory reading or return code zero is not a physical residency proof.

Workers use local files and explicit offline settings plus Python audit hooks. They cannot read DEV/INTERNAL_TEST/tuning-eval/A01–A16 contents; the separate supervisor performs byte-only integrity hashing. These hooks are not an OS security sandbox and do not intercept arbitrary native-library activity. Before/after source/model/data hashes and explicit audit records are required for certification.

The result ZIP contains only `RESULT.txt`, bounded sanitized `evidence.json`, and `archive-manifest.json`. Raw logs, dataset rows, prompts, token arrays, caches, secrets and model/adapter weights are excluded. `verify_result.py` separately checks ZIP integrity and all required training evidence; default exit 2 means training is not certified. `--archive-only` checks transport integrity and explicitly leaves training unchecked.

Owner regressions: `python -B tools/windows-rtx3060-12gb-1536/run_owner_tests.py` (180 seconds per group; no installs or ML execution). `owner_tokenizer_check.py` is an optional real tokenizer/compiler check using an already accepted environment, without weights, CUDA work or campaign readiness. The correction receipt distinguishes real owner checks from fixtures and remote execution.
