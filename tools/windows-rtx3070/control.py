"""Supervisor-only frozen controls, Git/source identity and byte-only integrity."""
import json
import subprocess
from common import ROOT, HERE, DATA, MODEL, SCRATCH, read_json, write_json, sha256
from model_files import verify_model

DECISION = ROOT / 'docs/gates/evidence/LOCAL_QWEN_QLORA_MEMORY_ARCHITECTURE_DECISION.json'


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], encoding='utf-8', errors='strict').strip()


def assert_git_safe():
    assert not git('status', '--porcelain=v1', '--untracked-files=all'), 'Repository must be clean; do not edit accepted files'
    tracked = git('ls-files', '-z').split('\0')
    bad = [p for p in tracked if p.startswith(('AlagModels/', 'AlagDatasets/', '.venv', '.tmp/', 'handoff-results/'))]
    assert not bad, 'Model/data/environment/output directory unexpectedly tracked'
    paths = ['.venv-qlora-remote/pyvenv.cfg', '.tmp/rtx3070-targeted-smoke/data-1024.json',
             'AlagModels/adapters/rtx3070-targeted-smoke/1024/adapter_model.safetensors',
             'handoff-results/RTX3070_TARGETED_LORA_SMOKE_RESULT.zip']
    ignored = git('check-ignore', *paths).splitlines()
    assert set(ignored) == set(paths)
    return {'commit': git('rev-parse', 'HEAD'), 'clean': True, 'ignored_paths': paths}


def project():
    decision = read_json(DECISION)
    spec = decision['next_experiment']; config = read_json(HERE / 'config.json')
    for key in ('training', 'quantization', 'lora', 'activation_offload'):
        assert config[key] == spec['configuration'][key], f'Frozen architecture drift: {key}'
    assert spec['allowed_training_campaigns'] == 1 and spec['allowed_retries'] == 0
    remote_spec = dict(spec, configuration=config)
    write_json(SCRATCH / 'spec-control.json', remote_spec)
    write_json(SCRATCH / 'selection-control.json', spec['same_historical_selection'])
    write_json(SCRATCH / 'module-control.json', decision['static_analysis']['module_dimensions'])
    registry = {k: v for k, v in read_json(DATA / 'contexts.json').items() if v['split'] == 'train'}
    assert len(registry) == 140
    write_json(SCRATCH / 'train-contexts.json', registry)
    write_json(SCRATCH / 'frozen-controls.json', {'decision_sha256': sha256(DECISION),
               'selected_ids': spec['same_historical_selection']['selected_ids'],
               'lengths': spec['same_historical_selection']['lengths'], 'optimizer_ids': spec['optimizer_row_ids'],
               'reload_id': spec['reload_row_id'], 'configuration': config})


def snapshot():
    paths = [ROOT / p for p in git('ls-files', '-z').split('\0') if p]
    # Git-tracked eval files are byte-hashed by this separate supervisor only.
    # No raw external datasets or old adapters are required on the target PC.
    paths += [MODEL / name for name in read_json(HERE / 'model-lock.json')['files']]
    return {p.relative_to(ROOT).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha256(p)} for p in sorted(paths)}


def protect_before():
    checked = assert_git_safe()
    model = verify_model()
    before = {'git': checked, 'files': snapshot(), 'model': model}
    write_json(SCRATCH / 'integrity-before.json', before)
    return before


def protect_after():
    before = read_json(SCRATCH / 'integrity-before.json')
    after = snapshot()
    result = {'passed': before['files'] == after, 'before': before['files'], 'after': after,
              'model': verify_model(), 'git': assert_git_safe()}
    write_json(SCRATCH / 'integrity-after.json', result)
    assert result['passed'], 'Protected files changed'
    return result
