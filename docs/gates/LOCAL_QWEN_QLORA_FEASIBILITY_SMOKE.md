# LOCAL_QWEN_QLORA_FEASIBILITY_SMOKE

**Verdict: `LOCAL_QWEN_QLORA_FEASIBILITY_SMOKE_FAIL`.** The NF4/LoRA pipeline executed, saved, and reloaded successfully, but the required **6 GiB GPU memory envelope was not established**. Peak allocated CUDA memory exceeded physical VRAM. This gate does not recommend full training.

## Observed result

| Check | Measurement |
| --- | --- |
| Runtime | Python 3.12.10; torch 2.14.0+cu126; Transformers 5.17.0; accelerate 1.15.0; safetensors 0.8.0 |
| Training libraries | bitsandbytes 0.50.2; PEFT 0.21.0; TRL 1.13.0; datasets 5.0.1 |
| Hardware | Windows x64; RTX 2060; physical 6144 MiB; sm75; CUDA runtime 12.6; driver 610.88; no native BF16 |
| CUDA backend | `libbitsandbytes_cuda126.dll`; native NF4 CUDA forward/backward and paged 8-bit optimizer mutation passed |
| Quantization | Original checkpoint loaded as NF4 4-bit, double quantization, FP16 compute; explicit CUDA:0; 252 quantized linear modules |
| LoRA | all-linear; r=8; alpha=16; dropout=0.05; bias=none; 16,515,072 trainable parameters |
| Frozen base | 4,022,468,096 parameters; no base gradients; all parameters placed on CUDA; use_cache=false |
| Campaign | limit 1024; microbatch 1; accumulation 4; two actual paged_adamw_8bit updates; no CPU model offload |
| Data | 32 complete TRAIN rows, 689–974 tokens, median 844.5; first optimized row 962 tokens; eight distinct rows received gradients |
| Step losses | 2.41476065, 1.41560414 |
| Step times | 33.172 s, 46.656 s |
| Numerical state | finite losses and gradients; no NaN/Inf; no GradScaler skips; scale 65536 throughout |
| Adapter mutation | 504/504 tensors changed; initialized/final hashes and example deltas retained |
| Save/reload | Adapter saved; every reloaded adapter tensor hash matched; unused TRAIN row forward produced finite logits |

## Memory verification failed

Before model load CUDA reported **5103 MiB free**; the initial desktop snapshot reported **5348 MiB free** through nvidia-smi. Peak allocated memory was **6234.4541 MiB (6.0883 GiB)** and peak reserved memory **6750 MiB (6.5918 GiB)**. CUDA reports device capacity **6143.5625 MiB**; nvidia-smi reports physical capacity **6144 MiB**. Both optimizer-step boundaries reported **zero free CUDA memory**. Process peak working set, including adapter serialization, was **3257.3711 MiB**.

Windows WDDM allowed the campaign to finish despite CUDA allocations exceeding physical VRAM. Driver paging/oversubscription is an inference from those measurements; exact dedicated/shared residency at the training peak was not sampled. OS memory-counter inspection occurred after exit and cannot prove peak residency. All parameters being on CUDA and the absence of configured CPU layer offload do **not** establish that the workload stayed in dedicated VRAM. The receipt therefore records a failed memory-envelope verification rather than certifying a 1024 GPU fit.

No CUDA OOM was thrown. The user's single 768-token retry was specifically conditional on OOM, so it was **not run**. There was one model-training attempt, with no rank, learning-rate, length, or quality tuning. Process exit released the training resources before a fresh reload process. No unrelated GPU process was terminated.

## Data, masking and evaluation isolation

Selection used fixed seed 20260917, SHA-256 ordering, full intent coverage, critical ambiguity/negation/injection tags, and a boundary-length first row. All 8,000 TRAIN rows were token-measured; only the 32 selected records were exported and only eight received gradients. No epoch occurred. IDs, lengths, exact optimizer row IDs and the distinct reload row are in the [evidence](evidence/LOCAL_QWEN_QLORA_FEASIBILITY_SMOKE.json). No target was truncated.

