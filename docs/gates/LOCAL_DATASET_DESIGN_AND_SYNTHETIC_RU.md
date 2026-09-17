# LOCAL_DATASET_DESIGN_AND_SYNTHETIC_RU

**Verdict: `LOCAL_DATASET_DESIGN_AND_SYNTHETIC_RU_PASS`.**

Created **10,000** accepted Russian supervised examples: **8,000 TRAIN / 1,000 DEV / 1,000 locked INTERNAL_TEST**, using **180** public contexts, **10** domains and all **13** contract intents. A separate **304-example** [development eval](../../evals/local-qwen/dev-ru-v1.json) is marked `TUNING_EVAL_ALLOWED=true`. Training and inference were not performed.

## Contract and design

The existing [g3.ts](../../packages/contracts/src/g3.ts), action/common types, production public-context allowlist and frozen interpretation rules remain authoritative and unchanged. Current Zod parsed all **10,304 targets** and **180 contexts**, with saved-schema parity. Full targets include every key in source-contract order, explicit nulls, no Markdown, explanation or reasoning.

The deterministic pipeline creates a semantic case and expected bindings **before** Russian realization. Seed **20260917**, generator **ru-v1.0.0**, project synthetic provenance on every row. A context registry keeps the corpus compact. The compiler exports TRL-compatible conversational prompt/completion JSONL to ignored scratch; a **1,000-record export** was round-trip checked. No training libraries were installed.

S1-like procurement and S2-like workload fixtures are mixed with logistics, project delivery, service contracts, B2B pricing, hiring, resource allocation, support and rent. These are NLU fixtures, not new production scenarios. Descriptive, semi-opaque and opaque IDs are balanced. Contexts include public briefs, issue/value catalogues, topics, known facts, acknowledgement eligibility, allowed argument bindings and active offers only. They contain no hidden production state.

The interpreter labels language, never utility, feasibility, acceptance policy, social state, outcome or score. Null/empty values represent absence of support. Argument bindings and active-offer targets remain mandatory where the frozen semantics require them. Missing offer references take clarification, retaining explicitly stated terms. Empty commitments have null drafts; partial commitments retain known terms. Only explicit retention language copies active terms. A meaning question and model-side ambiguity have distinct clarification flags.

## Counts and critical language

| Intent | TRAIN | DEV | INTERNAL_TEST | Total |
| --- | ---: | ---: | ---: | ---: |
| argument | 720 | 90 | 90 | 900 |
| ask_question | 720 | 90 | 90 | 900 |
| clarification | 560 | 70 | 70 | 700 |
| close_attempt | 400 | 50 | 50 | 500 |
| concession | 720 | 90 | 90 | 900 |
| counter_offer | 800 | 100 | 100 | 1000 |
| empathy | 400 | 50 | 50 | 500 |
| objection | 720 | 90 | 90 | 900 |
| offer | 960 | 120 | 120 | 1200 |
| pressure | 480 | 60 | 60 | 600 |
| probe_interest | 560 | 70 | 70 | 700 |
| reveal_information | 480 | 60 | 60 | 600 |
| walk_away | 480 | 60 | 60 | 600 |

Every supported TRAIN intent has at least **400** examples. Main-corpus coverage:

| Slice | Count | Rate |
| --- | ---: | ---: |
| Meaningful negation/exclusion | 4112 | 41.12% |
| Ambiguity requiring clarification, excluding injection | 1486 | 14.86% |
| Prompt injection / adversarial | 348 | 3.48% |
| Conditional offers/concessions/counters | 379 | 3.79% |
| Explicit counter-offer inheritance | 323 | 3.23% |
| Bounded noise | 631 | 6.31% |

There are **5881** examples with active public offers, **1500** actual target bindings, **900** argument bindings and **108** contrast pairs. Full per-domain, style, noise, class and nullable-field counts are in the [manifest](../../ml/data/synthetic_ru/manifest.json) and machine-readable evidence.

## Splits, duplicates and holdout isolation

All siblings of each concrete semantic/surface recipe stay together. All contrast pairs stay in TRAIN. Main splits additionally have disjoint context IDs: **140 / 20 / 20**. The tuning eval has independent language families and uses only DEV contexts. INTERNAL_TEST was qualified in scratch and locked when accepted files were materialized; subsequent generation refuses a changed internal-test file. It has not been used for prompt or training iteration.

