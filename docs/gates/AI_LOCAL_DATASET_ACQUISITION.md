# AI local dataset acquisition

**Verdict: `AI_LOCAL_DATASET_ACQUISITION_PASS`**

Completed: 2026-09-17T08:20:08.962120+00:00. Acquisition and structural verification only. Both authoritative corpora are accepted with the source quirks documented below; neither is training-ready.

## Model verification

`C:\Users\BastaPC\Desktop\Alag\AlagModels\Qwen3-4B` — **STRUCTURAL_PASS**. The existing model was neither moved nor modified. Official source: [Qwen/Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B/tree/1cfa9a7208912126459214e8b04321603b3df60c), revision `1cfa9a7208912126459214e8b04321603b3df60c`; Apache-2.0 is verified in the local LICENSE and official model metadata.

| Property | Verified value |
| --- | --- |
| Total local bytes, including Hugging Face cache | 8,060,930,550 (7.5073 GiB) |
| Root files / weight-file bytes | 8,060,926,626 / 8,044,982,000 |
| Checkpoint | Original Hugging Face BF16 safetensors; 3 shards; no GGUF or incomplete downloads |
| Architecture | Qwen3ForCausalLM / qwen3; 36 layers; hidden 2560; intermediate 9728; head dimension 128 |
| Attention | 32 query heads / 8 key-value heads; no sliding window |
| Position / vocabulary config | max_position_embeddings=40960; rope_theta=1000000; vocab_size=151936; tied embeddings |
| Parameters / indexed tensors | 4,022,468,096 / 398 |
| Tokenizer | tokenizer.json, tokenizer_config.json, vocab.json, merges.txt; Qwen2Tokenizer/BPE; chat template present |
| Special token IDs | BOS 151643; config EOS 151645; generation EOS [151645,151643]; generation PAD 151643 |
| Config-recorded library version | transformers_version=4.51.0 (metadata only; no installation performed) |

| Shard | Bytes | Tensors |
| --- | --- | --- |
| model-00001-of-00003.safetensors | 3957900840 | 174 |
| model-00002-of-00003.safetensors | 3987450520 | 219 |
| model-00003-of-00003.safetensors | 99630640 | 5 |

Config, generation config, tokenizer configuration, tokenizer vocabulary and index parse successfully. Every indexed tensor exists in the correct nonempty shard; BF16 tensor shapes, contiguous offsets, payload bounds and index total_size agree. Official revision metadata matches shard sizes and all small-file content hashes (including the LFS tokenizer). The 12 local HF download metadata files agree on one revision. Only safetensors headers were read: no tensor payload load, large-shard hashing, inference or runtime compatibility test was performed. The 40960 config limit is not a demonstrated runtime context capability.

## Authoritative sources and licenses