The unchanged compiler supplies system/public-context/Russian-utterance prompts and canonical interpretation JSON completions. The original non-thinking chat template was verified token by token. All 32 batches were checked before loading the model, and every optimized batch checked again: prompt labels -100, complete canonical JSON supervised, assistant EOS supervised exactly once, no thinking supervision, and padding ignored.

Stable TRL 1.13's documented text collator accepts prebuilt labels. `SFTConfig(completion_only_loss=True)` plus that collator and an explicit two-update AMP loop provide observable gradients/scaler/optimizer hooks without a full Trainer campaign. [TRL documentation](https://huggingface.co/docs/trl/sft_trainer).

Workers' Python audit hooks blocked eval/holdout/raw-data/receipt reads, network calls and protected writes. **DEV, INTERNAL_TEST, A01–A16 and tuning-eval training exposure: zero.** The separate integrity auditor hashed their bytes without parsing targets. The public context registry was filtered to TRAIN; the only eval-area worker read was the interpretation schema required by the existing compiler. Audit hooks are not a native-code sandbox; before/after hashes independently protect native model-file accesses.

## Integrity and verification

**12 focused tests passed before model load; 13 passed after adding the oversubscription-verdict regression test.** No model was loaded by unit tests. Exact package resolution passed `pip check`; installation used 61 stable binary wheels and took 230.406 seconds. All versions and official wheel URLs/SHA-256 are retained. In the isolated environment, datasets requires fsspec 2026.6.0; the resolver also selected filelock 4.0.0, huggingface_hub 1.32.0 and setuptools 84.0.0. These transitive differences are recorded. The known-good core versions and baseline environment remain unchanged.

All **196 protected file hashes** match before/after: the three pinned model shards, small model/cache files, accepted synthetic corpus, evaluation assets, raw external data, original application sources and frozen planning/gate documents. Baseline environment inventory/stats also match. Model shards retain:

- `model-00001-of-00003.safetensors`: `328a91d3122359d5547f9d79521205bc0a46e1f79a792dfe650e99fc2d651223`
- `model-00002-of-00003.safetensors`: `6cd087b316306a68c562436b5492edbcf6e16c6dba3a1308279caa5a58e21ca5`
- `model-00003-of-00003.safetensors`: `e4bf436957184f4eeb86a80e9db394503f1f56446b2e6b7edeac5b81470f4ca1`

Ignored adapter: `AlagModels/adapters/qlora-feasibility-smoke/1024/adapter_model.safetensors`, **66,126,768 bytes**, SHA-256 `9d902b8748c66be754b9a37f251d8d512bf5471640c4c1153789bd773bffd1c2`. Config, file sizes and all adapter tensor reload hashes are recorded. No weights were merged, committed or published.

## Git delivery and next boundary

Implementation commit **`b188d4d147978c408c0c18f1271a800d998f9231`** was normally pushed to the specified `origin/main`; remote equality and **0/0** were verified before this receipt. Source/config/docs only were staged by explicit paths. Existing ignore rules cover the private venv, expanded files, model, adapter and raw datasets. This receipt/evidence are delivered in a follow-up commit; resolve it with `git log -1 --format=%H -- docs/gates/LOCAL_QWEN_QLORA_FEASIBILITY_SMOKE.md`. Final receipt-push synchronization is verified after that commit and reported in the final response, avoiding a self-referential commit hash.

The successful subchecks establish adapter pipeline execution, not the requested GPU-resident training envelope, language quality, full-corpus feasibility, production speed, or G3 readiness. **`LOCAL_QWEN_QLORA_TRAINING_V1` is not recommended.** First resolve memory residency in a separately authorized bounded investigation. Nothing further was trained or integrated.

Source/reproduction: [ml/qlora_smoke](../../ml/qlora_smoke/README.md). Official references: [bitsandbytes](https://huggingface.co/docs/bitsandbytes/installation), [PEFT](https://huggingface.co/docs/peft/developer_guides/quantization), [Transformers](https://huggingface.co/docs/transformers/quantization/bitsandbytes).

STOP — FULL QLORA TRAINING NOT STARTED.
