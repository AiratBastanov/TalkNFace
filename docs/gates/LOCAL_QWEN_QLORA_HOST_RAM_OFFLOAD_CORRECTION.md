# LOCAL_QWEN_QLORA_HOST_RAM_OFFLOAD_CORRECTION

**VERDICT: LOCAL_QWEN_QLORA_HOST_OFFLOAD_MEMORY_BLOCKED**

Explicit host activation storage worked and reduced peak CUDA allocation, but both authorized configurations reported zero CUDA free bytes at both update boundaries. Physical GPU headroom is not established.

The gate is complete as a measured blocker. Two optimizer updates, finite gradients, 504/504 changed adapter tensors, adapter save and fresh-process reload passed in each campaign. Neither campaign certifies the required local GPU envelope. No third configuration was attempted.

## Runtime and offload proof

Reused Python 3.12.10 / torch 2.14.0+cu126 / Transformers 5.17.0 / bitsandbytes 0.50.2 / PEFT 0.21.0 / TRL 1.13.0 / accelerate 1.15.0 / datasets 5.0.1 / safetensors 0.8.0. `pip check` passed; both environment inventories are unchanged. RTX 2060, sm75, CUDA 12.6, no native BF16.

Installed source/signatures select `prepare_model_for_kbit_training(..., use_gradient_checkpointing=False)` followed by `model.gradient_checkpointing_enable(offload=True, every_n_layers=1, gradient_checkpointing_kwargs={"use_reentrant": True})`, then LoRA. The top-level Transformers argument is required; passing nested `offload` through PEFT would target PyTorch checkpoint kwargs.

The installed `save_on_cpu(pin_memory=True)` hooks were instrumented without changing their copy policy. Each real campaign recorded 288 CUDA-to-pinned-CPU packs and 288 restorations to CUDA across 36 decoder layers and eight microbatches. CPU storage, pinning and restore devices passed independently of the configuration flag. The cheap two-layer random Qwen test proved the path before loading the 4B checkpoint.

Only activation checkpoint storage changed in the primary comparison. NF4 double-quantized weights and LoRA remain on CUDA:0, with FP16 compute, SDPA, r=8, alpha=16, dropout=0.05, all-linear targets, batch 1, accumulation 4, two paged_adamw_8bit updates, learning rate 2e-4 and seed 20260917. All 252 quantized modules were checked; 16,515,072 parameters were trainable and 4,022,468,096 base parameters frozen. No model-weight CPU offload or device_map auto was used.

## Measured memory and training

Physical GPU memory is 6144 MiB by nvidia-smi; the CUDA API reports 6143.5625 MiB capacity. All values below are measured; process peaks cover the complete worker lifetime.

| Measurement | HOST_OFFLOAD_1024 | HOST_OFFLOAD_768 |
|---|---:|---:|
| Initial nvidia-smi free, MiB | 5396.0 | 5418.0 |
| CUDA free before load, MiB | 5103.0 | 5103.0 |
| Peak CUDA allocated, MiB | 5916.024 | 5621.174 |
| Peak CUDA reserved, MiB | 6734.000 | 8118.000 |
| Minimum CUDA free at update boundaries, MiB | 0.0 | 0.0 |
| Minimum nvidia-smi free sampled, MiB | 92.0 | 66.0 |
| Host RAM total, GiB | 31.925 | 31.925 |
| Host available before / minimum, GiB | 21.184 / 16.899 | 21.192 / 16.261 |
| Process peak RSS / working set, MiB | 4116.621 / 4126.809 | 4835.531 / 4845.379 |
| Pagefile used before / peak / increase, MiB | 15.562 / 15.562 / 0.000 | 15.438 / 15.438 / 0.000 |
| Peak observed live offloaded activations, MiB | 338.203 | 268.594 |
| Losses (two accumulated updates) | 2.414761 / 1.415448 | 2.336438 / 1.781837 |
| Update wall times, seconds | 11.250 / 67.359 | 8.391 / 8.766 |
| Complete subset rows / rows contributing gradients | 32 / 8 | 32 / 8 |
| Actual optimizer updates / scaler skips | 2 / 0 | 2 / 0 |
| NaN/Inf | None | None |
| Adapter tensors changed / save / reload | 504/504 / PASS / PASS | 504/504 / PASS / PASS |

