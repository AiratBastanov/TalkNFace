# LOCAL_QWEN_QLORA_MEMORY_ARCHITECTURE_DECISION

**VERDICT: LOCAL_QWEN_QLORA_MEMORY_ARCHITECTURE_DECISION_PASS**

**DECISION: LOCAL_TARGETED_LORA_NEXT — q_proj + v_proj, rank 8, alpha 16.** This selects one final local memory experiment, not full training. Practical step-boundary headroom of at least 256 MiB is **PLAUSIBLE**, not established; 512 MiB is preferred but **LOW_CONFIDENCE** from the present evidence. Static parameter savings alone do not establish either threshold.

No Qwen3-4B model was instantiated or run. Analysis read config/index and bounded safetensors headers, independently instantiated projection shapes on the storage-free `meta` device, and constructed a tiny CPU LoRA-FA optimizer without any forward, backward or optimizer step. No corpus records, model outputs or evaluation cases were inspected. No package was installed or changed.

## Current blocker and evidence

The two completed gates remain frozen. Functional NF4/FP16 QLoRA, explicit pinned-host activation storage, two finite updates, adapter mutation and save/reload are already proven. GPU headroom is not.

| Frozen campaign | Peak allocated MiB | Peak reserved MiB | Minimum CUDA free at updates | Minimum nvidia-smi free |
|---|---:|---:|---:|---:|
| Original all-linear r8, 1024 | 6234.454102 | 6750 | 0 | Not sampled during the campaign |
| Host activation offload, 1024 | 5916.024414 | 6734 | 0 | 92 MiB |
| Host activation offload, 768 | 5621.173828 | 8118 | 0 | 66 MiB |

Physical VRAM is 6144 MiB; CUDA reports 6143.5625 MiB capacity. Before each model load CUDA reported 5103 MiB free. Host RAM stayed above 16 GiB available and pagefile growth was zero in both offload campaigns. These observations support a GPU memory-policy/capacity blocker, not a host-RAM shortage or failed training pipeline.

Sources: [original receipt](LOCAL_QWEN_QLORA_FEASIBILITY_SMOKE.md), [original evidence](evidence/LOCAL_QWEN_QLORA_FEASIBILITY_SMOKE.json), [offload receipt](LOCAL_QWEN_QLORA_HOST_RAM_OFFLOAD_CORRECTION.md), [offload evidence](evidence/LOCAL_QWEN_QLORA_HOST_RAM_OFFLOAD_CORRECTION.json). Exact input hashes and extracted measurements are retained in the new JSON evidence.

## Memory decomposition

| Consumer | Evidence and interpretation | Effect of the selected change |
|---|---|---|
| Quantized base | Measured model footprint 2474.749512 MiB; CUDA allocated immediately after load 2554.405273 MiB. NF4/nested quantization already reduces the base. Footprint and allocator totals have different accounting. | Unchanged; all 252 base linear modules remain NF4 on CUDA:0. |
| Unquantized embedding/norms | Metadata contains 389,152,256 nonquantized parameters, including 388,956,160 tied embedding/head parameters. Installed PEFT upcasts eligible FP16 parameters to FP32: exactly 742.249023 MiB additional raw storage by shape/dtype arithmetic. The shared embedding alone is 1483.75 MiB at FP32 and must not be counted twice as embedding and head. | Unchanged. No embedding dtype, tying, loss or placement change is proposed. |
| Adapter weights | Current raw FP32 adapter weights are 63 MiB. Total measured post-preparation allocation is 3359.886719 MiB. Most of the roughly 805.481 MiB increase from quantized load is base upcasting, not LoRA. | Raw adapter weights fall to 11.25 MiB. |
| Adapter gradients | Approximately 63 MiB if all current adapter gradients are materialized in FP32; base gradients remain absent. FP16 compute does not imply FP16 adapter storage. | Approximately 11.25 MiB. |
| Optimizer | Installed bitsandbytes formula gives about 31.994141 MiB of current 8-bit moment/scaling/map tensor payload, excluding allocator and host bookkeeping. There are no 4B-base optimizer states. | About 5.714844 MiB. |
| Ordinary activations, loss and workspaces | The offload-1024 allocated peak exceeds post-preparation allocation by 2556.137695 MiB. This difference mixes gradients, state, activations, temporaries and workspaces; it is not a measured activation total. Vocabulary size is 151,936. A full 1024-token logit tensor alone is 296.75 MiB in FP16 or 593.5 MiB in FP32. Installed causal loss casts logits to FP32; ignored prompt labels do not prevent full-vocabulary logits from being computed. | Base attention/MLP activations and vocabulary loss remain. LoRA-specific dropout, matrix operations and extra adapter-wrapper buffers are removed from 180 projections. No quantified full-peak saving is asserted. |
| Checkpointed/offloaded activations | Each offload run recorded 288 actual CUDA-to-pinned-CPU packs and 288 restores. Peak observed live host activation storage was 338.203125 MiB at 1024 and 268.59375 MiB at 768. | Preserve this proven mechanism. It stores checkpoint inputs; it does not eliminate the activations/workspaces of a recomputed decoder block or the output loss. |
| CUDA reservation | At the end of the 1024 offload campaign allocated memory was 3471.343262 MiB while reserved memory was 6734 MiB. Cached blocks/virtual reservations cannot be equated to dedicated resident VRAM. | Allocation patterns may change, but no cache flush, allocator setting or counter reinterpretation will be used to manufacture a pass. |
| Windows WDDM/shared residency | Positive nvidia-smi free coexists with zero CUDA free at update boundaries. PDH shared usage can include intentional pinned host storage. Existing evidence does not identify each resident allocation or partition paging versus caching. | Require the same CUDA allocator, free-memory and host telemetry. Neither a positive nvidia-smi reading nor a smaller parameter count proves safe residency. |

