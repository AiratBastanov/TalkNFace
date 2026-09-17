# Qwen3 host RAM activation-offload correction

This bounded gate tests explicit checkpoint-activation storage in physical host RAM on the existing RTX 2060 / Windows machine. It runs at most two optimizer updates at 1024 and, only after an authorized GPU-memory failure, one two-update retry at 768. It never starts full training or evaluation.

Historical `ml/qlora_smoke`, its receipt/evidence, and its adapters remain immutable. New expanded data and telemetry live under ignored `.tmp/qlora-offload-smoke/`; adapter-only outputs live under ignored `AlagModels/adapters/qlora-offload-smoke/<limit>/`. Reuse `.venv-qlora-smoke` without installing or updating packages. Its exact dependency lock and wheel provenance remain in the previous gate.

Recorded outcome: `LOCAL_QWEN_QLORA_HOST_OFFLOAD_MEMORY_BLOCKED`. Explicit host checkpoint storage was verified, and allocated peaks fell to 5916.024 MiB at 1024 and 5621.174 MiB at 768. Both campaigns still reported zero CUDA free memory at both optimizer boundaries. Both completed two updates and passed adapter save/reload; no further configuration is authorized by this result. See the [receipt](../../docs/gates/LOCAL_QWEN_QLORA_HOST_RAM_OFFLOAD_CORRECTION.md) and [evidence](../../docs/gates/evidence/LOCAL_QWEN_QLORA_HOST_RAM_OFFLOAD_CORRECTION.json).

## Installed API and proof

Transformers 5.17.0 exposes `offload` as a **top-level** argument of `model.gradient_checkpointing_enable`. PEFT 0.21.0's `gradient_checkpointing_kwargs` are passed to the PyTorch checkpoint function. Consequently, this gate prepares/freeze/upcasts through PEFT with checkpoint enabling deferred, then calls:

```python
model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)
model.gradient_checkpointing_enable(
    offload=True,
    every_n_layers=1,
    gradient_checkpointing_kwargs={"use_reentrant": True},
)
```

LoRA is added afterward. Explicit `use_reentrant=True` preserves the historical run's effective PyTorch default; every decoder layer remains checkpointed. NF4 base weights, LoRA parameters, optimizer, SDPA attention and FP16 compute stay on CUDA:0. No device-map auto, weight/layer CPU offload, disk offload, alternative loss, model-size change, or distributed runtime is introduced.

The installed Transformers implementation wraps checkpointing in `torch.autograd.graph.save_on_cpu(pin_memory=True)`. `OffloadObserver` wraps its actual pack/unpack hooks and delegates copies unchanged. It records tensor shape/dtype/byte count, CPU destination, pinned allocation, restored CUDA device, and weak-reference live-byte accounting. It never reads activation values or saves model internals. The tiny random two-layer Qwen unit test proves the path before the 4B checkpoint is loaded; the real run must independently record positive pack/unpack counts and verified pinning across its 36 decoder layers.

Three mechanisms remain distinct: explicit activation offload is the new controlled policy; bitsandbytes paged optimizer is retained from the previous run; Windows WDDM oversubscription is not accepted as proof of GPU fit. Optional shared-memory counters can include intentional pinned-host storage and cannot independently attribute every byte to WDDM paging.

## Data and isolation

A separate supervisor reads the previous receipt solely for configuration, historical memory/timing comparison and selected TRAIN IDs. It materializes a TRAIN-only public context registry and an ID-only selection control in new scratch. The primary worker reconstructs the same 32 records plus the unused reload row from accepted TRAIN using the unchanged compiler. It verifies identical IDs, ordering and full token lengths. The first optimized row is 962 tokens; no easier primary sample is substituted.

The established canonical prompt/completion construction, non-thinking template, complete JSON/EOS supervision, explicit -100 prompt labels and TRL collator are preserved. All 32 masks are checked before model load; eight rows contribute gradients through microbatch 1 / accumulation 4 / two updates. There is no epoch or quality evaluation. The 768 fallback, if authorized, uses seeded coverage selection among complete eligible TRAIN rows. It records intents/tags that have no complete row within the limit instead of truncating targets. The observed 768 pool has 934 eligible rows and no eligible argument, close_attempt or counter_offer. This is a smoke-only restriction, not a policy for full-corpus training.

Worker audit hooks allow the current gate, its scratch/adapter roots, accepted TRAIN, the TRAIN-only context projection, fixed compiler helpers, required interpretation schema, and local model/tokenizer/runtime files. They refuse DEV, INTERNAL_TEST, tuning eval, A01–A16, raw datasets, historical scratch/adapters/receipts and protected writes. A separate byte-only auditor checks all previously protected artifacts, all pre-existing tracked files, historical adapters, pinned model shards and both environment inventories before/after. Python audit hooks are an accidental-access guard, not a native-code sandbox. File hashes independently establish byte integrity; they do not prove absence of native reads.

