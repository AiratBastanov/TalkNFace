# LOCAL_QWEN_TARGETED_LORA_MEMORY_SMOKE

**VERDICT: LOCAL_QWEN_TARGETED_LORA_GPU_ENVIRONMENT_BLOCKED**

Implemented and cheaply validated; **no Qwen3-4B model load or training campaign started**. The fair GPU environment precondition blocked execution. This is neither a targeted-LoRA memory PASS nor an executed memory FAIL.

## Why execution stopped

The frozen HOST_OFFLOAD_1024 start had **5396 MiB nvidia-smi free / 550 MiB used**. Current preflight measured **5101 MiB free / 845 MiB used**: **295 MiB less free**. The fair-start tolerance was fixed at 256 MiB before preflight. This deficit exceeds that tolerance and is larger than the entire minimum required training headroom.

CUDA reported **5103 MiB free**, exactly matching the historical CUDA start. That does not cancel the separate physical-memory occupancy evidence under WDDM. Physical capacity is 6144 MiB; CUDA capacity is 6143.5625 MiB. No allocator settings were changed.

The 5101 MiB nvidia-smi reading persisted through TRAIN preparation, both cheap-test runs and a subsequent read-only observation, with no 4B worker or model allocation. nvidia-smi listed only unrelated desktop/application GPU clients; WDDM does not expose their individual memory sizes there. No client was terminated. The lowest nvidia-smi reading during all preflight/cheap phases was **5027 MiB**, including the preflight CUDA context; this is not a training measurement. No favorable-start polling or second preflight was used to bypass the guard.

**ACTION REQUIRED FROM USER: close GPU-heavy applications and rerun the same gate.**

## Controlled implementation and cheap validation

The new bounded area is `ml/qwen_targeted_lora_memory_smoke/`. The configuration is loaded from `LOCAL_QWEN_QLORA_MEMORY_ARCHITECTURE_DECISION.json` → `next_experiment.configuration`; selection is projected from the same frozen object. Historical source, receipts and adapters remain untouched. Ignored scratch is `.tmp/qwen-targeted-lora-memory-smoke/`; the ignored adapter path is `AlagModels/adapters/qwen-targeted-lora-memory-smoke/1024/` and was not created.

Only the intended target list changes: **all-linear r8 → explicit q_proj/v_proj r8**. Rank 8, alpha 16, dropout 0.05, bias none and CAUSAL_LM stay fixed. Exact arithmetic and projection-only PEFT meta instantiation establish:

| Structure | Historical all-linear r8 | Configured q/v r8 |
|---|---:|---:|
| Trainable parameters | 16,515,072 | 2,949,120 |
| LoRA A tensors | 252 | 72 |
| LoRA B tensors | 252 | 72 |
| Raw FP32 adapter bytes | 66,060,288 | 11,796,480 |

Reduction: **13,565,952 parameters (82.142857%)**. q/v requires 36 q and 36 v targets. The real training worker asserts these counts before its first forward; that runtime assertion was not exercised because model loading was blocked. Static estimated weight/gradient/optimizer payload reduction is **129.7793 MiB**, not a measured peak-VRAM saving. No inference about actual fit is made.

All frozen settings remain: original local Qwen3-4B, NF4 double quantization, FP16 compute, CUDA:0, frozen base, SDPA, Transformers checkpoint activation offload, reentrant=True, all 36 checkpointed layers, paged_adamw_8bit, batch 1, accumulation 4, two updates, lr 2e-4, seed/data_seed 20260917, completion-only supervision, no packing/cache/BF16/TF32/evaluation/reporting. No model-weight CPU offload, TRL offload manager, allocator changes, cache optimization or retry configuration was introduced.

The installed method remains `gradient_checkpointing_enable(offload=True, every_n_layers=1, gradient_checkpointing_kwargs={"use_reentrant": True})` after PEFT preparation with checkpointing initially disabled. Its pinned-host implementation was verified historically and its installed signatures and configured call pass cheap tests here. Current 4B pack/restore counts are **not measured**. `offload.py` and the independent ~200 ms `monitor.py` match the historical helper bytes exactly.

**10 focused tests PASS.** They cover configuration/counts, metadata-only PEFT instantiation, frozen IDs/order/lengths, masks and padding, full JSON/EOS, no thinking supervision, prohibited opens denied before read, historical overwrite guards, ignored paths, offload call, host/GPU sampler and safety stop, and exact verdict thresholds. The initial suite detected newline conversion in copied helper files; exact bytes were restored and only the cheap suite was rerun. No training was repeated. The monitor pressure test terminates its own dummy child only.

## Runtime and prepared data

Python 3.12.10; torch 2.14.0+cu126; Transformers 5.17.0; bitsandbytes 0.50.2; PEFT 0.21.0; TRL 1.13.0; accelerate 1.15.0; datasets 5.0.1; safetensors 0.8.0. `pip check`: **No broken requirements found**. No install, upgrade, downgrade or environment mutation occurred. Device: RTX 2060 / sm75 / CUDA runtime 12.6; native BF16 unavailable.