An important installed-source qualification: `paged_adamw_8bit` enables a paged-capable optimizer, but `get_state_buffer` only selects a unified-memory buffer for tensors with at least 100,000 elements. Current all-linear r8 LoRA tensors range from 8,192 to 77,824 elements; all local candidates also fall below 100,000. Thus the installed allocation branch predicts ordinary CUDA state buffers for these adapters. The old `is_paged=True` evidence establishes the configured optimizer, not actual paging of its small states. This does not change the historical result. [bitsandbytes optimizer concepts](https://huggingface.co/docs/bitsandbytes/explanations/optimizers).

## Exact projection and adapter calculations

Config dimensions and all 252 corresponding safetensors header entries agree. These are linear **input → output** dimensions; grouped-query attention makes q/k/v nonsquare. There are 36 decoder layers.

| Projection | Input | Output | Count | Parameters in one rank-8 A+B pair |
|---|---:|---:|---:|---:|
| q_proj | 2560 | 4096 | 36 | 53,248 |
| k_proj | 2560 | 1024 | 36 | 28,672 |
| v_proj | 2560 | 1024 | 36 | 28,672 |
| o_proj | 4096 | 2560 | 36 | 53,248 |
| gate_proj | 2560 | 9728 | 36 | 98,304 |
| up_proj | 2560 | 9728 | 36 | 98,304 |
| down_proj | 9728 | 2560 | 36 | 98,304 |

For each targeted linear, `A.shape=(r,input)`, `B.shape=(output,r)` and `N=r*(input+output)`. Bias is none; no embedding or output-head adapter is added. The current formula reproduces the measured 16,515,072 exactly. Independent PEFT meta-device instantiation agrees for all four configurations.

| Targets / rank | A tensors | B tensors | EXACT trainable parameters | Reduction from current |
|---|---:|---:|---:|---:|
| All seven projections / 8 | 252 | 252 | 16,515,072 | 0 |
| q + v / 8 | 72 | 72 | 2,949,120 | 13,565,952 / 82.142857% |
| q + k + v + o / 8 | 144 | 144 | 5,898,240 | 10,616,832 / 64.285714% |
| q + v / 4 | 72 | 72 | 1,474,560 | 15,040,512 / 91.071429% |

| Configuration | EXACT raw FP16/BF16 parameter bytes | EXACT raw FP32 parameter bytes | ESTIMATED FP32 gradient MiB | ESTIMATED 8-bit optimizer payload MiB | ESTIMATED weights + gradients + optimizer MiB |
|---|---:|---:|---:|---:|---:|
| All-linear r8 | 33,030,144 | 66,060,288 | 63 | 31.994141 | 157.994141 |
| q/v r8 | 5,898,240 | 11,796,480 | 11.25 | 5.714844 | 28.214844 |
| q/k/v/o r8 | 11,796,480 | 23,592,960 | 22.5 | 11.427734 | 56.427734 |
| q/v r4 | 2,949,120 | 5,898,240 | 5.625 | 2.858398 | 14.108398 |

BF16 is shown solely as byte arithmetic; it is not proposed on this sm75 GPU. Optimizer estimates follow the inspected 0.50.2 source: two uint8 moments plus two FP32 absmax values per 256 elements and two shared 256-entry FP32 maps. Even the smallest r4 tensor has exactly 4096 elements and remains eligible for 8-bit states. Python bookkeeping, allocator rounding, temporary workspaces, residency and possible version/config overrides are excluded. Gradients assume standard FP32 adapter parameters. [bitsandbytes size threshold](https://huggingface.co/docs/bitsandbytes/optimizers).

The q/v r8 persistent payload reduction is **129.779297 MiB**. Attention-only saves 101.566406 MiB; q/v r4 saves 143.885742 MiB. Reducing q/v rank from 8 to 4 therefore saves only another 14.106445 MiB while halving adaptation rank.

An activation **shape proxy**, not a live-memory estimate: summed LoRA-A input volume within one recomputed decoder block at 1024 tokens is 52 MiB for all-linear versus 10 MiB for q/v at FP16 (104 versus 20 MiB at FP32). The q/v figure is unchanged at rank 4 because input width is unchanged. Shared inputs, dropout, autocast copies, nonlinear lifetimes and checkpoint recomputation prevent adding these volumes across all 36 layers or treating the difference as guaranteed peak savings. The installed 4-bit adapter wrapper also clones its base result and adds LoRA operations; removing wrappers removes that code from 180 projections, with unmeasured net peak effect.

## Installed APIs and LoRA-FA

The private environment is unchanged: Python 3.12.10, torch 2.14.0+cu126, Transformers 5.17.0, PEFT 0.21.0, bitsandbytes 0.50.2, TRL 1.13.0 and Accelerate 1.15.0. Evidence records exact signatures, implementation file paths and source hashes.

PEFT's installed default mapping explicitly assigns `qwen3`, `qwen2`, `llama` and `mistral` to `q_proj`/`v_proj`; defaults are architecture-specific (for example GPT-2 uses `c_attn`, Bloom uses `query_key_value`). The tiny CPU metadata probe resolved Qwen3's default to q/v without an explicit target list. Official Transformers guidance confirms predefined targets for common causal LMs. All-linear is the broader QLoRA-style placement, not an API requirement for training adapters on an NF4 base. [Transformers PEFT targets](https://huggingface.co/docs/transformers/v5.17.0/peft), [PEFT quantized training](https://huggingface.co/docs/peft/v0.21.0/developer_guides/quantization).

Installed LoRA-FA API:

```python
create_lorafa_optimizer(model: PeftModel, r: int, lora_alpha: int, lr: float,
                       weight_decay: float = 0.0,
                       use_rslora: bool | None = None) -> Optimizer
```

It freezes `lora_A` and leaves ordinary `lora_B` trainable. The tiny CPU construction reduced trainable parameters from 192 to 64 with A frozen, B trainable and no optimizer state allocated; **zero forward/backward/step calls** were made. Source inspection shows paired A/B processing, B-gradient projection using a regularized pseudoinverse of `A @ A.T`, and two `zeros_like(B)` Adam moments. On the expected FP32 adapters those moments are FP32. It is a custom AdamW-derived optimizer, not a flag for paged_adamw_8bit; there is no optimizer-class or 8-bit/paged argument in this helper. Use a single active ordinary Linear LoRA adapter with correctly paired A/B and B gradients; avoid assuming support for unrelated variants or sparse/expert parameters. Base parameters must already be frozen by preparation; the helper freezes A, not every arbitrary base parameter.

The official rationale is that fixing A removes the need to retain its large input solely to form A's weight gradient. This concerns the dominant adapter activation term; it does not make parameter/optimizer storage rank-independent or remove base-model activations. All-linear r8 FA would retain 16,515,072 stored adapter parameters but train only **8,847,360 B parameters**. FP32 weights + B gradients + B moments total about **164.25 MiB**, before projection temporaries—slightly more persistent payload than current standard r8 plus 8-bit state. Its potential benefit must come from activations. [PEFT LoRA-FA](https://huggingface.co/docs/peft/v0.21.0/package_reference/lora#lora-fa-optimizer).

No explicit prohibition on a frozen bitsandbytes base appears in the inspected FA helper, which operates on LoRA tensors, and PEFT generally supports LoRA on quantized models. However, these sources do not establish a tested Windows/sm75/NF4/FP16/checkpoint-offload FA combination. The non-training CPU probe does not certify it. FA remains a technically interesting alternative, but it changes the optimizer and gradient geometry while losing the known-good 8-bit state path. It is not selected for the next experiment.

## Candidate decision

Headroom ratings are predictions requiring measurement; none certifies a new GPU fit. Quality judgments below are architectural inferences, not measured accuracies.

| Candidate | Memory and ≥256 MiB headroom prediction | Adaptation-capacity risk | Runtime/time assessment | Decision |
|---|---|---|---|---|
| A: q/v r8 standard LoRA | 82.14% fewer trainable parameters; 129.779 MiB persistent payload reduction plus fewer adapter buffers. **PLAUSIBLE**, not high confidence; ≥512 MiB **LOW_CONFIDENCE**. | Less flexibility than all-linear, but retains trainable attention routing/content projections throughout 36 layers and rank 8. Reasonable first correction for narrow context-to-JSON adaptation. | One target-list change on the proven stack; lowest implementation and debugging cost. | **Selected** |
| B: q/k/v/o r8 | 101.566 MiB payload reduction; retains twice as many adapted projections as A. **LOW_CONFIDENCE** for the required boundary margin without measurement. | More attention flexibility than A, but no evidence it is necessary for this task. | Same supported stack, but less memory reduction than A for an unproven quality benefit. | Reject as next |
| C: q/v r4 | Only 14.106 MiB additional payload reduction over A; input-activation shape term unchanged. **PLAUSIBLE** only with the same uncertainties as A; ≥512 MiB low confidence. | Halves rank on an already restricted target set. No demonstrated quality need to accept that restriction. | Easy, but adds a second tuning variable for a small incremental benefit. | Reject as next |
| D: all-linear r8 LoRA-FA | Removes A-gradient activation requirements but has about 164.25 MiB persistent FP32 payload. **LOW_CONFIDENCE** for net headroom with existing checkpoint offload. | Fixed random A restricts adaptation directions; B uses a different update rule. No task-specific quality evidence. | Installed API exists; optimizer/preconditioning and quantized-runtime combination need independent validation. | Reject as next |
| E: model/parameter CPU offload | Could remove much more base residency, but no verified backward-safe NF4 offload path here. **LOW_CONFIDENCE** for this Windows stack. | Placement alone should not reduce adapter capacity if correctly implemented; correctness remains unverified. | Host/device transfers, tied head/embedding, quantization state and checkpoint backward lifecycle add significant latency and complexity. | Reject as next |
| F: DeepSpeed/ZeRO CPU offload | Optimizer-only offload targets a small adapter-state budget; parameter offload requires a larger runtime change. **LOW_CONFIDENCE** for this setup. | Does not inherently reduce adapter capacity; integration/numerical risks dominate. | New compiled/distributed runtime, Windows build requirements and unverified pinned-stack compatibility exceed the bounded correction's time/risk budget. | Reject as next |
| G: temporary larger-GPU cloud | **HIGH_CONFIDENCE** in available capacity if a dedicated ≥24 GB-class GPU is actually provisioned, but exact training margin still requires a smoke. Free GPU access is not guaranteed. | Can retain all-linear capacity and full sequences; no reason to invent a quality advantage. | More setup, transfer, cost and environment reproduction work than one target-list test. Strong fallback after the local stop, not the selected next architecture. | Defer |

Broad all-linear adaptation is useful general-purpose QLoRA guidance, but it has not been shown necessary for this narrow Russian utterance/public-context → canonical JSON task. q/v adaptation can alter what context is attended to and the information carried forward while preserving the pretrained MLPs. This is a justified experiment, not evidence of adequate language/semantic accuracy. Future quality validation must respect the frozen evaluation boundaries.

The principal uncertainty is that 129.779 MiB is less than the 256 MiB practical target and current live peaks/loss buffers are much larger. The hypothesis additionally relies on removing wide-MLP LoRA operations, their saved/cast/dropout tensors and wrapper allocations, potentially changing cache demand. These effects are unmeasured and may overlap existing base activations. A simple subtraction from the old allocated peak would produce 5786.245117 MiB, but **that is not a forecast of allocated peak or free/resident memory**. The low-cost, single-change probe is justified as the last local attempt; success is not presumed.

## Offload and cloud findings

Accelerate's Big Model Inference CPU hooks load parameters for forward and remove them afterward; its official guide explicitly limits that path to inference. The installed `cpu_offload(model, execution_device=None, offload_buffers=False, state_dict=None, preload_module_classes=None)` signature does not provide a quantized PEFT training lifecycle guarantee. Transformers also reserves `device_map="auto"` for inference. Its FP32 CPU offload example is an LLM.int8 path, not proof of this NF4 training configuration. General CPU backend support should not be confused with safe parameter offload during checkpointed backward. [Accelerate](https://huggingface.co/docs/accelerate/concept_guides/big_model_inference), [Transformers bitsandbytes](https://huggingface.co/docs/transformers/v5.17.0/quantization/bitsandbytes).

DeepSpeed does document Windows training support, so a blanket claim that it cannot work on Windows would be wrong. Its current Windows instructions require Visual C++ tools and a wheel build; standard extensions may compile through JIT. ZeRO-Offload uses CPU Adam, while ZeRO-3 is needed to offload/shard base parameters. No applicable ready binary combination with this exact stack was established, and no installation was attempted. These are concrete integration costs, not a claim of universal impossibility. [DeepSpeed Windows](https://github.com/deepspeedai/DeepSpeed#Windows), [installation](https://www.deepspeed.ai/tutorials/advanced-install/), [ZeRO-Offload](https://www.deepspeed.ai/tutorials/zero-offload/).

TRL documents a separate saved-tensor activation-offload manager. The previous gate instead verified Transformers checkpoint offload; enabling both or swapping managers would be an additional memory-policy variable, so it is not part of the chosen target-only experiment. [TRL memory guide](https://huggingface.co/docs/trl/reducing_memory_usage#activation-offloading).

Cloud fallback would keep canonical data preparation and development local, use a temporary dedicated larger GPU for separately authorized training, and return an adapter/config plus hashes and runtime evidence. A published example of the capacity class is GCP G2 with an L4 listed at 24 GB; this is a capacity example, not a reservation or cost promise. A remote platform would need matching model shard hashes, a pinned platform-specific binary environment, and its own runtime smoke—Windows wheel files cannot simply be transplanted to Linux. [GCP GPU specifications](https://docs.cloud.google.com/compute/docs/gpus#g2_machine_series).

TRAIN would remain the only gradient source; DEV would be a separate authorized evaluation input, while locked INTERNAL_TEST and A01–A16 need not leave the local machine. No splitting, target truncation or relabeling is allowed. Export only an explicitly reviewed allowlist with canonical IDs/hashes and TRAIN contexts, exclude secrets, use temporary credentials outside Git, and return adapter-only artifacts against the identical base. No upload, account, purchase, reservation or remote execution occurred. Free Colab GPU types, limits and availability are dynamic and non-guaranteed; even paid managed notebook access can vary. No specific free GPU is assumed. [Colab resource policy](https://research.google.com/colaboratory/faq.html#resource-limits).

## Exactly one next bounded experiment — not executed

**LOCAL_QWEN_TARGETED_LORA_MEMORY_SMOKE**

Change only `target_modules` from `"all-linear"` to `["q_proj", "v_proj"]`. Keep rank 8, alpha 16, dropout 0.05, bias none, CAUSAL_LM, fresh adapter initialization, and the original pinned Qwen3-4B. Expected trainable count is exactly 2,949,120 across 72 A and 72 B tensors.

Preserve NF4, nested quantization, FP16 compute, explicit CUDA:0 placement, frozen base, the installed Transformers checkpoint offload path and reentrant setting, SDPA, paged_adamw_8bit, learning rate 2e-4, max_length 1024, packing false, microbatch 1, accumulation 4, two actual optimizer updates, seed/data_seed 20260917, no BF16/TF32/cache, no evaluation/scheduled saves/reporting and zero dataloader workers. No package update, weight CPU offload, allocator setting, loss replacement or cache-clearing change is included.

Reconstruct the same historical 32 TRAIN IDs/order and complete lengths; use the same first eight optimizer rows (962, 876, 689, 814, 856, 833, 932, 717 tokens), with a separate unused TRAIN reload row. They exercise the configured 1024 envelope but do not constitute an actual 1024-token or full-corpus maximum-length run. Prove prompt -100 labels, full canonical completion plus EOS, enable_thinking=false and no target truncation before loading the model. Preserve filesystem guards and protected hashes. Save only the new adapter in a new ignored output path, release the worker, and reload in a fresh process for a finite-logit TRAIN-only forward.

Keep the independent 200 ms host/GPU sampler, 12 GiB available-RAM start check, 6 GiB safety floor, measured pagefile growth ceiling of 256 MiB, and unchanged 120/300/600/1800/600-second tests/load/microstep/campaign/reload watchdogs. Record actual gradients, update calls, scaler skips, tensor changes, peaks, pre/post phases, CUDA free at each optimizer boundary, nvidia-smi and optional dedicated/shared counters. Sample boundaries before any cleanup; reserved memory is recorded without being treated as physical residency. Do not terminate user processes.

**Success requires** two finite non-skipped updates, adapter mutation/save/reload, protected integrity/isolation, verified host offload, peak allocated below physical CUDA capacity, no OOM or unexplained oversubscription evidence, safe host memory/pagefile behavior, and **at least 256 MiB CUDA free at each optimizer boundary**. Prefer at least 512 MiB. Even a successful 1024 smoke would not authorize full training.

**LOCAL STOP CONDITION:** one campaign only. If it OOMs, reaches/exceeds physical allocation capacity, has less than 256 MiB CUDA free at either optimizer boundary, violates host safety, exceeds a watchdog, or fails any correctness/isolation check, stop the local training path. No 768 retry, rank-4 retry, alternate target list, LoRA-FA switch, allocator experiment, CPU-weight offload or new runtime is authorized. Preserve the result and require a separate architecture authorization before any further experiment; cloud remains a fallback consideration, not an automatic launch.

Sequence coverage is a separate unresolved requirement. Accepted TRAIN contains 8,000 records with median 870, p90 1126, p95 1188, p99 1253 and max 1421 tokens; all fit the recorded 1536 envelope. Only 934/8000 records fit 768 in the preceding preparation, and argument, close_attempt and counter_offer have no complete records at that limit. Neither 768 nor 1024 can silently become the full-training cap. Before full training, the chosen architecture must separately prove an envelope that preserves every complete TRAIN target (or obtain a separately reviewed sequence strategy). No second experiment is specified or started by this decision.

## Verification, protected state and Git delivery

Six focused static tests passed: counts independently verified against PEFT meta instantiation, actual nonsquare dimensions, 4096/100000 optimizer thresholds, dtype-versus-total-memory accounting, zero-step LoRA-FA construction, and no corpus/evaluation record access. Run the calculation with `.venv-qlora-smoke/Scripts/python.exe -B ml/qlora_memory_decision/analyze.py analyze`; its output goes only to ignored `.tmp/qlora-memory-decision/`. Tests use `python -B -m unittest discover -s ml/qlora_memory_decision -p test_analysis.py -v` in that private environment.

Before/after byte-only audit verifies **268 protected files**, including the three pinned model shards, all existing adapters, raw datasets, corpus/evaluation files, historical receipts, application/contracts and planning files. Both environment inventories remain unchanged. The static worker refuses all corpus JSONL and eval-area opens; aggregate token/manifest statistics were authorized metadata, not held-out example exposure. A separate auditor hashes protected bytes without parsing records. A01–A16, INTERNAL_TEST and tuning-eval example exposure remain zero.

Initial main was clean at `37a2a1ed7d19297f92db556947b8b7da388b8996`, with the exact requested origin and ahead/behind 0/0 after fetch. Only this receipt/evidence and two small analysis/test files are delivered. The JSON records source/input/API hashes and the delivery procedure; resolve the self-referential final commit with `git log -1 --format=%H -- docs/gates/LOCAL_QWEN_QLORA_MEMORY_ARCHITECTURE_DECISION.md`. Normal push and final HEAD/origin/main equality are verified after committing and reported in the final response. Models, adapters, datasets, venv and scratch remain untracked.

This PASS certifies completion of the decision gate. It does not certify new memory fit, quality, full-corpus training or G3 readiness.

STOP — NO ADDITIONAL QWEN3-4B TRAINING PERFORMED.
