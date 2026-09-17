# Dataset specification

## Authority and scope

Authority is the checked-in `packages/contracts/src/g3.ts`, with ID/term types in `common.ts`, action semantics in `action.ts`, interpretation rules in `packages/ai/src/prompt.ts`, and the public allowlist in `packages/ai/src/context.ts`. `verify_contract.mjs` compares the saved JSON Schema to `z.toJSONSchema(PlayerMoveInterpretationSchema)` and parses **every** target and public context with current Zod source. No production contract or application source is changed.

Supported intents are ask_question, probe_interest, argument, offer, concession, counter_offer, pressure, empathy, objection, clarification, reveal_information, close_attempt, walk_away. Acknowledgement is a factual binding within an available intent (here empathy), not a new intent. Explicit acceptance is close_attempt. Personal or conditional threats are pressure/threat; respectful boundaries are objection/respectful_firm; final termination is walk_away.

All schema fields are mandatory, including nulls and empty arrays. `factIds` is at most two actual references; catalogue presence alone is not evidence. An argument requires a supplied claim, exactly its known supporting facts, and language supporting its condition. Facts without an explicitly named topic do not acquire a guessed topic. A multi-issue package with no singled-out topic leaves both topics null. Single-topic questions, boundaries, pressure and empathy bind a named public topic when one exists. Two-topic questions preserve their order.

Binding intents require complete issue coverage unless clarification is needed. Alternatives, ranges, approximation, mutually incompatible values, out-of-domain values and omissions retain only unambiguous terms. If no term is supplied, the draft is null and clarification is required. Conditional terms are present in the full draft. No value is rounded, negated into a positive binding, or chosen from ambiguous alternatives.

counter_offer and close_attempt always bind the exact active offer ID, as required by the existing semantic validator. Without a resolvable active offer, a referential attempt becomes clarification with a null target, preserving any explicitly stated term. The schema cannot represent an unresolved non-null offer reference. Only explicit retention language permits inheritance. A meaning question to the counterpart uses clarification with `needsClarification=false`; ambiguity in the player's own action uses `true` and a short Russian question.

Null discipline has contract-required exceptions: an accepted argument cannot have null argument/facts, and accepted counter_offer/close_attempt records cannot have null targets. These are not invented optional bindings. All other optional fields have substantial null/empty slices, including fully unresolved offers and concessions.

The interpreter never computes feasibility, utility, reservation, policy, social state, score, hidden facts or outcomes. Even an economically poor or impossible offer can be valid interpretation supervision: the deterministic engine owns that decision. All commitments remain drafts.

## Public fixtures

Ten language domains cover procurement, workload, logistics, project scope/deadline, service contracts, B2B pricing, hiring, resource allocation, support and commercial rent. Procurement/workload are **S1-like/S2-like**, with familiar issue structures and entirely independently authored values and public briefs. They are not production S1/S2 sessions. No hidden production fact, private participant briefing, interest, utility table, policy or witness trace is imported.

Contexts use descriptive, semi-opaque and opaque identifiers. Labels and allowed value phrases carry meaning, not IDs. Three active-offer variants expose different terms and opaque number-like offer IDs. Additional states have no active offer, no arguments or no topic for the first issue. In particular, PRICE can exist without any price topic. Multiple known facts and similar argument labels require selective binding.

Registry entries wrap a schema-valid `publicContext` with fixture-only domain, ID style, split and issue/topic correspondence metadata. Fixture metadata never enters the SFT prompt. The compiler preserves briefs, player role/briefing, issue labels/units/value IDs and labels, topics, facts, acknowledgement eligibility, argument labels/facts/equality conditions, and active offer ID/terms. Revision, turn counters, proposer and supersedes metadata are omitted from the compact input because they do not resolve these one-turn interpretation labels. Ordered=false and quantity=null are invariant for these fixtures; no non-null quantity is discarded.

## Generation and splits

Root seed: 20260917. Version: ru-v1.0.0. Each row records source type PROJECT_SYNTHETIC, generator version, seed, semantic family, surface family, context and case index. Stable SHA-256-derived local RNGs make row generation independent of process/global RNG state. Semantic truth is computed before rendering. Evidence spans are then filled from authored support markers after surface/noise transformation. Validation replays the authored realization, so edits to text or support intervals cannot pass merely by retaining a schema-valid target.

