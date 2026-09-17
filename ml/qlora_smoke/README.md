# Local Qwen QLoRA feasibility smoke

Bounded Windows / RTX 2060 6 GiB R&D gate. This is a hardware/runtime/pipeline check, with exactly eight microbatches and two optimizer updates. It does not measure interpretation quality or authorize full training, evaluation, application integration, or G3.

The original `AlagModels/Qwen3-4B` is loaded locally with NF4 double quantization, FP16 compute, and explicit CUDA:0 placement. The source checkpoint is never converted or saved. PEFT prepares the quantized model and adds rank-8, alpha-16, dropout-0.05 all-linear LoRA adapters. All base parameters stay frozen. CPU model offload, BF16, automatic device mapping, packing, target truncation, and model merging are prohibited.

## Data and loss boundary

`prepare_smoke_data.py` reads only accepted `train.jsonl` examples and the public context registry, filtering the latter to TRAIN contexts. It calls the unchanged `compile_sft.py` representation. A fixed seed/hash ordering selects 32 complete examples, covering every intent and ambiguity, negation and injection tags. The first example is at least 900 tokens for the 1024 campaign (700 for the authorized 768 fallback). A distinct TRAIN row is reserved for reload. Measuring TRAIN lengths does not perform gradient updates on the corpus.

The original tokenizer is applied with `enable_thinking=False`. Full tokenization must preserve the exact generation-prompt prefix. Only canonical assistant JSON, its EOS, and trailing template whitespace receive labels. Any empty thinking prefix from the original non-thinking template belongs to the masked prompt. No reasoning content is supervised.

`SFTConfig(completion_only_loss=True)` records the requested configuration. Stable TRL 1.13's text collator consumes prebuilt labels; mask construction moved to dataset preparation. We supply explicitly verified `-100` prompt labels through that documented API. All 32 collated examples are checked before model load, and each training batch is checked again. The small explicit AMP loop avoids an epoch/eval scheduler and makes actual optimizer calls, scaler skips, gradient accumulation, and tensor mutation observable. This gate does not instantiate a full `SFTTrainer` campaign.

The first eight deterministically ordered rows receive one gradient update contribution each; the remaining subset rows establish preparation/coverage correctness. Two updates use microbatch 1, accumulation 4, learning rate 2e-4, checkpointing, FP16 AMP, and the official Transformers `paged_adamw_8bit` resolver. No loss-decrease or model-quality claim is made.

## Isolation and instrumentation

Workers install an audit hook before library/model/data loading. It refuses DEV, INTERNAL_TEST, A01–A16, tuning eval, raw datasets, prior gate receipts, baseline-environment reads, network connections, and writes outside this gate's scratch/adapter paths. These Python hooks are an accidental-access guard, not a native-code security sandbox; safetensors' native model reads are additionally protected by full before/after hashes. A separate hash auditor reads protected files as bytes only. No holdout contents reach a worker.

`integrity.py` checks pinned model shards, small files, accepted artifacts, raw data, all pre-existing tracked files, and baseline environment file inventory/stats. Cheap tests probe forbidden opens without reading their contents. Existing `.gitignore` rules cover `.venv-qlora-smoke`, `.tmp`, `AlagModels`, and `AlagDatasets`.

`preflight.py` proves the native CUDA DLL, uint8 NF4 storage, nested quantization, CUDA forward/backward, and a paged 8-bit optimizer mutation. Merely importing bitsandbytes cannot pass. Training records memory snapshots, CUDA peaks, process working-set peak, each microbatch loss, step times, finite gradients, actual optimizer-hook calls, scaler state, and changed adapter tensor hashes. A fresh process reloads the base and saved adapter, compares every adapter tensor hash, and performs one finite-logit forward on the unused TRAIN row. It does not score or generate a quality sample.

## Reproduction

First verify clean `main`, the specified origin, and local/remote 0/0; do not overwrite an existing run. Use installed Python 3.12.10. `setup_environment.py` creates a new private venv, checks official stable metadata, pins the core stack, and installs only binary wheels with a 300-second watchdog. `requirements.txt` and the gate evidence retain exact versions and wheel provenance. The baseline venv is never changed.

From the repository root, after the private environment exists:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
.venv-qlora-smoke/Scripts/python.exe -B ml/qlora_smoke/integrity.py before
.venv-qlora-smoke/Scripts/python.exe -B ml/qlora_smoke/run_bounded.py tests 120 .venv-qlora-smoke/Scripts/python.exe -B ml/qlora_smoke/test_qlora_smoke.py
.venv-qlora-smoke/Scripts/python.exe -B ml/qlora_smoke/run_bounded.py preflight 120 .venv-qlora-smoke/Scripts/python.exe -B ml/qlora_smoke/preflight.py
.venv-qlora-smoke/Scripts/python.exe -B ml/qlora_smoke/run_bounded.py prepare-1024 120 .venv-qlora-smoke/Scripts/python.exe -B ml/qlora_smoke/prepare_smoke_data.py --max-length 1024
.venv-qlora-smoke/Scripts/python.exe -B ml/qlora_smoke/run_bounded.py train-1024 1800 .venv-qlora-smoke/Scripts/python.exe -B ml/qlora_smoke/train_smoke.py --max-length 1024
.venv-qlora-smoke/Scripts/python.exe -B ml/qlora_smoke/run_bounded.py reload-1024 600 .venv-qlora-smoke/Scripts/python.exe -B ml/qlora_smoke/verify_adapter.py --max-length 1024
.venv-qlora-smoke/Scripts/python.exe -B ml/qlora_smoke/integrity.py after
```

Inspect each result before the next phase. Commands intentionally refuse existing logs/attempts. A watchdog terminates only the process tree it owns; model load and individual forward/backward operations also have 300/600-second worker deadlines. Preserve every failure. Only a CUDA OOM at 1024 authorizes one fresh 768 attempt with the same settings and newly selected complete examples. A second OOM blocks the gate. Never kill unrelated GPU processes or expand timeouts to repeat an unchanged campaign.

Adapter files live only under ignored `AlagModels/adapters/qlora-feasibility-smoke/<limit>/`. Expanded data and logs stay under ignored `.tmp/qlora-smoke/`. Full weights are never committed or published.

## Observed memory limitation

The 1024-limit campaign completed two updates and reload, but reached **6234.4541 MiB allocated / 6750 MiB reserved**, above the **6144 MiB physical GPU** (CUDA reports 6143.5625 MiB). Free CUDA memory reached zero. All model parameters were on CUDA and no CPU model offload was configured. Windows WDDM can permit allocations beyond dedicated VRAM; shared-memory residency during the peak was not measured. Process completion therefore does not establish the required GPU-resident memory envelope. `assess_result.py` records `LOCAL_QWEN_QLORA_FEASIBILITY_SMOKE_FAIL` for this unmet verification. This is not a claim that the CUDA kernels or adapters failed.

No CUDA OOM was raised, so the specifically authorized OOM-only 768 retry was **not** run. A separate bounded memory investigation would need to establish dedicated/shared residency before recommending full training. No quality or LoRA settings were changed after the successful two-update execution.

Official references: [bitsandbytes installation](https://huggingface.co/docs/bitsandbytes/installation), [PEFT quantization](https://huggingface.co/docs/peft/developer_guides/quantization), [TRL SFT](https://huggingface.co/docs/trl/sft_trainer), [Transformers bitsandbytes](https://huggingface.co/docs/transformers/quantization/bitsandbytes). Exact PyPI metadata and wheel URLs are recorded in the evidence.

STOP — FULL QLORA TRAINING NOT STARTED.
