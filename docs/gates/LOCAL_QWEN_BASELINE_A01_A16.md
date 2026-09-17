# LOCAL_QWEN_BASELINE_A01_A16

**Verdict: `LOCAL_QWEN_BASELINE_A01_A16_PASS`. Model quality: `BASELINE_WEAK`.**

PASS certifies completion of the baseline procedure; model quality is a separate result. No training or application integration was performed.

Initial source snapshot `c742fd179d9f07c35f710441da7747635ef9aee9` was pushed and synchronized before ML implementation. Remote history was empty. The final gate commit contains this receipt and is pushed without force.

## Hardware and runtime

Windows 11 IoT Enterprise LTSC, build 26100, x64; Ryzen 7 5700X3D (8 cores / 16 threads); 32 GiB physical RAM. Exact available RAM/VRAM snapshots are in the JSON evidence.

Python 3.12.10; torch 2.14.0+cu126; Transformers 5.17.0; accelerate 1.15.0; safetensors 0.8.0. NVIDIA RTX 2060, 6144 MiB VRAM, driver 610.88 reporting CUDA compatibility 13.3; the prebuilt torch wheel bundles CUDA 12.6. Native BF16: False; emulated BF16: True.

The checkpoint remains original BF16. Automatic device mapping retains embeddings and 11 decoder layers on CUDA and offloads the remaining layer weights to CPU; no disk offload. No compiler, global Python/CUDA installation, PATH change or administrator action occurred. All exact transitive versions are in [requirements.txt](../../ml/baseline/requirements.txt) and the JSON evidence.

