# LOCAL_QWEN_TARGETED_LORA_MEMORY_SMOKE

This gate changes only all-linear rank-8 LoRA to explicit `q_proj`/`v_proj`
rank-8 LoRA. Configuration and all 32 TRAIN IDs/order/lengths are projected
directly from the frozen memory-architecture decision. No evaluation is allowed.

The delivered run is **GPU_ENVIRONMENT_BLOCKED before model load**: the frozen
start had 5396 MiB nvidia-smi free, while preflight and subsequent read-only
observations had 5101 MiB. The 295 MiB deficit exceeds the 256 MiB fair-start
tolerance fixed before preflight. CUDA's 5103 MiB free reading was unchanged;
under WDDM these are distinct measurements. No 4B campaign was launched.

The environment remains `.venv-qlora-smoke`, with no installation or changes.
`preflight.py` verifies Python 3.12.10, pip check, all frozen package versions,
sm75, FP16/runtime metadata, unchanged allocator environment and fair starting
memory. `control.py before` hashes protected files and prepares supervisor-only
control projections; worker audit hooks deny evaluation and historical inputs.
`prepare_smoke_data.py` compiles only the 33 frozen TRAIN records with the accepted
compiler/tokenizer. It never reselects or truncates a target. Expanded examples
remain only in ignored `.tmp/qwen-targeted-lora-memory-smoke/`.

`test_targeted.py` tests the frozen configuration, actual projection-only PEFT
meta shapes (72 A, 72 B, 2,949,120 parameters), completion/JSON/EOS labels,
negative access guards, offload call, monitor safety, ignored outputs and verdict
boundaries. It performs no model checkpoint load, forward or optimizer update.
Its rank-4 meta fixture is a negative configuration assertion, not a training
candidate or experiment.

`offload.py` and `monitor.py` are exact copies of the completed offload gate's
helpers. The former preserves Transformers checkpoint offload to pinned CPU
storage, `every_n_layers=1`, `use_reentrant=True`, and no TRL offload manager.
The latter preserves the independent 200 ms sampler, native pagefile accounting,
optional PDH counters, 12 GiB host start / 6 GiB stop thresholds, watchdogs and
termination restricted to gate-owned processes. Historical helpers are untouched.

`train_smoke.py` refuses a failed preflight or an existing attempt, rechecks
the GPU start, asserts exact runtime adapter structure before forward, and
contains only the 1024 configuration. Its explicit loop preserves the previous
TRL collator/SFTConfig, NF4 CUDA:0 base, FP16 AMP and paged AdamW8bit policy.
Only the first eight frozen rows can contribute gradients, four per update,
with two real non-skipped updates. Read-only microbatch gradient observations
add instrumentation overhead to timing; they never mutate/unscale gradients.
The inherited post-save cache release is cleanup, after boundary measurements,
and is not used as a memory optimization. There is no retry path.

Save only to ignored `AlagModels/adapters/qwen-targeted-lora-memory-smoke/1024/`.
`verify_adapter.py` must run in a fresh process after training exits. It checks
all adapter hashes and performs one finite-logit prompt forward on the frozen
unused TRAIN row, with no generation. `control.py after` checks protected bytes
and both environment inventories. `assess.py` requires every functional and
integrity criterion plus allocation below capacity and >=256 MiB CUDA free at
both optimizer boundaries; >=512 MiB is COMFORTABLE, otherwise ACCEPTABLE.
Reserved CUDA address space alone is not treated as physical residency.

The bounded phase commands use this private interpreter, always with `-B`:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
$python = '.\.venv-qlora-smoke\Scripts\python.exe'
$gate = 'ml/qwen_targeted_lora_memory_smoke'
& $python -B "$gate/control.py" before
& $python -B "$gate/monitor.py" preflight 120 $python -B "$gate/preflight.py"
& $python -B "$gate/monitor.py" prepare-1024 120 $python -B "$gate/prepare_smoke_data.py"
& $python -B "$gate/monitor.py" cheap-tests 120 $python -B "$gate/test_targeted.py"
# Only with passing preflight/tests and no existing campaign:
& $python -B "$gate/monitor.py" TARGETED_QV_R8_1024 1800 $python -B "$gate/train_smoke.py"
# Only after successful functional training and full training-process exit:
& $python -B "$gate/monitor.py" reload-1024 600 $python -B "$gate/verify_adapter.py"
& $python -B "$gate/control.py" after
```

These are phase references, not an unattended batch: stop on a failed
precondition. Existing logs/results intentionally prevent repeating a phase.
The present blocked preflight must not be overridden. Preserve its evidence
before a separately requested resumption after external GPU use is reduced.

An executed campaign failing memory, host/pagefile safety, watchdog,
adapter/reload, or integrity stops this local path. No 768/rank/target/FA/
allocator/optimizer/CPU-weight-offload correction is authorized. A PASS would
recommend only `LOCAL_QWEN_TARGETED_LORA_1536_ENVELOPE_SMOKE`; an executed FAIL
would recommend only `QWEN3_4B_REMOTE_TRAINING_ARCHITECTURE`. The blocked result
calls for rerunning this same gate after its external precondition is restored.

The subset maximum is 974 tokens (first eight maximum 962), despite max_length
1024. It cannot prove a 1421-token record or the full 1536 envelope fits.
REAL_APPLICATION_SMOKE is NOT_APPLICABLE_WITH_REASON: this gate changes only
isolated R&D infrastructure and would write an ignored adapter; no product
code, UI, API behavior or capability changes. Full training is not authorized.