Exhaustive checks found **zero duplicate IDs, canonical examples or utterance/context pairs**, **zero group leakage**, and **zero normalized utterances shared across splits**. The bounded near-neighbour audit queried all 10,304 rows and inspected **362636** candidate pairs. There are **8341** unique raw utterance strings across main corpus plus tuning eval; repeated strings in different public contexts are intentionally retained. Within-split near variants are expected and remain grouped.

Manual cross-split review removed the entire `dev.offer.memo` family because its package/request construction was too close to a TRAIN family. Its quota was assigned to other existing DEV families. The remaining nearest cross-split pair differs in explicit conditionality and has different contexts and targets. No similarity threshold was loosened.

A01?A16 SHA-256 before and after:

`c32e0b688d0f0a3d7eda547c60cffdcef74c15c95ecfa941e7741adc7be89dc1`

**Training exposure: NONE.** The generator has no holdout/external-data reader. Source hashes were recorded before the final exclusion audit. All **164,864** synthetic/holdout comparisons used only text, never expected labels. Fixed checks cover normalized exact match, token/bigram Jaccard and character similarity. **Zero exact matches and zero threshold flags.** The nearest candidate for all 16 holdouts and the 20 highest family neighbours were manually reviewed; retained neighbours and required generic task overlap are explained in [quality_review.json](../../ml/data/synthetic_ru/quality_review.json). No raw model output was inspected, no holdout failure was used to author a case, no prompt was tuned, and no evaluation was run.

## Validation, privacy and quality review

**28 focused tests passed, 0 failed.** Tests exercise deterministic generation, actual schema validation, ID catalogs, nulls, argument conditions/facts, exact active references, inheritance, ambiguity, negation, injection, duplicate and split detection, compiler canonical JSON, raw/model path refusal and edited-text rejection. Evidence uses the existing JavaScript UTF-16 convention. Cyrillic, digits, punctuation, en/em dashes and emoji are covered; Node also checked every emitted span.

Review covered **153 distinct sampled records**, including **25 random records per main split**, **5 per intent**, and **all 15 safety families**. All generation validation failures were inspected: a repeated contrast context and 21 ID collisions from one repeated recipe name were corrected at source and regenerated. A reporting NameError and sampled capitalization/topic-binding issues were also corrected. No generated row was edited in place. Final schema/public semantics/realization validation accepts **100%** of records, with **0 unknown IDs**, **0 hidden fields** and **0 obvious identifier findings**.

This is project-author review, not independent human annotation. The scanner is bounded; it is not a general PII detector. Binding examples often use labelled business term lists. Lexical checks cannot prove absence of every semantic paraphrase; general contract operations necessarily overlap. PASS certifies this bounded data procedure, not trained-model accuracy.

## Token lengths and repository size

The existing Qwen tokenizer was loaded offline with `enable_thinking=false`; weight-file and network access were forbidden in that process. Measurements include system/user/assistant content and actual chat-template special tokens, with no truncation.

| Main corpus total sequence length | Tokens |
| --- | ---: |
| Median | 869 |
| p90 | 1114 |
| p95 | 1186 |
| p99 | 1245 |
| Maximum | 1421 |

**100% are at most 1,536 tokens.** Per-split and tuning-eval statistics are in [token_statistics.json](../../ml/data/synthetic_ru/token_statistics.json). All 26 dataset/source/report artifacts before these receipts total **15,159,891 bytes**; generated JSON/JSONL totals **15,020,876 bytes**, below the preferred 25 MB limit. Expanded SFT exports remain ignored; no Git LFS.

## External language research and integrity

CaSiNo and Job Interview Negotiation were used only for aggregate linguistic pattern counts (probing, proposals, reasons, coordination, concessions and conjunction patterns), stored in [linguistic_patterns.json](../../ml/data/synthetic_ru/linguistic_patterns.json). No external labels became targets; no corpus translation, source utterance, raw dialogue ID, personal data, timestamp or private utility was copied.