Runtime sources: [official Windows setup](https://pytorch.org/get-started/locally/), [official wheel commands](https://pytorch.org/get-started/previous-versions/), [Qwen3 non-thinking settings](https://huggingface.co/Qwen/Qwen3-4B), [Transformers Qwen3](https://huggingface.co/docs/transformers/model_doc/qwen3), [Accelerate CPU offload](https://huggingface.co/docs/accelerate/usage_guides/big_modeling).

## Frozen model, prompt and evaluation

Model revision: `1cfa9a7208912126459214e8b04321603b3df60c`. All three full shard SHA-256 values match the pinned upstream hashes, beyond the acquisition gate's structural checks. Ten small-file hashes, all 29 model/cache file stats, nine raw artifact hashes and 173 protected project hashes match before/after.

Prompt version: `local-qwen-baseline-v1`. SHA-256: `a4e8b3a6c6bf3b64000abab9d369cd0f76a14889b067a9db19faa159b1066a5b`. The prompt, config, eval asset, schema, requirements and inference/scoring code hashes were captured before the campaign and checked afterward. No prompt tuning or output repair.

`enable_thinking=False`; sampling temperature=0.7, top_p=0.8, top_k=20, min_p=0; seeds 101/202/303; max_new_tokens=512; input cap=4096; eager attention. Python/NumPy/torch CPU/CUDA RNGs reset to the case seed immediately before each generation. Deterministic torch algorithms and CUBLAS workspace configuration are enabled; TF32 is disabled.

A01–A16 retain the exact planning utterances. Expected labels were materialized before inference. The interpretation schema comes from the existing `g3.ts`; G1 canonical action names were not substituted for interpretation intents. Public contexts include only domain catalogs, public/revealed facts, allowed argument bindings and a current offer where specified. The model sees no labels or hidden negotiation state.

A05 primary intent is fixed as objection, with unresolved price clarification and PREPAY=0. A13 exposes only the player's already-known BATNA under an eval-only ID. A14 uses a concrete current 110/all7/50 offer. Optional topic alternatives and exact match rules are documented in the versioned holdout asset. These decisions were frozen before model outputs.

Strict JSON rejects duplicate keys, NaN, Markdown wrappers and trailing explanations. Invalid outputs receive no repair call. Schema checks precede public ID/value, span, argument, condition and offer validation. Frozen commitment checks reject legal-but-invented terms and negation errors. Full expected structure match covers all fields, allowing only documented topic alternatives, set order and valid evidence/clarification wording. Planning rows are semantic prose rather than complete JSON gold; this diagnostic also checks the pre-run null/empty defaults for unspecified bindings. No labels were relaxed after outputs.

## Results

| Seed | Primary intent | JSON | Schema | Semantic | Critical commitments | Ambiguity | Full structure |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 101 | 8/16 (50.00%) | 16/16 (100.00%) | 11/16 (68.75%) | 4/16 (25.00%) | 2/12 (16.67%) | 0/1 (0.00%) | 0/16 (0.00%) |
| 202 | 11/16 (68.75%) | 16/16 (100.00%) | 12/16 (75.00%) | 5/16 (31.25%) | 3/12 (25.00%) | 0/1 (0.00%) | 0/16 (0.00%) |
| 303 | 10/16 (62.50%) | 16/16 (100.00%) | 12/16 (75.00%) | 5/16 (31.25%) | 2/12 (16.67%) | 0/1 (0.00%) | 1/16 (6.25%) |

| Aggregate metric | Result |
| --- | --- |
| PRIMARY_INTENT_ACCURACY | 29/48 (60.42%) |
| JSON_VALID_RATE | 48/48 (100.00%) |
| SCHEMA_VALID_RATE | 35/48 (72.92%) |
| SEMANTIC_VALID_RATE | 14/48 (29.17%) |
| FULL_EXPECTED_STRUCTURE_MATCH | 1/48 (2.08%) |
| CRITICAL_COMMITMENT_ACCURACY | 7/36 (19.44%) |
| AMBIGUITY_CLARIFICATION_ACCURACY | 0/3 (0.00%) |
| UNKNOWN_ID_RATE | 17/48 (35.42%) |
| UNNECESSARY_CLARIFICATION_RATE | 3/42 (7.14%) |

Critical cases: A01, A04, A05, A06, A07, A09, A11, A12, A13, A14, A15, A16. Ambiguity accuracy uses A05 (three generations); A16 is a separate refusal/clarification check. Unnecessary clarification excludes A05/A16.

Negation-sensitive critical accuracy (A05/A09/A11/A15): 3/12 (25.00%). A16 refusal/clarification safety: 0/3 (0.00%).

Outputs with invented legal-domain offer terms: 5. Unknown ID outputs: 17. Raw outputs, token IDs and per-field expected/actual values are retained in the machine-readable evidence.

## Failure matrix

| Seed | Case | Expected intent | Actual intent | Failed fields |
| --- | --- | --- | --- | --- |
| 101 | A01 | ask_question | ask_question | acknowledgementFactId, factIds |
| 101 | A02 | probe_interest | ask_question | acknowledgementFactId, intent |
| 101 | A03 | argument | argument | argument, argument.evidenceSpan, secondaryTopicId |
| 101 | A04 | offer | offer | argument.claimId, offerDraft.conditionalOn, primaryTopicId |
| 101 | A05 | objection | objection | acknowledgementFactId, argument, argument.claimId, clarification, factIds, needsClarification, offerDraft, primaryTopicId, targetOfferId |
| 101 | A06 | counter_offer | offer | argument.claimId, intent, offerDraft.conditionalOn, offerDraft.terms.DELIVERY, primaryTopicId |
| 101 | A07 | concession | offer | argument, argument.claimId, factIds, intent, offerDraft, offerDraft.conditionalOn, primaryTopicId |
| 101 | A08 | pressure | pressure | acknowledgementFactId, factIds, primaryTopicId |
| 101 | A09 | objection | objection | acknowledgementFactId, factIds, tone |
| 101 | A10 | empathy | acknowledge | intent |
| 101 | A11 | objection | argument | acknowledgementFactId, argument, argument.claimId, intent |
| 101 | A12 | clarification | clarification | acknowledgementFactId, clarification, factIds, needsClarification |
| 101 | A13 | reveal_information | offer | argument.claimId, intent, offerDraft.conditionalOn, offerDraft.terms.DELIVERY, offerDraft.terms.PREPAY, offerDraft.terms.PRICE, targetOfferId |
| 101 | A14 | close_attempt | acceptance | intent |
| 101 | A15 | walk_away | walk_away | acknowledgementFactId, factIds, primaryTopicId |
| 101 | A16 | clarification | reveal_information | acknowledgementFactId, clarification, factIds, intent, needsClarification, primaryTopicId |
| 202 | A01 | ask_question | ask_question | acknowledgementFactId, factIds |
| 202 | A02 | probe_interest | ask_question | acknowledgementFactId, factIds, intent |
| 202 | A03 | argument | argument | argument, argument.evidenceSpan, secondaryTopicId |
| 202 | A04 | offer | offer | argument.claimId, offerDraft.conditionalOn, primaryTopicId |
| 202 | A05 | objection | objection | acknowledgementFactId, argument, argument.claimId, clarification, factIds, needsClarification, offerDraft, primaryTopicId, targetOfferId |
| 202 | A06 | counter_offer | counter_offer | acknowledgementFactId, argument, argument.claimId, factIds, offerDraft, offerDraft.terms, offerDraft.terms.DELIVERY, offerDraft.terms.PREPAY, primaryTopicId |
| 202 | A07 | concession | offer | argument.claimId, intent, offerDraft.conditionalOn, primaryTopicId |
| 202 | A08 | pressure | pressure | acknowledgementFactId, factIds, primaryTopicId |
| 202 | A09 | objection | objection | acknowledgementFactId, factIds, tone |
| 202 | A10 | empathy | acknowledge | intent |
| 202 | A11 | objection | objection | acknowledgementFactId, argument, argument.claimId |
| 202 | A12 | clarification | clarification | acknowledgementFactId, clarification, factIds, needsClarification |
| 202 | A13 | reveal_information | reveal_information | acknowledgementFactId |
| 202 | A14 | close_attempt | acceptance | intent |
| 202 | A15 | walk_away | walk_away | acknowledgementFactId, factIds, primaryTopicId |
| 202 | A16 | clarification | reveal_information | acknowledgementFactId, clarification, factIds, intent, needsClarification, primaryTopicId |
| 303 | A01 | ask_question | ask_question | acknowledgementFactId, factIds |
| 303 | A02 | probe_interest | ask_question | acknowledgementFactId, factIds, intent |
| 303 | A03 | argument | argument | argument, argument.evidenceSpan |
| 303 | A04 | offer | offer | argument.claimId, offerDraft.conditionalOn, primaryTopicId |
| 303 | A05 | objection | objection | acknowledgementFactId, argument, argument.claimId, clarification, factIds, needsClarification, offerDraft, primaryTopicId |
| 303 | A06 | counter_offer | offer | argument.claimId, intent, offerDraft.conditionalOn, offerDraft.terms.DELIVERY, primaryTopicId |
| 303 | A07 | concession | offer | argument.claimId, intent, offerDraft.conditionalOn, primaryTopicId |
| 303 | A08 | pressure | pressure | acknowledgementFactId, factIds, primaryTopicId |
| 303 | A09 | objection | objection | acknowledgementFactId, factIds, tone |
| 303 | A11 | objection | objection | acknowledgementFactId, argument, argument.claimId |
| 303 | A12 | clarification | clarification | acknowledgementFactId, clarification, factIds, needsClarification |
| 303 | A13 | reveal_information | offer | acknowledgementFactId, intent, offerDraft, offerDraft.terms, offerDraft.terms.PREPAY, offerDraft.terms.PRICE, targetOfferId |
| 303 | A14 | close_attempt | acceptance | intent |
| 303 | A15 | walk_away | walk_away | acknowledgementFactId, factIds, primaryTopicId |
| 303 | A16 | clarification | reveal_information | acknowledgementFactId, clarification, factIds, intent, needsClarification, primaryTopicId |

Field failure counts: acknowledgementFactId=30, factIds=25, primaryTopicId=21, intent=19, argument.claimId=16, argument=11, offerDraft.conditionalOn=9, clarification=9, needsClarification=9, offerDraft=6, targetOfferId=4, offerDraft.terms.DELIVERY=4, argument.evidenceSpan=3, tone=3, offerDraft.terms.PREPAY=3, secondaryTopicId=2, offerDraft.terms.PRICE=2, offerDraft.terms=2.

Primary-intent confusions: `probe_interest` → `ask_question` (3); `concession` → `offer` (3); `close_attempt` → `acceptance` (3); `clarification` → `reveal_information` (3); `counter_offer` → `offer` (2); `empathy` → `acknowledge` (2); `reveal_information` → `offer` (2); `objection` → `argument` (1).

Schema failures: `$.offerDraft.conditionalOn: array length` (8); `$.intent: enum` (5). Empty conditional arrays must be null when no condition exists; `acceptance` and `acknowledge` are outside the frozen interpretation enum.

The model frequently adds fact/acknowledgement bindings where the frozen expected structure has none. All three A03 outputs identify an argument but fail the claim-evidence check. A05 never safely clarifies the unresolved price; A16 never takes the required refusal/clarification path. These failures, alongside incomplete or incorrect offer inheritance, prevent use at the future G3 acceptance bar.

The JSON evidence distinguishes unknown IDs from invented terms, missing/extra fields from semantic errors, and primary-intent correctness from full-structure correctness. The observed weaknesses are preserved; this gate does not modify the prompt or train against failed holdout cases.

## Latency and resources

Model load: 4.846 s. Generation mean / median / p95 (nearest rank): 111.515 / 98.472 / 176.932 s. Output tokens per second including prefill: 1.507. Total evaluation wall time including load: 5366.202 s.

CUDA peak allocated / reserved: 4.111 / 4.398 GiB. Process peak working set: 6.165 GiB. This is one sequential holdout campaign, not a concurrency/load-capacity benchmark. The one generic English sanity generation is excluded from these metrics.

## Verification, isolation and next gate

Targeted verification: 13 scorer and process-lifecycle tests; 304 Python/Zod schema-parity checks; unchanged application/schema source; dataset and network guard checks; dependency consistency; pre/post full-model, small-file, raw-data and protected-source integrity. Browser E2E was not repeated because no application behavior changed.

Code review found a Windows venv launcher cleanup issue and reporting gaps: ID/term emissions could be hidden by an unrelated schema failure, ambiguity success needed to require semantic safety, and nullable-schema errors hid nested field paths. These were corrected after the campaign. The inference worker function is AST-identical; prompt, configuration and expected labels are unchanged. Metrics were recalculated from the same 48 raw outputs with zero model calls. Executed/final hashes and reversible source diffs are preserved in the JSON evidence.

Training status: no training, LoRA, QLoRA, quantization, conversion, normalization, translation, synthetic training data or splits. CaSiNo and Job Interview were accessed only by the separate hash auditor. No external model API, G3 route/UI integration or SQLite AI migration was introduced.

Exactly one next bounded recommendation: **`LOCAL_DATASET_DESIGN_AND_SYNTHETIC_RU`**. Design the local data and Russian supervision requirements before any training authorization; keep this holdout excluded and preserve this baseline for comparison.

Reproduction commands and metric definitions: [baseline README](../../ml/baseline/README.md). Machine-readable receipt: [evidence](evidence/LOCAL_QWEN_BASELINE_A01_A16.json).

STOP — TRAINING AND G3 APPLICATION INTEGRATION NOT STARTED.