Peak allocated fits below physical capacity in both runs, but zero CUDA free bytes at both step boundaries fails the mandatory headroom requirement. Reserved bytes are not independently used as the rejection criterion. nvidia-smi and CUDA free counters disagree; positive dedicated free does not replace the required CUDA measurement. Optional per-process dedicated/shared PDH measurements are retained in JSON. Shared bytes can include intentional pinned-host memory, so they do not identify all WDDM paging.

The independent 200 ms supervisor observed no real host-RAM safety stop, no pagefile growth and no terminated user process. The 12 GiB start requirement and 6 GiB floor held. Unit tests separately simulated low RAM and terminated only an owned dummy process. All watchdogs remained unchanged: tests 120 s, load 300 s, forward/backward 600 s, campaign 1800 s and reload 600 s.

## Comparison with frozen no-offload evidence

Historical allocated/reserved peaks were 6234.4541 / 6750 MiB; process peak was 3257.3711 MiB; update times were 33.172 / 46.656 s. The historical experiment was not rerun.

| Difference from historical run | 1024 | 768 |
|---|---:|---:|
| CUDA peak reduction, MiB / percent | 318.430 / 5.11% | 613.280 / 9.84% |
| Process peak working-set increase, MiB | 869.438 | 1588.008 |
| Aggregate two-update time ratio | 0.985x | 0.215x |

The 1024 aggregate showed no measured slowdown, although its second update took longer. The 768 result also changes sequence lengths and rows, so it cannot isolate the effect of offloading. These tiny-run timings do not predict full-training speed. Minimum proven step-boundary CUDA headroom remains zero for both.

## Data, tests and integrity

The 1024 subset reuses all 32 historical IDs, their order and full lengths (689–974 tokens); its first optimized row is 962 tokens. The 768 pool contains 934 complete eligible TRAIN examples; selection is seeded and records 32 IDs with lengths 663–767. Three intents have no eligible complete example: argument, close_attempt and counter_offer. The first fallback preparation stopped on that coverage constraint before any 768 model load. A focused selector correction permits coverage of eligible intents and explicitly records omissions; it never shortens JSON. There was exactly one 768 training campaign.

Canonical JSON plus EOS are fully supervised; all system/user prompt tokens are -100. enable_thinking=false is preserved and no thinking content is supervised. All masks were checked before model load. Reloads used separate unused TRAIN rows and finite-logit forward passes, with zero generated tokens and no quality assessment. Selected/optimized/reload IDs and adapter config/file sizes/SHA-256 are in the JSON evidence.

Fourteen cheap tests passed before the 4B run; the added fallback regression and final 15-test suite passed. Tests cover the installed API, actual tiny-Qwen offload, deterministic complete-row selection, completion masks, blocked evaluation opens, RAM sampling/floor/owned-process stop, historical parsing, verdicts and ignored outputs. No unit test loads Qwen3-4B.

All 216 protected file hashes and both environment inventories are unchanged. This includes original pinned model shards, accepted corpus, raw datasets, evaluation files, application/planning sources, historical gate source/evidence and historical adapter. Hashing is performed by a separate byte-only auditor. Worker exposure: DEV=0, INTERNAL_TEST=0, tuning eval=0, A01–A16=0. Python audit hooks are not a native-code security sandbox; file hashes prove integrity rather than absence of arbitrary native reads.

## Delivery and next decision

Source delivery: `28c933d21675968bd6159b4fb9393f4e86af4609`; normal origin/main push and 0/0 synchronization are recorded in JSON. This receipt follows in its own normal commit; use `git log -- docs/gates/LOCAL_QWEN_QLORA_HOST_RAM_OFFLOAD_CORRECTION.md` to resolve its self-referential delivery hash. Model/adapter binaries, venv and scratch remain ignored.

Recommend **LOCAL_QWEN_QLORA_MEMORY_ARCHITECTURE_DECISION** only: make a separate bounded decision on memory policy/placement before authorizing another training experiment. No full V1 recommendation, model-weight offload implementation, extra configuration, evaluation or G3 integration was started.

Official API references: [Transformers 5.17 checkpoint offload](https://huggingface.co/docs/transformers/v5.17.0/grad_checkpointing), [PEFT 0.21 preparation](https://huggingface.co/docs/peft/v0.21.0/en/package_reference/peft_model#peft.prepare_model_for_kbit_training), [PyTorch saved-tensor CPU storage](https://docs.pytorch.org/docs/2.14/autograd.html#torch.autograd.graph.save_on_cpu), [TRL activation offloading](https://huggingface.co/docs/trl/reducing_memory_usage#activation-offloading).

STOP — FULL QLORA TRAINING NOT STARTED.