Attribution: CaSiNo, Chawla et al., [NAACL 2021](https://aclanthology.org/2021.naacl-main.254/), [author repository, pinned revision](https://github.com/kushalchawla/CaSiNo/tree/2f6ed4a6a55110152a7699fbaa8150d6036314be), CC-BY-4.0. Job Interview Negotiation, Yamaguchi, Iwasa and Fujita, [EACL 2021](https://aclanthology.org/2021.eacl-main.63/), [author repository, pinned revision](https://github.com/gucci-j/negotiation-breakdown-detection/tree/d4c2bf63b4da95b342fd952065f9ad3e97179134), MIT. Raw notices remain intact. Project synthetic artifact license: **NOT_ASSIGNED**.

Full SHA-256 integrity checks confirm **all 3 model shards**, model inventory/small files and **all 9 raw artifacts** unchanged and matching their pinned evidence. **All 130 originally tracked files** and **173 protected application files** are unchanged, including A01?A16, G0/G1/G2 receipts, baseline raw evidence and deterministic/application source. Model weights were not loaded, moved, converted or modified. Raw datasets remain read-only. Model, raw data, `.venv-ml` and scratch exports remain ignored and were not staged.

## Git delivery and artifact evidence

Dataset implementation commit: **`eec23a82a0fadbbd1ddbe73404f2394c1d75f0e3`** (`feat(ai-data): add Russian synthetic interpretation corpus`), normally pushed to **origin/main** at the user-specified remote. Its remote SHA equals local HEAD; **ahead/behind 0/0 and clean status** were verified before writing this receipt. These two receipt files are delivered in a separate follow-up commit; resolve its ID with `git log -1 --format=%H -- docs/gates/LOCAL_DATASET_DESIGN_AND_SYNTHETIC_RU.md`. Final receipt-push synchronization is reported in the terminal response.

Only explicit reviewed paths were staged, with staged-byte parity and size checks. No force push or global Git setting change. Sandbox Git-directory/Windows-credential restrictions were handled using an approved operation and command-local workspace trust/OpenSSL settings. The initial automatic push rejection was resolved by rechecking the user's attachment's exact default-branch publication instruction; the same normal push then succeeded.

The [machine-readable receipt](evidence/LOCAL_DATASET_DESIGN_AND_SYNTHETIC_RU.json) records all statistics, review decisions, before/after integrity and generated artifact SHA-256 values. Manifest SHA-256: `055c0b7f586dfc860685e7b1dca4bcf466dade863ba4ac669005a8e740418ba7`. Receipt self-hashes are excluded to avoid circular digests. Reproduction commands: [dataset README](../../ml/data/synthetic_ru/README.md).

## Next gate recommendation only

**LOCAL_QWEN_QLORA_FEASIBILITY_SMOKE** is recommended, **not executed**. [next_gate.json](../../ml/data/synthetic_ru/next_gate.json) records the existing 4,022,468,096-parameter Qwen checkpoint, RTX 2060 6 GB, Python 3.12.10 / Torch 2.14.0+cu126 / Transformers 5.17.0, token lengths and a tight-memory feasibility proposal. Ideal four-bit weight storage is a lower bound of about **1.873 GiB**, excluding unquantized modules, activations, adapters, optimizer and runtime overhead. Fit and duration are not established.

Future investigation may use microbatch 1, accumulation, checkpointing, a complete-example sequence subset, four-bit NF4 and FP16 on this non-native-BF16 GPU. Official references checked for this recommendation: [Qwen model card](https://huggingface.co/Qwen/Qwen3-4B), [Transformers NF4 guidance](https://huggingface.co/docs/transformers/quantization/bitsandbytes), [bitsandbytes platform support](https://huggingface.co/docs/bitsandbytes/installation), [PEFT quantization](https://huggingface.co/docs/peft/developer_guides/quantization), [TRL format](https://huggingface.co/docs/trl/sft_trainer), [TRL memory guidance](https://huggingface.co/docs/trl/reducing_memory_usage). No expected training duration is invented. TRL, PEFT, bitsandbytes, Unsloth, LLaMA-Factory and Axolotl remain uninstalled.

**TRAINING: NOT STARTED. MODEL INFERENCE: NOT RUN. G3 APPLICATION INTEGRATION: NOT STARTED.**

STOP ? QLORA TRAINING NOT STARTED.