| Dataset | Pinned author repository | Revision | License | Paper |
| --- | --- | --- | --- | --- |
| CaSiNo | [kushalchawla/CaSiNo](https://github.com/kushalchawla/CaSiNo/tree/2f6ed4a6a55110152a7699fbaa8150d6036314be) | 2f6ed4a6a55110152a7699fbaa8150d6036314be | CC-BY-4.0 | [Chawla et al., NAACL 2021](https://aclanthology.org/2021.naacl-main.254/) |
| Job Interview Negotiation | [gucci-j/negotiation-breakdown-detection](https://github.com/gucci-j/negotiation-breakdown-detection/tree/d4c2bf63b4da95b342fd952065f9ad3e97179134) | d4c2bf63b4da95b342fd952065f9ad3e97179134 | MIT | [Yamaguchi, Iwasa and Fujita, EACL 2021](https://aclanthology.org/2021.eacl-main.63/) |

CaSiNo is the English human-human campsite negotiation corpus over Food, Water and Firewood. Job Interview is the official English human-human multi-issue job negotiation corpus; its repository is archived/read-only. Source identity is confirmed by the papers and author repositories. The license of each corpus was checked independently against its pinned LICENSE text and GitHub SPDX metadata; the Job Interview README also explicitly declares MIT. Preserve author/paper attribution and the relevant license notices in any later permitted derivatives. Neither license was inferred from a mirror or from memory.

License evidence: [CaSiNo LICENSE](https://github.com/kushalchawla/CaSiNo/blob/2f6ed4a6a55110152a7699fbaa8150d6036314be/LICENSE), [Job Interview LICENSE](https://github.com/gucci-j/negotiation-breakdown-detection/blob/d4c2bf63b4da95b342fd952065f9ad3e97179134/LICENSE). Copies of each README and LICENSE sit with its raw dataset. CaSiNo data/README.md and the JI schema helper were also retained; the helper was read only, not imported or executed.

## Raw artifact inventory

Paths are relative to the workspace. All nine artifacts are read-only and their SHA-256 values were checked again after inspection. Exact source URLs, acquisition timestamps, Git blob identities and ZIP parent linkage are in the JSON manifest.

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| AlagDatasets/raw/casino/data/casino.json | 4300019 | 4f2c4560a0070906ed018c3f0766e35f8f8f31b36274ebf35b608621915744ab |
| AlagDatasets/raw/casino/README.md | 2061 | b52d17f5a0d71a8760a42cc3cb5b02f7c0ba739487a6a703e15f655400d465a6 |
| AlagDatasets/raw/casino/LICENSE | 18658 | f5b745ef98087f531e719ee8ca6a96809444573ecc7173c6fa68eaad39b3cc3f |
| AlagDatasets/raw/casino/data/README.md | 1590 | 2cc2a0bfe22e3285ddb4a04a1675dfe68b2609ec561ae0595ebcdd5504344001 |
| AlagDatasets/raw/job-interview/data.zip | 4324755 | 1bfe698a677ed6faaebe2ebdc607d913c7e6e5814c91e471a000c21894ec6dd9 |
| AlagDatasets/raw/job-interview/README.md | 2558 | b95b22909943ca220f11f8e66b33dd64727808c64909f5f6d8862e5d1748000a |
| AlagDatasets/raw/job-interview/LICENSE | 1107 | b1c72068b3d8b1f4dc0a509035aee17848ff129b259d6889a76754512aceb873 |
| AlagDatasets/raw/job-interview/helper/negotiation_ji.py | 9337 | eb5737a790e9ae678fd828e31c70f762dae7a41efc80812c2cae633e43d7e8e9 |
| AlagDatasets/raw/job-interview/data.json | 40712917 | 989ad5bb86a4c4552e34bfb1af4c31344dd21c9c02900eb218328f3c2126199e |

All acquisitions completed on 2026-09-17 UTC. Repository/commit/tree API responses and successful blob envelopes are retained under AlagDatasets/manifests/upstream. Each non-extracted artifact matches the size and Git blob SHA-1 in its pinned repository tree; data.json is the exact ZIP member. A Git blob identity check is additional to the local SHA-256 inventory.

Transport was bounded HTTPS with certificate validation. Windows curl failed before acquisition with a Schannel credential error; the working Python HTTPS transport was used. A stalled CaSiNo raw transfer and a stalled API envelope were quarantined outside raw. A single verified HTTP 206 range completed the missing 105715 bytes of the original raw file; the assembled file matched the pinned upstream Git blob before acceptance. Successful downloads were reused, not redownloaded. No TLS bypass, administrator rights, system installation, global PATH change, Git LFS or dataset framework was used.

ZIP inspection preceded extraction: data.json (40712917 bytes), __MACOSX/ and a 176-byte AppleDouble ._data.json were present. Absolute/drive paths, traversal, symlinks, duplicate paths, executable payloads, encryption and unreasonable sizes were rejected by the policy. The known inert AppleDouble header was verified and skipped; only data.json was written under AlagDatasets/raw/job-interview. CRC test: PASS. Unexpected binary files: 0; data.zip is the expected archive, and the retained Python helper is plain source text.

## Counts and schema

| Metric | CaSiNo | Job Interview |
| --- | --- | --- |
| Raw dialogues/sessions | 1030 | 3935 |
| Natural-language utterances | 11919 | 39636 |
| Control/event entries | 2378 | 7376 structured bid records (separate from comments) |
| Total chat-log entries | 14297 | 39636 comments |
| Annotated dialogues | 396 | 0 with stored dialogue-act labels |
| Annotation rows | 4615 | Not supplied |
| Valid strategy label assignments | 5858 | Not supplied |

CaSiNo is a JSON list. Each dialogue has dialogue_id, chat_logs, participant_info and annotations. Chat records contain text, local speaker alias id and task_data. Participants provide High/Medium/Low issue preferences and prepared reasons; outcome fields contain points_scored, satisfaction and opponent_likeness. Annotations are [utterance text, comma-separated label string] pairs, not a dense label array aligned with every chat entry. In annotated dialogues there are 4618 language turns but 4615 annotation rows. The remaining 7301 language turns belong to unannotated dialogues.

Job Interview is a JSON list with id, status, two users, comments and solutions. Comments contain body, user_id, id and created_at; speaker roles are worker and recruiter. Solutions contain a proposal body, creator, time and accepted state. Utility profiles describe five weighted issues; Position utility depends on Company. Integer domains observed in raw are Salary 20–50 and Weekly holiday 2–6. Discrete options are Company {Amazon, Apple, Facebook, Google}, Position {Designer, Engineer, Manager, Sales}, and Workplace {Beijing, Seoul, Sydney, Tokyo}. Weights sum to approximately 1 within floating-point precision. No utility calculation, training extraction or historical dependency installation was performed.

| JI status | Sessions | Comments | Bids |
| --- | --- | --- | --- |
| completed | 2500 | 31384 | 6348 |
| terminated | 139 | 1797 | 301 |
| aborted | 1296 | 6455 | 727 |

The paper count of 2639 equals the raw non-aborted subset (2500 completed + 139 terminated). The downloaded file contains 3935 sessions, including 1296 aborted. The official helper filters differently for different tasks, so its output is not the raw-file count. No rows were filtered here.

## Annotation and event inventories

| CaSiNo strategy label | Frequency |
| --- | --- |
| elicit-pref | 377 |
| no-need | 196 |
| non-strategic | 1455 |
| other-need | 409 |
| promote-coordination | 579 |
| self-need | 964 |
| showing-empathy | 254 |
| small-talk | 1054 |
| uv-part | 131 |
| vouch-fair | 439 |

| CaSiNo control event | Frequency |
| --- | --- |
| Accept-Deal | 1005 |
| Reject-Deal | 167 |
| Submit-Deal | 1181 |
| Walk-Away | 25 |

These are nine strategy labels plus non-strategic; they are multi-label annotations, not exclusive G1 actions. One empty delimiter token is reported separately, not counted as a valid label. The [CaSiNo paper, Table 2 and section 3](https://aclanthology.org/2021.naacl-main.254.pdf) supports the vocabulary and notes weaker annotator agreement for coordination and empathy.

Job Interview stores **no utterance dialogue-act labels**, so an observed act-frequency table would be fabricated. Frequencies are null / NOT_AVAILABLE_IN_RAW in the manifest. The [JI paper, section 5.1 and Table 4](https://aclanthology.org/2021.eacl-main.63.pdf) describes rule-based greet, disagree, agree, inquire, propose, inform and fallback unk; sep/end/pad are structural tags. These were reviewed for relevance only, and no extractor was run. Stored outcome inventories are status={completed:2500, terminated:139, aborted:1296} and accepted={true:2488, null:4888}; false does not occur.

CaSiNo language contains emotion symbols: smiling face 1595, frowning face 268, open-mouth face 139, pouting face 44, plus one sun symbol. These are not gold G1 tone labels.

## Data-quality findings

| Check | CaSiNo | Job Interview |
| --- | --- | --- |
| Strict UTF-8 / JSON errors | 0 / 0 | 0 / 0 |
| Duplicate JSON keys / replacement characters / lone surrogates | 0 / 0 / 0 | 0 / 0 / 0 |
| Missing required dialogue/comment fields | 0 | 0 |
| Empty utterance strings | 0 | 0 |
| Empty dialogues | 0 | 312 |
| Duplicate dialogue IDs | 0 | 0 |
| Exact duplicate full records | 0 | 0 |
| Malformed annotation entries | 1 label string with one empty token | No stored annotations |
| Annotation length mismatch dialogues | 3 | Not applicable |
| Annotation positional text mismatches | 26 across those 3 dialogues | Not applicable |
| Unknown nonempty annotation labels | 0 | Not applicable |
| Malformed bid records | 0 | 4 records in 3 sessions |
| Unique natural-language strings | 11617 | 30612 |
| Exact duplicate language-string groups | 102 | 1639 |
| Repeated language occurrences beyond first | 302 | 9024 |
| Nonempty role/text sequence duplicate groups | 0 | 18 (84 extra sequences) |
| Adjacent same-speaker language pairs | 60 in 48 dialogues | 12909 in 3089 sessions |
| Comment/bid timestamp inversions | No timestamps in schema | 0 / 0 |

Malformed/corrupt-record accounting: both files contain 0 corrupt/unparseable JSON records and 0 missing top-level/utterance fields. CaSiNo has one malformed annotation label string plus three incomplete annotation sequences, affecting four distinct dialogues. Job Interview has four malformed proposal records in three distinct sessions (one missing issue and three fractional values in INTEGER issues). Source quirks are not transport corruption: acquired bytes match their authoritative source identities.

- **CaSiNo — ANNOTATION_ALIGNMENT:** Dialogues 35, 428 and 596 each have one unannotated natural-language turn. All 4615 annotation texts exist exactly in their own dialogue, without ambiguous duplicate text, but positional zip alignment would misassign 26 overlapping rows. No repair performed.

- **CaSiNo — EMPTY_LABEL_TOKEN:** Dialogue 19, annotation index 11 has small-talk,self-need,,vouch-fair. One empty comma-delimited token; 10 recognized nonempty labels and 5858 valid label assignments. Raw bytes retained.

- **CaSiNo — NO_UNIVERSAL_ACTION_LABELS:** Only 396 dialogues have strategy annotations. Strategy labels are multi-label and are not a complete canonical-action inventory. Control markers are not natural utterances.

- **Job Interview — RAW_VS_PAPER_COUNT:** 3935 raw sessions = 2500 completed + 139 terminated + 1296 aborted. Excluding aborted sessions gives the paper count of 2639; the official helper applies task-dependent filters. No filter or split was applied here.

- **Job Interview — NO_STORED_DIALOGUE_ACT_LABELS:** The raw schema has no per-utterance dialogue-act annotations. Paper vocabulary comes from heuristic extraction, not supplied gold labels; act frequencies are unavailable. No extractor was run.

- **Job Interview — SHORT_AND_EMPTY_SESSIONS:** 312 sessions have zero comments and 709 have fewer than three. These remain in the immutable raw corpus and raw-session count.

- **Job Interview — MALFORMED_BIDS:** Four bid records in three sessions: Salary 35.5 appears twice in session index 569; Weekly holiday 4.8 appears once in index 1205; one bid omits Salary in index 1777. The fractional values are within numeric bounds but violate the declared INTEGER type.

- **Job Interview — OUTCOME_AMBIGUITY:** accepted is true for 2488 bids and null for 4888; no explicit false values. Forty-eight completed sessions have no accepted bid, 26 aborted sessions have accepted bids, and 10 sessions have two accepted bids. Do not derive utterance labels from status or null acceptance.

- **Job Interview — SCHEMA_RANGE_DISAGREEMENT:** Raw utility limits are Salary 20..50 and Weekly holiday 2..6. The paper lists weekly days off 2..5; helper constructor limits use 20..51 and 2..7 and get_all_bids uses exclusive range stops. Use the observed raw definitions for this audit; do not silently normalize these differences.

- **Both — EXACT_DUPLICATES:** Exact utterance repetition is a statistic, not automatic corruption. CaSiNo has 302 extra repeated language utterances; JI has 9024. JI also has 18 duplicate nonempty role/text dialogue-sequence groups (84 extra sequences). Any later split must prevent group leakage; none created here.

- **Both — LANGUAGE_AND_DOMAIN_GAP:** Both sources are English and use different issue vocabularies from Negotiation Arena. Neither is a ready Russian canonical-action corpus. No translation, synthetic generation or target-label conversion was performed.

- **Both — TONE_AND_PRIVACY:** No G1 tone gold labels exist. CaSiNo emoticons and personal disclosures do not justify tone/personality inference. Demographics, personality, linkable IDs and absolute timestamps are excluded by default as specified in the field review.

Duplicate counts use exact decoded strings with case/spacing preserved; no text was deduplicated. JI has 19 duplicate role/text sequence groups including the 312 empty sessions, or 18 groups after considering only nonempty sequences. Empty sessions are valid source records with no language examples. Same-speaker adjacency is documented rather than forcibly repaired; JI comments are asynchronous, and CaSiNo control events affect alternation. Raw comments and bids are each timestamp-ordered, but no merged or normalized turn stream was written.

## Canonical-action mapping assessment

The inspected frozen contracts are packages/contracts/src/action.ts and packages/contracts/src/common.ts. Actual kinds: question, acknowledge, argument, offer, counter_offer, accept, pressure, walk_away, clarification. **There is no standalone objection action.** Tone values are neutral, respectful_firm, accusatory and threat. G1 proposal packages require 2–4 terms, whereas ordinary JI bids have 5 issues. No contract was changed.

`DIRECT_MAPPING`: Same intent at the stated annotation/event level. This does not imply a complete G1 action payload or a safe label for adjacent dialogue text.

`PARTIAL_MAPPING`: Overlapping, broader, contextual or multi-intent evidence; no automatic relabeling is justified.

`NO_SAFE_MAPPING`: No reliable label transfer, orthogonal metadata, or no corresponding action in the frozen G1 contract.

A direct intent/event match does not make a valid full canonical action. Topic/fact/argument IDs, offer references, scenario term IDs, conditions and evidence bindings remain unresolved. No event label is propagated to neighboring text, and no external label is converted into a training label.

| Requested category | G1 kind/field | CaSiNo | Job Interview | Assessment |
| --- | --- | --- | --- | --- |
| question / probe interest | question | DIRECT_MAPPING | PARTIAL_MAPPING | CaSiNo elicit-pref is the strongest intent-level match; JI has unlabelled text and only paper-described heuristics. |
| acknowledgement | acknowledge | PARTIAL_MAPPING | PARTIAL_MAPPING | Requires an established acknowledgementFactId; empathy/agreement alone does not supply one. |
| argument | argument | PARTIAL_MAPPING | PARTIAL_MAPPING | Reasons and assertions are useful language, but neither dataset binds valid G1 argument IDs. |
| offer | offer | PARTIAL_MAPPING | PARTIAL_MAPPING | Use language and structured proposal context only after a separately approved mapping design. |
| counter-offer | counter_offer | PARTIAL_MAPPING | PARTIAL_MAPPING | Neither external strategy set identifies targetOfferId; sequential proposals alone are insufficient. |
| pressure | pressure | PARTIAL_MAPPING | NO_SAFE_MAPPING | Some CaSiNo undermining language may be relevant, but no explicit pressure label exists in either raw corpus. |
| objection | ABSENT | NO_SAFE_MAPPING | NO_SAFE_MAPPING | Requested analysis category is absent as a standalone action in the actual frozen G1 schema. |
| clarification | clarification | PARTIAL_MAPPING | PARTIAL_MAPPING | Preference statements or informative replies require contextual review; no direct clarification label. |
| acceptance | accept | DIRECT_MAPPING | PARTIAL_MAPPING | CaSiNo direct match is a UI event only; JI stores bid acceptance state, not language labels. |
| walk-away | walk_away | DIRECT_MAPPING | NO_SAFE_MAPPING | CaSiNo direct match is a UI event only; JI terminal status cannot establish utterance intent. |
| tone | tone | NO_SAFE_MAPPING | NO_SAFE_MAPPING | No gold neutral/respectful_firm/accusatory/threat annotations; emotion symbols are not equivalent. |

| Source | External label/field | Candidate category | State | Reason |
| --- | --- | --- | --- | --- |
| CaSiNo | elicit-pref | question / probe interest | DIRECT_MAPPING | Preference probing matches the intent; topic IDs and multi-intent arbitration remain unresolved. |
| CaSiNo | self-need | argument | PARTIAL_MAPPING | A stated need can motivate an argument, but does not identify a valid G1 argumentId. |
| CaSiNo | other-need | argument | PARTIAL_MAPPING | Reasons about another person may support an argument; neither factual truth nor argument binding follows from the label. |
| CaSiNo | no-need | argument / clarification | PARTIAL_MAPPING | A preference statement is not necessarily an argument or clarification; turn context matters. |
| CaSiNo | showing-empathy | acknowledge | PARTIAL_MAPPING | Empathy does not necessarily acknowledge a specific established fact. |
| CaSiNo | promote-coordination | offer / counter_offer | PARTIAL_MAPPING | Cooperation can be proposed without concrete terms or a referenced previous offer. |
| CaSiNo | uv-part | argument / pressure / objection-like language | PARTIAL_MAPPING | Undermining a need does not uniquely determine an action or tone. |
| CaSiNo | vouch-fair | argument / acknowledge / objection-like language | PARTIAL_MAPPING | A fairness claim may endorse or challenge a proposal; context is required. |
| CaSiNo | small-talk | none | NO_SAFE_MAPPING | Rapport and greetings do not imply acknowledgement of a G1 fact. |
| CaSiNo | non-strategic | none | NO_SAFE_MAPPING | Absence of a listed strategy is not absence of a canonical action; offers and acceptance can occur here. |
| CaSiNo | Submit-Deal + allocation task_data | offer / counter_offer | PARTIAL_MAPPING | Structured event, not a language example; does not distinguish initial from counter-offer or supply internal IDs. |
| CaSiNo | Accept-Deal | accept | DIRECT_MAPPING | Explicit acceptance event only. Binding to the relevant offer and to any natural utterance is future work. |
| CaSiNo | Walk-Away | walk_away | DIRECT_MAPPING | Explicit exit event only; it is not a gold label for the preceding utterance. |
| CaSiNo | Reject-Deal | objection | NO_SAFE_MAPPING | G1 has no standalone objection/reject action. Rejection does not imply walk_away. |
| CaSiNo | emoticons / satisfaction / personality | tone | NO_SAFE_MAPPING | Emotion, outcome satisfaction and personality are different from G1 tone; do not infer tone from them. |
| Job Interview raw | comments[].body with prior turns and role | candidate negotiation intents | PARTIAL_MAPPING | Useful natural language, but no stored action/act labels. Annotation would require a later gate. |
| Job Interview raw | solutions[].body | offer / counter_offer | PARTIAL_MAPPING | Structured proposals have five issues; G1 PackageSchema permits two to four. Do not truncate or copy them automatically. |
| Job Interview raw | solutions[].accepted == true | accept | PARTIAL_MAPPING | An acceptance state tied to a bid, not an utterance annotation or explicit accepting-speaker event. |
| Job Interview raw | solutions[].accepted == null | objection / walk_away | NO_SAFE_MAPPING | Null supplies neither an explicit rejection nor an exit intent. |
| Job Interview raw | completed / aborted / terminated | accept / walk_away | NO_SAFE_MAPPING | Session status is not an utterance action; status and accepted-bid metadata can disagree. |
| Job Interview paper only | inquire | question / probe interest | PARTIAL_MAPPING | Heuristic question patterns can also occur in proposals; labels are absent from raw data. |
| Job Interview paper only | agree | acknowledge / accept | PARTIAL_MAPPING | Broad agreement/thanks patterns do not resolve factual acknowledgement versus binding acceptance. |
| Job Interview paper only | propose | offer / counter_offer | PARTIAL_MAPPING | Broad numeric/pattern extraction does not establish a valid complete offer. |
| Job Interview paper only | inform | clarification / argument | PARTIAL_MAPPING | Reply information is broader than either G1 action; no factual or argument binding follows. |
| Job Interview paper only | disagree | objection | NO_SAFE_MAPPING | Broad negative patterns and rejection are not a supported standalone G1 action. |
| Job Interview paper only | greet / unk / sep / end / pad | none | NO_SAFE_MAPPING | Greetings, unknown markers and sequence-control tags do not map to canonical actions. |

## Privacy and field use

USEFUL_FOR_NLU means a candidate for later reviewed preparation, not permission to copy raw values directly. USEFUL_FOR_RESEARCH_ONLY stays outside default NLU examples. EXCLUDE_FROM_TRAINING_BY_DEFAULT must not become model-visible features or labels without a separately justified experiment. Immutable source files retain every original field.

| Dataset | Fields | Classification | Reason |
| --- | --- | --- | --- |
| CaSiNo | chat_logs[].text (natural-language entries) | USEFUL_FOR_NLU | Primary candidate text; future contextual/manual review and personal-information screening are still needed. |
| CaSiNo | chat_logs[].id; array order | USEFUL_FOR_NLU | Local participant aliases and turn sequence provide conversational context; do not mistake id for an utterance ID. |
| CaSiNo | annotations[][0:2] | USEFUL_FOR_NLU | Utterance text plus comma-separated strategy labels; preserve original semantics and audit the documented alignment/format defects. |
| CaSiNo | chat_logs[].task_data.issue2youget / issue2theyget | USEFUL_FOR_NLU | Three-issue allocation context for later proposal interpretation, with scenario-specific ID mapping required. |
| CaSiNo | chat_logs[].text (control markers); task_data.data | USEFUL_FOR_RESEARCH_ONLY | Event evidence and alignment context only; never use the marker as a Russian-language utterance or label a neighboring turn automatically. |
| CaSiNo | participant_info.*.value2issue.{High,Medium,Low} | USEFUL_FOR_NLU | Scenario preference grounding when legitimately known at the turn; hidden partner preferences must not leak into inputs. |
| CaSiNo | participant_info.*.value2reason.{High,Medium,Low} | USEFUL_FOR_NLU | Potential interest/argument context, subject to personal-detail review and visibility rules; not automatically factual or valid G1 arguments. |
| CaSiNo | participant_info.*.outcomes.points_scored | USEFUL_FOR_RESEARCH_ONLY | Post-negotiation utility/outcome research, not input-time action supervision. |
| CaSiNo | participant_info.*.outcomes.{satisfaction,opponent_likeness} | USEFUL_FOR_RESEARCH_ONLY | Subjective outcomes; no direct action or tone supervision and potential future-information leakage. |
| CaSiNo | participant_info.*.demographics.{age,gender,ethnicity,education} | EXCLUDE_FROM_TRAINING_BY_DEFAULT | Not needed for Russian utterance-to-action parsing; exclude all demographic values by default. |
| CaSiNo | participant_info.*.personality.svo; personality.big-five.* | EXCLUDE_FROM_TRAINING_BY_DEFAULT | Exclude SVO and all five personality measurements; do not use them as target labels, input features or tone proxies. |
| CaSiNo | dialogue_id | USEFUL_FOR_RESEARCH_ONLY | Provenance, error tracing and later grouping only, outside model-visible examples. |
| Job Interview | comments[].body; array order | USEFUL_FOR_NLU | Primary unlabelled negotiation language and local sequence context. |
| Job Interview | users[].role | USEFUL_FOR_NLU | Recruiter/worker role is scenario context; avoid carrying user identifiers into inputs. |
| Job Interview | solutions[].body.* | USEFUL_FOR_NLU | Proposal slots and candidate values, subject to five-issue incompatibility and documented malformed bids. |
| Job Interview | users[].utilities[].{name,type,min,max,options.name,options.names,relatedTo} | USEFUL_FOR_NLU | Issue/value domain and dependency context; future use must respect what the speaker can know. |
| Job Interview | users[].utilities[].weight; options[].weight | USEFUL_FOR_RESEARCH_ONLY | Private utility preferences support economic research, not language-intent labels or inaccessible opponent knowledge. |
| Job Interview | solutions[].accepted; status | USEFUL_FOR_RESEARCH_ONLY | Outcome/event context, not an utterance label. Null is not false/rejected; final status must not leak into turn-time inputs. |
| Job Interview | users[].worker_id; users[].assignment_id | EXCLUDE_FROM_TRAINING_BY_DEFAULT | Crowd-worker and assignment identifiers are unnecessary for NLU. Never expose them to model input; any future grouping must be separate and justified. |
| Job Interview | id; users[].id; comments[].{id,user_id}; solutions[].{id,user_id} | EXCLUDE_FROM_TRAINING_BY_DEFAULT | Raw linkable IDs should not enter training examples. Later provenance joins/local speaker aliases can be stored separately. |
| Job Interview | comments[].created_at; solutions[].created_at | EXCLUDE_FROM_TRAINING_BY_DEFAULT | Absolute timestamps are unnecessary model features; relative ordering/event alignment may be computed only in a later gate. |

Field-level review and Unicode/schema checks are complete. No exhaustive free-text PII screening or redaction was performed; future use of dialogue/reason text requires that review.

## Training suitability and holdout boundary

**CaSiNo:** Useful for preference probing, needs/reasons, contextual acknowledgement and bargaining language; requires later curation, alignment handling, privacy review and Russian/G1 annotation. Not training-ready.

**Job Interview:** Useful for multi-issue proposal language, role/context and structured bid grounding; no supplied dialogue-act labels, five-issue mismatch and session/bid quirks require a separately approved design. Not training-ready.

Both corpora are English. Future Russian utterance-to-canonical-action work requires separately authorized curation, privacy handling and scenario-aware annotation. Tone, objection semantics, multi-intent arbitration and binding complete G1 action payloads remain open; raw strategy labels are not a substitute for these decisions.

A01–A16 remain holdout evaluation material. No case text or hidden acceptance expectations were inspected for training, copied, paraphrased or used for prompt/model tuning. Existing project files were hashed only for the protection audit. Dataset acquisition does not feed the model; the future baseline must use the untouched checkpoint before any fine-tuning.

## Scope and application protection

Before/after SHA-256 audit: **173/174 pre-existing files unchanged; the sole intentional change is .gitignore**. No files were removed or unexpectedly added in the protected scope. Application source, contracts, engine, scenarios, tests, API/UI/database logic, frozen documents and prior gate evidence stayed unchanged. The manifest contains every protected path and both hashes.

The workspace has no .git directory, so no existing Git index could be audited. Both AlagModels/ and AlagDatasets/ were added to .gitignore and confirmed ignored by Git check-ignore using a disposable Git directory under .tmp. No root Git repository was created. All model file sizes/mtimes and small-file hashes are unchanged; all nine raw hashes are unchanged after inspection.

The user-reported G0/G1/G2 PASS baseline (197 tests, 0 failures, 6/6 production Chrome E2E) is preserved by the file audit, not newly re-executed. Full application tests and the browser campaign were not rerun because no application source changed. TARGET_LINUX_RUNTIME_SMOKE remains NOT_VERIFIED.

| Activity | Status |
| --- | --- |
| Training / LoRA / QLoRA | NOT STARTED |
| Baseline inference | NOT STARTED |
| Normalization / translation / tokenization / splits | NOT STARTED |
| Synthetic Russian data | NOT STARTED |
| G3 application integration / free-text NLU | NOT STARTED |
| External LLM API / new ML packages | NOT USED / NOT INSTALLED |

## DEFERRED_CANDIDATES

Deal or No Deal, CraigslistBargain, CRA, Kaggle negotiation datasets, synthetic negotiation datasets and third-party bundles remain NOT_DOWNLOADED. No additional dataset was acquired, and no additional candidate is recommended by this gate.

## Evidence and next gate

Machine-readable receipt: [AI_LOCAL_DATASET_MANIFEST.json](evidence/AI_LOCAL_DATASET_MANIFEST.json). SHA-256: `080a38e3ad8d07846f04ff49f95d7bac5fa2b7a57f02a6597d238976c1906abf`.

Supporting local files: AlagDatasets/manifests/{acquisition.json,model-verification.json,dataset-validation.json,zip-safety.json,protected-before.json,protected-after.json,raw-integrity-audit.json}; acquisition and verification scripts live under AlagDatasets/reports. Source papers are linked above; raw corpus content is never embedded in these receipts.

**Next recommended bounded gate: `LOCAL_QWEN_BASELINE_A01_A16`.** Run the untouched local checkpoint only under that separately authorized gate, with a fixed holdout evaluation procedure, before training. This recommendation does not start inference or authorize normalization.

**STOP — NO TRAINING STARTED.**