Prepared **32 complete TRAIN rows plus the exact unused TRAIN reload row**. All IDs, order and token lengths match the decision evidence. The same first eight IDs are reserved for optimizer use, with lengths **962, 876, 689, 814, 856, 833, 932, 717**; none actually contributed gradients. The unused reload row is `ru-ec5a75935e736187`.

All 33 records pass real tokenizer/compiler and installed TRL collator checks: prompt labels -100, exact canonical JSON completion, supervised EOS, ignored padding, enable_thinking=false and no thinking content in supervision. No target was truncated. Expanded records remain ignored and are not included in evidence.

Configured max_length is **1024**, selected maximum **974**, planned optimizer maximum **962**. This preparation cannot prove that the accepted corpus maximum **1421** or a **1536-token envelope** fits.

## Training, memory and comparison

Actual optimizer updates **0**; microbatches **0**; losses/gradients/scaler skips/adapter mutation **not measured**. Model footprint, load duration, after-load/after-PEFT allocations, training peaks, both boundary-free readings and memory margin are **not measured**. Save/reload **not run**; no new adapter exists.

Host telemetry for preflight/preparation/cheap tests only: physical RAM **31.925 GiB**, available at preflight **20.841 GiB**, observed minimum available **20.768 GiB**. Process peak RSS **846.375 MiB**, working-set peak **850.629 MiB**. Actual native pagefile use was **26.055 MiB** before and at peak, delta **0 MiB**. These are not offloaded-training RAM figures.

The unchanged comparison is exclusively **HOST_OFFLOAD_1024**: peak allocated **5916.0244 MiB**, peak reserved **6734 MiB**, after-PEFT allocated **3359.8867 MiB**, boundary CUDA free **0 / 0 MiB**, nvidia-smi minimum free **92 MiB**, process peak working set **4126.8086 MiB**, step times **11.25 / 67.359 seconds**. It was not rerun. New-minus-old training allocation, RAM and timing differences are unavailable because this campaign did not execute. Reserved bytes are not equated with physical residency. No comparison against 768 is substituted.

## Isolation, integrity and product scope

Preparation accessed TRAIN and filtered TRAIN public contexts only, with the accepted compiler, system prompt, schema and tokenizer. Gradient rows **0**. DEV, INTERNAL_TEST, tuning eval and A01–A16 content exposure **0**. Negative access tests deny opens before any read. The supervisor's separate SHA-256 auditor reads protected files as bytes without parsing examples; raw external data was only byte-hashed by that auditor. Python audit guards are not an OS sandbox for arbitrary native IO; no native model loader ran here.

Before/after hashes verify **272 protected files unchanged**, including the three pinned model shards, accepted corpus, eval files, external datasets, existing adapters, completed receipts/sources, application/contracts and planning files. Both `.venv-ml` and `.venv-qlora-smoke` file/stat inventories also match. The complete hashes and phase audits are in the JSON evidence.

**REAL_APPLICATION_SMOKE = NOT_APPLICABLE_WITH_REASON.** This gate changes isolated R&D training infrastructure and defines an ignored adapter output path; it changes no production code, UI, API behavior or product capability. No browser E2E, G3, quality evaluation or full training was started.

## Next and STOP boundary

The next action is **the same LOCAL_QWEN_TARGETED_LORA_MEMORY_SMOKE after external GPU occupancy is reduced**, preserving this blocked receipt. Its one authorized training campaign has not been consumed. Do not turn this precondition block into a model-memory failure or claim a measured targeted-LoRA fit.

If a future execution passes every fixed criterion, recommend only `LOCAL_QWEN_TARGETED_LORA_1536_ENVELOPE_SMOKE`. If the executed campaign fails its envelope, recommend only `QWEN3_4B_REMOTE_TRAINING_ARCHITECTURE`. Neither is started here.

The fixed executed-campaign STOP boundary remains: OOM, peak allocated >= CUDA capacity, either optimizer boundary <256 MiB free, unsafe host/pagefile use, timeout, or correctness/save/reload/isolation/integrity failure ends this local path. No 768, rank-4, q/k/v/o, LoRA-FA, allocator/cache, optimizer, quantization or model-weight-offload retry. COMFORTABLE requires >=512 MiB at both boundaries; ACCEPTABLE requires >=256 MiB. Thresholds were not lowered.

## Git delivery

Initial main was clean at `a4249e76f8596f85aa9fd98be00dd1ad765b296d`; the exact requested origin was fetched and ahead/behind verified 0/0 before writes. Only the new source/tests/config/README and this receipt/evidence are delivered. Models, adapters, corpus, scratch and both environments remain ignored/untracked.

Resolve the self-referential delivery commit with `git log -1 --format=%H -- docs/gates/LOCAL_QWEN_TARGETED_LORA_MEMORY_SMOKE.md`. Normal push and final HEAD/origin/main/remote-main equality, ahead/behind 0/0 and clean status are checked after commit and reported in the final response; the JSON records this delivery procedure rather than inventing a future commit hash.

STOP — FULL QLORA TRAINING NOT STARTED.