A family is a concrete discourse and grounding recipe, not an entire intent. Every surface variant, slot substitution and noisy sibling of that recipe stays in its assigned split. The generator does not shuffle individual paraphrases into splits. Contrast branches share a single group. Shared catalogue labels, grammatical slot formatting and broad contract operations are not independent supervised examples.

TRAIN uses 140 contexts, DEV 20 and INTERNAL_TEST 20, with disjoint context IDs. The tuning eval deliberately reuses DEV contexts, with separately authored constructions. It has no training context or training family. All 108 contrast pairs stay in TRAIN. The whole `dev.offer.memo` family was quarantined after the lexical cross-split review; its quota was reassigned to existing DEV families. No threshold was relaxed to preserve counts.

Class counts follow 9/7/9/12/10/9/9/6/5/7/6/5/6 percent for ask_question/probe_interest/argument/offer/counter_offer/concession/objection/pressure/empathy/clarification/reveal_information/close_attempt/walk_away. Every training intent has at least 400 records. Critical commitments have more construction families. The separate 304-case tuning eval oversamples offer ambiguity, objections, counter-offer inheritance and clarification/safety.

Business, neutral, concise and conversational frames are balanced. Some quantities use words, others digits. About 6% of records have one bounded noise transformation (case, punctuation, abbreviation, one typo, emoji or dash punctuation). Most offers intentionally use readable labelled term lists: reliable value binding is the primary goal. This is a synthetic language fixture corpus, not a claim to represent the full distribution of spontaneous Russian negotiation.

## Evidence, audit and privacy

Offsets follow the existing contract exactly: JavaScript UTF-16 units, start inclusive and end exclusive. Emoji occupy two units. Punctuation remains part of the unchanged input. Authored 1–4 support spans cover the interpreted clauses, excluding polite wrappers when they carry no meaning; argument support is contained in an evidence span. Python regression tests cover Cyrillic, digits, punctuation, en/em dashes and emoji; Node slices every actual evidence span.

Exact IDs, canonical examples and utterance/context pairs are checked exhaustively. Families, contrasts and main context splits are checked exhaustively. Near-duplicate checks query every row using eight rare token bigrams and bounded candidate postings, then inspect up to 24 general and 24 cross-split neighbours with token-bigram and character-trigram Jaccard. This is a bounded audit, not an exhaustive semantic equivalence proof. Identical utterances in distinct contexts are retained deliberately to teach copying different IDs and offers.

Holdout auditing hashes A01–A16 before/after and compares all main/eval utterances to its text only. Fixed thresholds: normalized exact match, token Jaccard >=0.60, token-bigram Jaccard >=0.38, or character SequenceMatcher ratio >=0.78. The authoring-source snapshot is recorded before text access. The nearest row for every holdout and the 20 highest family neighbours are manually reviewed. Generic overlap in contract operations is distinguished from a copied/paraphrased holdout construction in the review notes. Holdout labels, individual failures and raw model outputs never generate cases. No prompt tuning, training or inference is involved.

Privacy uses allowlisted context fields, strict target schemas, independently authored fictional context text, and bounded email/phone/address/worker/demographic/personality scans. Injection text may **ask** for private information; targets and contexts contain none. The scanner is not a general PII detector and no independent human annotation campaign was performed. Review is Codex's deterministic sample review, with exact sample IDs and limitations recorded.

## External language research and licensing

`linguistic_patterns.py` reads only English language fields in immutable source files, computes overlapping regex counts, and exports aggregate categories. It never maps external strategy/act labels to targets. Generation imports neither external data nor the holdout. The English counts are rough research indicators of probing, proposals, reasons, coordination, concession and multi-issue phrasing, not gold annotations. No corpus translation or dialogue adaptation occurred. Preserve the source attribution in README and the existing source notices. Project synthetic license status remains NOT_ASSIGNED.

## Future training boundary

`next_gate.json` estimates hardware constraints using the recorded model parameter count, current installed stack, measured tokenizer lengths and official documentation. It does not predict duration or certify QLoRA feasibility. No TRL, PEFT, bitsandbytes, Unsloth, LLaMA-Factory or Axolotl is installed. INTERNAL_TEST is locked and cannot be exported through the training compiler. A01–A16 remains a separate final holdout. Use only TRAIN and DEV/the explicitly tuning-allowed eval for future iteration.
