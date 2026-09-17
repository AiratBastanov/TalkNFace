"""Bounded, offline BF16 inference; one model load per worker, no output repair."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
EVAL = ROOT / 'evals/local-qwen/a01-a16.json'
SCHEMA = ROOT / 'evals/local-qwen/interpretation.schema.json'
FROZEN_FILES = [HERE / 'system-prompt.txt', HERE / 'config.json', HERE / 'requirements.txt',
                EVAL, SCHEMA, HERE / 'run.py', HERE / 'scoring.py', HERE / 'lifecycle.py']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def now():
    return datetime.now(timezone.utc).isoformat()


def isolate():
    def audit(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            target = os.fsdecode(args[0]).replace('\\', '/').lower()
            if 'alagdatasets' in target:
                raise PermissionError('Dataset access is forbidden in inference worker')
        if event == 'socket.connect':
            raise PermissionError('Network access is forbidden in inference worker')
    sys.addaudithook(audit)


def worker(mode, output):
    isolate()
    import torch
    import transformers
    import psutil
    from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed
    cfg = json.loads((output / 'config.json').read_text(encoding='utf-8'))
    torch.set_num_threads(cfg['cpu_threads'])
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    cuda = torch.cuda.is_available()
    runtime = {'python': platform.python_version(), 'executable': sys.executable, 'platform': platform.platform(),
               'torch': torch.__version__, 'transformers': transformers.__version__, 'cuda_available': cuda,
               'torch_cuda_runtime': torch.version.cuda, 'cpu_threads': torch.get_num_threads(),
               'ram_available_before_load_bytes': psutil.virtual_memory().available,
               'dataset_worker_access_guard': True, 'network_worker_access_guard': True,
               'package_versions': {d.metadata['Name']: d.version for d in importlib.metadata.distributions()}}
    if cuda:
        runtime.update(gpu_name=torch.cuda.get_device_name(0), capability=list(torch.cuda.get_device_capability(0)),
                       native_bf16=torch.cuda.is_bf16_supported(including_emulation=False),
                       bf16_including_emulation=torch.cuda.is_bf16_supported())
        runtime['cuda_free_total_before_load_bytes'] = list(torch.cuda.mem_get_info())
        torch.cuda.reset_peak_memory_stats()
    write_json(output / 'runtime.json', runtime)
    placement = cfg['device_strategy']
    if placement == 'auto_cpu_offload':
        if not cuda:
            raise RuntimeError('CUDA offload selected but CUDA is unavailable')
        # Tiny operation capability check, not a second model generation.
        probe = torch.ones((8, 8), dtype=torch.bfloat16, device='cuda')
        assert (probe @ probe).dtype == torch.bfloat16
        torch.cuda.synchronize()
        del probe
    model_dir = ROOT / cfg['model_relative_path']
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True, trust_remote_code=False)
    options = {'dtype': torch.bfloat16, 'local_files_only': True, 'trust_remote_code': False,
               'attn_implementation': cfg['attention_implementation'], 'use_safetensors': True}
    if placement == 'auto_cpu_offload':
        options.update(device_map='auto', max_memory={0: f"{cfg['gpu_weight_budget_mib']}MiB", 'cpu': f"{cfg['cpu_weight_budget_gib']}GiB"},
                       offload_state_dict=False)
    else:
        options.update(device_map={'': 'cpu'})
    started = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(str(model_dir), **options)
    model.eval()
    if cuda:
        torch.cuda.synchronize()
    load_seconds = time.perf_counter() - started
    assert {p.dtype for p in model.parameters()} == {torch.bfloat16}, 'Non-BF16 parameter detected'
    devices = getattr(model, 'hf_device_map', {'': str(model.device)})
    assert 'disk' not in devices.values(), 'Disk offload not authorized by selected strategy'
    runtime.update(model_load_seconds=load_seconds, device_map={k: str(v) for k, v in devices.items()},
                   parameter_dtype='torch.bfloat16', parameter_count=sum(p.numel() for p in model.parameters()),
                   original_checkpoint_loaded=True, quantized=False, attention_implementation=cfg['attention_implementation'])
    write_json(output / 'runtime.json', runtime)
    print(json.dumps({'event': 'MODEL_LOADED', 'seconds': load_seconds, 'device_strategy': placement}), flush=True)
    system = (HERE / 'system-prompt.txt').read_text(encoding='utf-8').strip()
    inputs = json.loads((output / 'inputs.json').read_text(encoding='utf-8'))
    rows_file = output / 'generations.jsonl'
    begin = time.perf_counter()
    for item in inputs:
        if mode == 'sanity':
            messages = [{'role': 'system', 'content': 'Return exactly one JSON object. No explanation.'},
                        {'role': 'user', 'content': 'Return the JSON object {"ok":true}.'}]
        else:
            messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps(
                {'publicContext': item['publicContext'], 'utterance': item['text'],
                 'outputSchema': json.loads(SCHEMA.read_text(encoding='utf-8'))}, ensure_ascii=False, separators=(',', ':'))}]
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        # The official non-thinking hard switch supplies the empty thinking block in the input prefix.
        assert rendered.rstrip().endswith('<think>\n\n</think>'), 'Non-thinking chat prefix changed'
        encoded = tokenizer(rendered, return_tensors='pt')
        count = int(encoded.input_ids.shape[-1])
        assert count <= cfg['max_input_tokens'], f'Input exceeds frozen context bound: {count}'
        input_device = model.get_input_embeddings().weight.device
        encoded = encoded.to(input_device)
        options = dict(cfg['generation'])
        if mode == 'sanity':
            options['max_new_tokens'] = cfg['sanity_max_new_tokens']
        options['max_time'] = cfg['per_generation_timeout_seconds']
        set_seed(item['seed'])
        if cuda:
            torch.cuda.synchronize()
        start = time.perf_counter()
        with torch.inference_mode():
            generated = model.generate(**encoded, **options, logits_to_keep=1)
        if cuda:
            torch.cuda.synchronize()
        seconds = time.perf_counter() - start
        ids = generated[0, count:].tolist()
        eos = model.generation_config.eos_token_id
        eos = eos if isinstance(eos, list) else [eos]
        content_ids = ids[:-1] if ids and ids[-1] in eos else ids
        raw = tokenizer.decode(content_ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
        if '<think>' in raw or '</think>' in raw:
            raise RuntimeError('Unexpected reasoning delimiter despite disabled thinking; content not recorded')
        memory = psutil.Process().memory_info()
        row = {'case_id': item['case_id'], 'seed': item['seed'], 'input_token_count': count,
               'output_token_count': len(ids), 'output_content_token_count': len(content_ids),
               'output_token_ids': ids, 'latency_seconds': seconds,
               'tokens_per_second_including_prefill': len(ids) / seconds,
               'ended_with_eos': bool(ids and ids[-1] in eos),
               'generation_token_limit_reached': len(ids) == options['max_new_tokens'],
               'input_sha256': hashlib.sha256(rendered.encode('utf-8')).hexdigest(),
               'process_ram_peak_bytes': getattr(memory, 'peak_wset', memory.rss), 'raw_model_output': raw}
        with rows_file.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            stream.flush()
        print(json.dumps({'event': 'GENERATION_COMPLETED', 'case_id': item['case_id'], 'seed': item['seed'],
                          'seconds': seconds, 'output_tokens': len(ids)}), flush=True)
        del generated, encoded
    runtime.update(generation_campaign_seconds=time.perf_counter() - begin,
                   process_ram_peak_bytes=getattr(psutil.Process().memory_info(), 'peak_wset', None))
    if cuda:
        runtime.update(peak_allocated_vram_bytes=torch.cuda.max_memory_allocated(),
                       peak_reserved_vram_bytes=torch.cuda.max_memory_reserved())
    write_json(output / 'runtime.json', runtime)


def launch(mode, output):
    from scoring import metrics, score
    from lifecycle import terminate_owned_tree
    cfg = json.loads((HERE / 'config.json').read_text(encoding='utf-8'))
    data = json.loads(EVAL.read_text(encoding='utf-8'))
    assert data['purpose'] == 'HOLDOUT_EVAL_ONLY' and data['training_allowed'] is False
    output.mkdir(parents=True, exist_ok=False)
    frozen = {p.relative_to(ROOT).as_posix(): digest(p) for p in FROZEN_FILES}
    write_json(output / 'frozen.json', {'at_utc': now(), 'files': frozen})
    write_json(output / 'config.json', cfg)
    inputs = [{'case_id': c['id'], 'seed': seed, 'text': c['text'], 'publicContext': c['publicContext']}
              for seed in cfg['seeds'] for c in data['cases']] if mode == 'eval' else [{'case_id': 'SANITY', 'seed': cfg['sanity_seed']}]
    write_json(output / 'inputs.json', inputs)
    env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
               TOKENIZERS_PARALLELISM='false', HF_HOME=str(ROOT / '.tmp/qwen-cache/hf'),
               TORCH_HOME=str(ROOT / '.tmp/qwen-cache/torch'), CUBLAS_WORKSPACE_CONFIG=':4096:8',
               PYTHONHASHSEED='0', PYTHONUTF8='1', HF_HUB_DISABLE_PROGRESS_BARS='1')
    start = time.perf_counter()
    timeout = cfg['sanity_timeout_seconds' if mode == 'sanity' else 'evaluation_timeout_seconds']
    with (output / 'worker.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, str(__file__), '_worker', '--mode', mode, '--output', str(output)],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        write_json(output / 'process.json', {'pid': process.pid, 'start_utc': now(), 'mode': mode, 'timeout_seconds': timeout})
        try:
            exit_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            terminate_owned_tree(process)
            exit_code = 'TIMEOUT'
    elapsed = time.perf_counter() - start
    assert frozen == {p.relative_to(ROOT).as_posix(): digest(p) for p in FROZEN_FILES}, 'FROZEN_ARTIFACT_DRIFT'
    rows = [json.loads(line) for line in (output / 'generations.jsonl').read_text(encoding='utf-8').splitlines()] if (output / 'generations.jsonl').exists() else []
    result = {'mode': mode, 'exit_code': exit_code, 'wall_seconds_including_load': elapsed, 'completed_generations': len(rows),
              'expected_generations': len(inputs), 'frozen_hashes': frozen, 'frozen_artifacts_unchanged': True,
              'runtime': json.loads((output / 'runtime.json').read_text(encoding='utf-8')) if (output / 'runtime.json').exists() else None}
    if mode == 'eval':
        by_id = {c['id']: c for c in data['cases']}
        schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
        scored = [{**row, **score(row['raw_model_output'], by_id[row['case_id']], schema)} for row in rows]
        result.update(per_case=scored, aggregate=metrics(scored, data['cases']),
                      per_seed={str(seed): metrics([r for r in scored if r['seed'] == seed], data['cases']) for seed in cfg['seeds']})
    else:
        result['sanity_outputs'] = rows
    write_json(output / 'result.json', result)
    print(json.dumps({'mode': mode, 'exit_code': exit_code, 'completed': len(rows), 'wall_seconds': elapsed}), flush=True)
    return 0 if exit_code == 0 and len(rows) == len(inputs) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['sanity', 'eval', '_worker'])
    parser.add_argument('--mode', choices=['sanity', 'eval'])
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    target = Path(args.output).resolve()
    if not target.is_relative_to(ROOT / '.tmp'):
        parser.error('Run artifacts must be in the ignored project .tmp directory')
    try:
        if args.command == '_worker':
            worker(args.mode, target)
        else:
            sys.exit(launch(args.command, target))
    except Exception:
        traceback.print_exc()
        sys.exit(1)
