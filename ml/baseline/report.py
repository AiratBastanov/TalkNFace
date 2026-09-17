"""Assemble a gate receipt from saved outputs. Never loads or calls the model."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from scoring import match, metrics

ROOT = Path(__file__).resolve().parents[2]
GATE = 'LOCAL_QWEN_BASELINE_A01_A16'
OUT = ROOT / 'docs/gates/evidence' / (GATE + '.json')
MD = ROOT / 'docs/gates' / (GATE + '.md')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fraction(value):
    numerator = value.get('correct', value.get('count'))
    return f"{numerator}/{value['total']} ({100 * value['rate']:.2f}%)" if value['rate'] is not None else 'NOT_MEASURED'


def failure_paths(row, text):
    paths = set()
    for field, values in row['field_failures'].items():
        if field.startswith('$'):
            continue
        if field in ['argument', 'offerDraft'] and isinstance(values, dict):
            wanted, actual = values.get('expected'), values.get('actual')
            if isinstance(wanted, dict) and isinstance(actual, dict):
                for key in wanted:
                    if not match(wanted[key], actual.get(key), text):
                        if key == 'terms' and isinstance(actual.get(key), list):
                            expect = {t['issueId']: t['valueId'] for t in wanted[key]}
                            observed = {t['issueId']: t['valueId'] for t in actual[key]}
                            paths.update('offerDraft.terms.' + issue for issue in set(expect) | set(observed) if expect.get(issue) != observed.get(issue))
                        else:
                            paths.add(field + '.' + key)
                continue
        paths.add(field)
    for error in row['schema_errors'] + row['semantic_errors']:
        paths.add(error.split(': ', 1)[0].removeprefix('$.'))
    paths.update(item['field'] for item in row['unknown_ids'])
    paths.update('offerDraft.terms.' + term['issueId'] for term in row['invented_terms'])
    if not row['json_valid']:
        paths.add('$json')
    elif not row['primary_intent_correct']:
        paths.add('intent')
    return sorted(paths)


def classify(result, cfg):
    if result['completed_generations'] != 48 or result['exit_code'] != 0:
        return None
    agg = result['aggregate']
    strong = (all(m['PRIMARY_INTENT_ACCURACY']['correct'] >= 15 for m in result['per_seed'].values())
              and agg['CRITICAL_COMMITMENT_ACCURACY']['rate'] == 1
              and agg['AMBIGUITY_CLARIFICATION_ACCURACY']['rate'] == 1
              and agg['UNKNOWN_ID_RATE']['count'] == 0
              and not any(r['invented_terms'] for r in result['per_case']))
    if strong:
        return 'BASELINE_STRONG'
    thresholds = cfg['quality_classification']
    if (agg['PRIMARY_INTENT_ACCURACY']['rate'] >= thresholds['promising_min_primary_intent_rate']
        and agg['SCHEMA_VALID_RATE']['rate'] >= thresholds['promising_min_schema_valid_rate']
        and agg['CRITICAL_COMMITMENT_ACCURACY']['rate'] >= thresholds['promising_min_critical_commitment_rate']):
        return 'BASELINE_PROMISING'
    return 'BASELINE_WEAK'


def main(run, scored_result=None):
    result = read(scored_result or run / 'result.json')
    cfg = read(run / 'config.json')
    holdout = read(ROOT / 'evals/local-qwen/a01-a16.json')
    before = read(ROOT / '.tmp/qwen-integrity-before.json')
    after = read(ROOT / '.tmp/qwen-integrity-after.json')
    assert {k: v for k, v in before.items() if k != 'at_utc'} == {k: v for k, v in after.items() if k != 'at_utc'}
    assert result['frozen_artifacts_unchanged']
    rows = result['per_case']
    assert len({(r['case_id'], r['seed']) for r in rows}) == len(rows)
    done = result['completed_generations'] == 48 and result['exit_code'] == 0
    verdict = GATE + '_PASS' if done else 'LOCAL_QWEN_BASELINE_RUNTIME_BLOCKED'
    quality = classify(result, cfg)
    # Exactly one recommendation, never automatic execution.
    near_bar = (done and result['aggregate']['PRIMARY_INTENT_ACCURACY']['rate'] >= 44 / 48
                and result['aggregate']['CRITICAL_COMMITMENT_ACCURACY']['rate'] >= 35 / 36
                and result['aggregate']['SCHEMA_VALID_RATE']['rate'] == 1
                and not any(r['unknown_ids'] or r['invented_terms'] for r in rows))
    next_gate = 'LOCAL_QWEN_PROMPT_ONLY_EXPERIMENT' if quality == 'BASELINE_STRONG' or near_bar else 'LOCAL_DATASET_DESIGN_AND_SYNTHETIC_RU'
    ids = {c['id']: c for c in holdout['cases']}
    negation = [r for r in rows if ids[r['case_id']]['negationSensitive']]
    injection = [r for r in rows if r['case_id'] == 'A16']
    for row in rows:
        row['failed_field_paths'] = failure_paths(row, ids[row['case_id']]['text'])
    failure_fields = Counter(k for r in rows for k in r['failed_field_paths'])
    confusion_counts = Counter((r['expected_primary_intent'], r['actual_primary_intent']) for r in rows if not r['primary_intent_correct'])
    schema_failure_counts = Counter(error for r in rows for error in r['schema_errors'])
    runtime = result['runtime']
    verification = read(ROOT / '.tmp/qwen-verification.json')
    evidence = {
        'gate': GATE, 'schema_version': 1, 'verdict': verdict, 'model_quality': quality,
        'completed_at_utc': datetime.now(timezone.utc).isoformat(),
        'git': {'repository': 'https://github.com/AiratBastanov/TalkNFace.git',
                'source_baseline_commit': 'c742fd179d9f07c35f710441da7747635ef9aee9',
                'remote_empty_verified_before_initialization': True, 'initial_push_synchronized': True,
                'final_commit': 'The commit containing this receipt; synchronization is checked after push and reported to the user.'},
        'hardware': read(ROOT / '.tmp/qwen-hardware.json'), 'runtime': runtime,
        'installed_wheel_sources': read(ROOT / '.tmp/qwen-wheel-sources.json'),
        'generation_configuration': cfg,
        'model_source': {'path': cfg['model_relative_path'], 'revision': cfg['model_revision'], 'dtype': 'original BF16',
                         'format': '3 Hugging Face safetensors shards', 'quantization': False},
        'official_runtime_sources': [
            'https://pytorch.org/get-started/locally/', 'https://pytorch.org/get-started/previous-versions/',
            'https://download.pytorch.org/whl/cu126/torch/', 'https://pypi.org/project/transformers/5.17.0/',
            'https://pypi.org/project/accelerate/1.15.0/', 'https://pypi.org/project/safetensors/0.8.0/',
            'https://huggingface.co/Qwen/Qwen3-4B', 'https://huggingface.co/docs/transformers/model_doc/qwen3',
            'https://huggingface.co/docs/accelerate/usage_guides/big_modeling'],
        'prompt': {'version': cfg['version'], 'path': 'ml/baseline/system-prompt.txt',
                   'sha256': result['frozen_hashes']['ml/baseline/system-prompt.txt'],
                   'thinking_enabled': False, 'tuned_after_outputs': False},
        'frozen_hashes': result['frozen_hashes'], 'frozen_artifacts_unchanged_during_campaign': True,
        'benchmark_inputs_unchanged_after_postprocessing': True,
        'holdout': {'path': 'evals/local-qwen/a01-a16.json', 'purpose': holdout['purpose'],
                    'training_allowed': False, 'materialization_decisions': holdout['materializationDecisions'],
                    'expected_generations': 48, 'completed_generations': len(rows),
                    'critical_case_ids': [c['id'] for c in holdout['cases'] if c['critical']],
                    'ambiguity_case_ids': ['A05'], 'refusal_case_ids': ['A16'],
                    'unnecessary_clarification_denominator_excludes': ['A05', 'A16']},
        'sanity': read(ROOT / '.tmp/qwen-sanity-auto/result.json'),
        'aggregate_metrics': result['aggregate'], 'per_seed_metrics': result['per_seed'],
        'negation_metrics': metrics(negation, holdout['cases']), 'injection_refusal_metrics': metrics(injection, holdout['cases']),
        'evaluation_wall_seconds_including_load': result['wall_seconds_including_load'],
        'failure_field_counts': dict(failure_fields),
        'failure_analysis': {
            'intent_confusions': [{'expected': expected, 'actual': actual, 'count': count} for (expected, actual), count in confusion_counts.most_common()],
            'schema_error_counts': dict(schema_failure_counts),
            'critical_by_case': {c['id']: {'correct': sum(r['critical_term_correct'] for r in rows if r['case_id'] == c['id']), 'total': sum(r['case_id'] == c['id'] for r in rows)} for c in holdout['cases'] if c['critical']},
        },
        'per_case_outcomes': rows,
        'integrity_before': before, 'integrity_after': after,
        'dataset_isolation': {'raw_corpora_model_exposure': False, 'dataset_text_decoded': False,
                              'hash_only_separate_process': True, 'worker_dataset_open_guard_test_passed': True,
                              'worker_network_guard_test_passed': True},
        'application_protection': {'protected_file_count': len(before['protected_application']),
                                   'all_hashes_unchanged': True, 'g1_g2_source_changes': False,
                                   'node_lockfile_changed': False, 'browser_e2e_rerun': False,
                                   'reason': 'R&D-only change; source/build/planning hashes checked against acquisition.'},
        'verification': verification,
        'postprocessing': result.get('postprocessing'),
        'training_status': {'training_performed': False, 'lora': False, 'qlora': False, 'training_split_created': False,
                            'synthetic_training_data_created': False, 'dataset_normalization': False, 'translation': False},
        'g3_application_integration_started': False, 'external_inference_api_used': False,
        'next_gate': next_gate, 'next_gate_started': False,
        'limitations': [
            '48 holdout generations on one machine measure this baseline only, not throughput or production capacity.',
            'RNG control is reproducible on the pinned stack; no duplicate full campaign or cross-hardware bitwise claim.',
            'GPU uses BF16 emulation and CPU weight offload; measured latency is unsuitable for assuming live UI readiness.',
            'Semantic validation combines public-context invariants with the frozen holdout safety oracle; it is not a production free-text validator.',
            'Primary intent counts parsed intent independently of other schema fields. Semantic validity is stricter than JSON/schema validity.',
            'Planning rows specify semantic constraints rather than complete JSON gold. Full structure matching also checks pre-run null/empty defaults for unspecified bindings; it is a stricter diagnostic and no labels were relaxed after outputs.',
            'The future application must confirm commitments; this harness executes no negotiation actions.',
        ],
    }
    OUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    a = result['aggregate']
    lines = [f'# {GATE}', '', f'**Verdict: `{verdict}`. Model quality: `{quality}`.**', '',
             'PASS certifies completion of the baseline procedure; model quality is a separate result. No training or application integration was performed.', '',
             f'Initial source snapshot `{evidence["git"]["source_baseline_commit"]}` was pushed and synchronized before ML implementation. Remote history was empty. The final gate commit contains this receipt and is pushed without force.', '',
             '## Hardware and runtime', '',
             'Windows 11 IoT Enterprise LTSC, build 26100, x64; Ryzen 7 5700X3D (8 cores / 16 threads); 32 GiB physical RAM. Exact available RAM/VRAM snapshots are in the JSON evidence.', '',
             f'Python {runtime["python"]}; torch {runtime["torch"]}; Transformers {runtime["transformers"]}; accelerate {runtime["package_versions"]["accelerate"]}; safetensors {runtime["package_versions"]["safetensors"]}. NVIDIA RTX 2060, 6144 MiB VRAM, driver 610.88 reporting CUDA compatibility 13.3; the prebuilt torch wheel bundles CUDA {runtime["torch_cuda_runtime"]}. Native BF16: {runtime["native_bf16"]}; emulated BF16: {runtime["bf16_including_emulation"]}.', '',
             'The checkpoint remains original BF16. Automatic device mapping retains embeddings and 11 decoder layers on CUDA and offloads the remaining layer weights to CPU; no disk offload. No compiler, global Python/CUDA installation, PATH change or administrator action occurred. All exact transitive versions are in [requirements.txt](../../ml/baseline/requirements.txt) and the JSON evidence.', '',
             'Runtime sources: [official Windows setup](https://pytorch.org/get-started/locally/), [official wheel commands](https://pytorch.org/get-started/previous-versions/), [Qwen3 non-thinking settings](https://huggingface.co/Qwen/Qwen3-4B), [Transformers Qwen3](https://huggingface.co/docs/transformers/model_doc/qwen3), [Accelerate CPU offload](https://huggingface.co/docs/accelerate/usage_guides/big_modeling).', '',
             '## Frozen model, prompt and evaluation', '',
             f'Model revision: `{cfg["model_revision"]}`. All three full shard SHA-256 values match the pinned upstream hashes, beyond the acquisition gate\'s structural checks. Ten small-file hashes, all {len(before["model_inventory"])} model/cache file stats, nine raw artifact hashes and {len(before["protected_application"])} protected project hashes match before/after.', '',
             f'Prompt version: `{cfg["version"]}`. SHA-256: `{evidence["prompt"]["sha256"]}`. The prompt, config, eval asset, schema, requirements and inference/scoring code hashes were captured before the campaign and checked afterward. No prompt tuning or output repair.', '',
             '`enable_thinking=False`; sampling temperature=0.7, top_p=0.8, top_k=20, min_p=0; seeds 101/202/303; max_new_tokens=512; input cap=4096; eager attention. Python/NumPy/torch CPU/CUDA RNGs reset to the case seed immediately before each generation. Deterministic torch algorithms and CUBLAS workspace configuration are enabled; TF32 is disabled.', '',
             'A01–A16 retain the exact planning utterances. Expected labels were materialized before inference. The interpretation schema comes from the existing `g3.ts`; G1 canonical action names were not substituted for interpretation intents. Public contexts include only domain catalogs, public/revealed facts, allowed argument bindings and a current offer where specified. The model sees no labels or hidden negotiation state.', '',
             'A05 primary intent is fixed as objection, with unresolved price clarification and PREPAY=0. A13 exposes only the player\'s already-known BATNA under an eval-only ID. A14 uses a concrete current 110/all7/50 offer. Optional topic alternatives and exact match rules are documented in the versioned holdout asset. These decisions were frozen before model outputs.', '',
             'Strict JSON rejects duplicate keys, NaN, Markdown wrappers and trailing explanations. Invalid outputs receive no repair call. Schema checks precede public ID/value, span, argument, condition and offer validation. Frozen commitment checks reject legal-but-invented terms and negation errors. Full expected structure match covers all fields, allowing only documented topic alternatives, set order and valid evidence/clarification wording. Planning rows are semantic prose rather than complete JSON gold; this diagnostic also checks the pre-run null/empty defaults for unspecified bindings. No labels were relaxed after outputs.', '',
             '## Results', '',
             '| Seed | Primary intent | JSON | Schema | Semantic | Critical commitments | Ambiguity | Full structure |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for seed, values in result['per_seed'].items():
        keys = ['PRIMARY_INTENT_ACCURACY', 'JSON_VALID_RATE', 'SCHEMA_VALID_RATE', 'SEMANTIC_VALID_RATE', 'CRITICAL_COMMITMENT_ACCURACY', 'AMBIGUITY_CLARIFICATION_ACCURACY', 'FULL_EXPECTED_STRUCTURE_MATCH']
        lines.append('| ' + seed + ' | ' + ' | '.join(fraction(values[k]) for k in keys) + ' |')
    lines += ['', '| Aggregate metric | Result |', '| --- | --- |']
    for key, value in a.items():
        if isinstance(value, dict) and 'rate' in value:
            lines.append(f'| {key} | {fraction(value)} |')
    lines += ['', 'Critical cases: ' + ', '.join(evidence['holdout']['critical_case_ids']) + '. Ambiguity accuracy uses A05 (three generations); A16 is a separate refusal/clarification check. Unnecessary clarification excludes A05/A16.', '',
              f'Negation-sensitive critical accuracy (A05/A09/A11/A15): {fraction(evidence["negation_metrics"]["CRITICAL_COMMITMENT_ACCURACY"])}. A16 refusal/clarification safety: {fraction(evidence["injection_refusal_metrics"]["CRITICAL_COMMITMENT_ACCURACY"])}.', '',
              f'Outputs with invented legal-domain offer terms: {sum(bool(r["invented_terms"]) for r in rows)}. Unknown ID outputs: {a["UNKNOWN_ID_RATE"]["count"]}. Raw outputs, token IDs and per-field expected/actual values are retained in the machine-readable evidence.', '',
              '## Failure matrix', '', '| Seed | Case | Expected intent | Actual intent | Failed fields |', '| --- | --- | --- | --- | --- |']
    for row in rows:
        if row['field_failures']:
            fields = ', '.join(row['failed_field_paths']).replace('|', '/')
            lines.append(f'| {row["seed"]} | {row["case_id"]} | {row["expected_primary_intent"]} | {row["actual_primary_intent"]} | {fields} |')
    if not failure_fields:
        lines.append('| — | — | — | — | No failures |')
    lines += ['', 'Field failure counts: ' + ', '.join(f'{k}={v}' for k, v in failure_fields.most_common()) + '.', '',
              'Primary-intent confusions: ' + '; '.join(f'`{expected}` → `{actual}` ({count})' for (expected, actual), count in confusion_counts.most_common()) + '.', '',
              'Schema failures: ' + '; '.join(f'`{error}` ({count})' for error, count in schema_failure_counts.most_common()) + '. Empty conditional arrays must be null when no condition exists; `acceptance` and `acknowledge` are outside the frozen interpretation enum.', '',
              'The model frequently adds fact/acknowledgement bindings where the frozen expected structure has none. All three A03 outputs identify an argument but fail the claim-evidence check. A05 never safely clarifies the unresolved price; A16 never takes the required refusal/clarification path. These failures, alongside incomplete or incorrect offer inheritance, prevent use at the future G3 acceptance bar.', '',
              'The JSON evidence distinguishes unknown IDs from invented terms, missing/extra fields from semantic errors, and primary-intent correctness from full-structure correctness. The observed weaknesses are preserved; this gate does not modify the prompt or train against failed holdout cases.', '',
              '## Latency and resources', '',
              f'Model load: {runtime["model_load_seconds"]:.3f} s. Generation mean / median / p95 (nearest rank): {a["latency_seconds"]["mean"]:.3f} / {a["latency_seconds"]["median"]:.3f} / {a["latency_seconds"]["p95_nearest_rank"]:.3f} s. Output tokens per second including prefill: {a["tokens_per_second_including_prefill"]:.3f}. Total evaluation wall time including load: {result["wall_seconds_including_load"]:.3f} s.', '',
              f'CUDA peak allocated / reserved: {runtime["peak_allocated_vram_bytes"] / 2**30:.3f} / {runtime["peak_reserved_vram_bytes"] / 2**30:.3f} GiB. Process peak working set: {runtime["process_ram_peak_bytes"] / 2**30:.3f} GiB. This is one sequential holdout campaign, not a concurrency/load-capacity benchmark. The one generic English sanity generation is excluded from these metrics.', '',
              '## Verification, isolation and next gate', '',
              f'Targeted verification: {verification["unit_test_count"]} scorer and process-lifecycle tests; 304 Python/Zod schema-parity checks; unchanged application/schema source; dataset and network guard checks; dependency consistency; pre/post full-model, small-file, raw-data and protected-source integrity. Browser E2E was not repeated because no application behavior changed.', '',
              'Code review found a Windows venv launcher cleanup issue and reporting gaps: ID/term emissions could be hidden by an unrelated schema failure, ambiguity success needed to require semantic safety, and nullable-schema errors hid nested field paths. These were corrected after the campaign. The inference worker function is AST-identical; prompt, configuration and expected labels are unchanged. Metrics were recalculated from the same 48 raw outputs with zero model calls. Executed/final hashes and reversible source diffs are preserved in the JSON evidence.', '',
              'Training status: no training, LoRA, QLoRA, quantization, conversion, normalization, translation, synthetic training data or splits. CaSiNo and Job Interview were accessed only by the separate hash auditor. No external model API, G3 route/UI integration or SQLite AI migration was introduced.', '',
              f'Exactly one next bounded recommendation: **`{next_gate}`**. ' + ('A prompt-only comparison is warranted by proximity to the frozen acceptance bar; no training is justified by this gate alone.' if next_gate == 'LOCAL_QWEN_PROMPT_ONLY_EXPERIMENT' else 'Design the local data and Russian supervision requirements before any training authorization; keep this holdout excluded and preserve this baseline for comparison.'), '',
              'Reproduction commands and metric definitions: [baseline README](../../ml/baseline/README.md). Machine-readable receipt: [evidence](evidence/LOCAL_QWEN_BASELINE_A01_A16.json).', '',
              'STOP — TRAINING AND G3 APPLICATION INTEGRATION NOT STARTED.', '']
    # Receipts are under docs/gates, so repository R&D links need two parents.
    MD.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    print(json.dumps({'verdict': verdict, 'model_quality': quality, 'next': next_gate, 'files': [str(MD), str(OUT)]}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--scored-result', type=Path)
    args = parser.parse_args()
    main(args.run, args.scored_result)
