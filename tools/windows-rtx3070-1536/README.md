# RTX 3070 Ti — 1536/full-TRAIN envelope gate

This gate is separate from the successful immutable 1024 campaign. It reuses the exact verified Python environment and byte-pinned Qwen3-4B, but writes to new scratch/adapter/result paths.

Order: `00-preflight.ps1` → `03-prepare-smoke.ps1` → inspect preparation → `04-run-targeted-memory-smoke.ps1` exactly once → `05-package-result.ps1`.

`01` and `02` are intentionally NOT_APPLICABLE stubs: do not reinstall the environment or redownload the model.

The preparation tokenizes all 8000 TRAIN records with the Qwen tokenizer, proves observed max 1421 and zero records above 1536, then selects the nine longest complete records. Ranks 5–8 run in optimizer update 1; ranks 1–4 run in update 2; rank 9 is reserved for fresh-process reload. No truncation, DEV/INTERNAL_TEST/tuning-eval/A01–A16 reads, full training, or quality evaluation are allowed.

A normal PASS requires both optimizer boundaries to retain at least 512 MiB CUDA free. `PASS_TIGHT_MEMORY` is diagnostic only and does not authorize full training preparation on this 8-GiB GPU.