## Independent monitoring and safety

`monitor.py` runs outside the training process, sampling physical RAM, process RSS/working set/private commit and system pagefile use every 200 ms. A separate gate-owned `nvidia-smi --loop-ms=200` subprocess samples GPU memory/use without blocking the RAM loop. Standard Windows PDH English-name counters optionally track dedicated/shared GPU bytes for the actual Python worker PID. `EnumPageFilesW` measures real pagefile pages; process private/pagefile counters are explicitly labelled committed bytes, not disk paging.

At least 12 GiB physical RAM must be available before launch, model load and training. Below 6 GiB, the supervisor writes a cancellation request; the worker's daemon exits its own process, releasing CUDA resources. After a two-second grace period the supervisor may terminate only descendants of its own launcher. A focused test exercises this fallback against an owned dummy process with simulated pressure. No user process is terminated.

The fixed pagefile-growth acceptance ceiling is 256 MiB for this short gate, declared before training; larger growth cannot certify controlled physical-RAM offloading. Pagefile measurements are system-wide and cannot attribute unrelated application activity. Host sampling stops when the owned worker exits. Logs and raw telemetry are retained with hashes, not committed in bulk.

## Verdict and fallback

PASS requires two finite updates, changed adapter tensors, explicit host offload proof, save/reload, unchanged protected files, host RAM above the floor, no large pagefile growth, **peak allocated CUDA bytes below device capacity**, and **positive CUDA free memory at both optimizer boundaries**. Reserved bytes are recorded but are not compared to physical capacity as an independent failure condition.

At 1024, less than 256 MiB minimum step-boundary free memory yields PASS_TIGHT_MEMORY. A primary OOM, allocation reaching/exceeding physical capacity, or zero step-boundary free memory permits exactly one unchanged-settings 768 retry. Both memory failures yield HOST_OFFLOAD_MEMORY_BLOCKED. Host pressure, runtime incompatibility or another correctness failure is not a license to iterate configurations.

Only a comfortable 1024 pass can recommend `LOCAL_QWEN_QLORA_TRAINING_V1`. Tight memory calls for a bounded full-length envelope check. A 768 pass calls for a sequence-length strategy gate: long accepted TRAIN records must not be silently dropped. No next gate starts here.

## Execution order

Verify clean synchronized main and the specified origin first. `integrity.py before` writes the new frozen control files; run `pip check` and verify the existing versions. Then, from the repository root:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
.venv-qlora-smoke/Scripts/python.exe -B ml/qlora_offload_smoke/monitor.py prepare-1024 120 .venv-qlora-smoke/Scripts/python.exe -B ml/qlora_offload_smoke/prepare_smoke_data.py --max-length 1024
.venv-qlora-smoke/Scripts/python.exe -B ml/qlora_offload_smoke/monitor.py tests 120 .venv-qlora-smoke/Scripts/python.exe -B ml/qlora_offload_smoke/test_offload.py
.venv-qlora-smoke/Scripts/python.exe -B ml/qlora_offload_smoke/monitor.py HOST_OFFLOAD_1024 1800 .venv-qlora-smoke/Scripts/python.exe -B ml/qlora_offload_smoke/train_smoke.py --max-length 1024
.venv-qlora-smoke/Scripts/python.exe -B ml/qlora_offload_smoke/monitor.py reload-1024 600 .venv-qlora-smoke/Scripts/python.exe -B ml/qlora_offload_smoke/verify_adapter.py --max-length 1024
.venv-qlora-smoke/Scripts/python.exe -B ml/qlora_offload_smoke/integrity.py after
```

Inspect each result before continuing; reload only after successful training serialization and complete training-process exit. Commands refuse existing campaign logs/results. Model-load and individual forward/backward deadlines remain 300/600 seconds. Do not extend a watchdog or repeat an unchanged campaign. Preserve failures and use the 768 commands only when the primary's memory measurements authorize them.

Official references: [Transformers 5.17 checkpoint offload](https://huggingface.co/docs/transformers/v5.17.0/grad_checkpointing), [PEFT 0.21 preparation](https://huggingface.co/docs/peft/v0.21.0/en/package_reference/peft_model#peft.prepare_model_for_kbit_training), [PyTorch saved-tensor CPU storage](https://docs.pytorch.org/docs/2.14/autograd.html#torch.autograd.graph.save_on_cpu), [TRL activation offloading](https://huggingface.co/docs/trl/reducing_memory_usage#activation-offloading). TRL's separate full-forward offload manager is not additionally enabled in this controlled comparison.

STOP — FULL QLORA TRAINING NOT STARTED.
