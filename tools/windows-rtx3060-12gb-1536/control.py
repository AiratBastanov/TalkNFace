"""Supervisor-only frozen controls, Git/source identity and byte-only integrity for the 1536 gate."""
import subprocess
import json
from common import ROOT, HERE, DATA, MODEL, SCRATCH, read_json, write_json, sha256
from model_files import verify_model

DECISION = ROOT / 'docs/gates/evidence/LOCAL_QWEN_QLORA_MEMORY_ARCHITECTURE_DECISION.json'
BASE_TOOL = ROOT / 'tools/windows-rtx3070'
BASE_CONFIG_SHA256 = '760ca765962a192adf8795cbf8e33bef4e6beb458ce27bac6cb3730228b0cfb1'


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], encoding='utf-8', errors='strict', timeout=30)


def assert_git_safe():
    assert git('branch', '--show-current').rstrip('\r\n') == 'main', 'Expected main'
    assert git('remote', 'get-url', 'origin').rstrip('\r\n') == 'https://github.com/AiratBastanov/TalkNFace.git', 'Unexpected source origin'
    assert not git('status', '--porcelain=v1', '--untracked-files=all'), 'Repository must be clean; do not edit accepted files'
    tracked = git('ls-files', '-z').split('\0')[:-1]
    bad = [p for p in tracked if p.startswith(('AlagModels/', 'AlagDatasets/', '.venv', '.tmp/', 'handoff-results/'))]
    assert not bad, 'Model/data/environment/output directory unexpectedly tracked'
    paths = ['.venv-qlora-remote/pyvenv.cfg', '.tmp/rtx3060-12gb-targeted-1536-smoke/data-1536.json',
             'AlagModels/adapters/rtx3060-12gb-targeted-1536-smoke/1536/adapter_model.safetensors',
             'handoff-results/RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_RESULT.zip']
    ignored = git('check-ignore', '-z', *paths).split('\0')[:-1]
    assert set(ignored) == set(paths), 'New 1536 runtime/output paths must stay ignored'
    return {'commit': git('rev-parse', 'HEAD').rstrip('\r\n'), 'origin': git('remote', 'get-url', 'origin').rstrip('\r\n'), 'clean': True, 'ignored_paths': paths}


def project():
    decision = read_json(DECISION)
    base = read_json(BASE_TOOL / 'config.json')
    config = read_json(HERE / 'config.json')
    assert sha256(BASE_TOOL / 'config.json') == BASE_CONFIG_SHA256, 'Successful 1024 baseline configuration changed'
    sequence = decision['sequence_constraint']
    assert sequence['train_total'] == 8000
    assert sequence['max_complete_tokens'] == 1421
    assert sequence['all_train_at_most_1536'] is True
    assert sequence['1024_smoke_does_not_certify_full_corpus'] is True
    assert sequence['no_long_records_silently_dropped'] is True
    for key in ('seed', 'model', 'train', 'quantization', 'lora', 'activation_offload', 'host_memory'):
        assert config[key] == base[key], f'Architecture/runtime drift from successful 1024 gate: {key}'
    base_training = dict(base['training']); new_training = dict(config['training'])
    assert base_training.pop('max_length') == 1024 and new_training.pop('max_length') == 1536
    assert new_training == base_training, 'Only training.max_length may differ from the successful 1024 training configuration'
    assert config['subset_rows'] == 8 and config['retry_sequence_limit'] is None
    assert config['output'] == '.tmp/rtx3060-12gb-targeted-1536-smoke'
    assert config['adapter'] == 'AlagModels/adapters/rtx3060-12gb-targeted-1536-smoke'
    accepted = read_json(ROOT / 'tools/windows-rtx3070-1536/config.json')
    assert config['training'] == accepted['training'], 'Accepted 1536 training changed'
    for name in ('model-lock.json', 'runtime-lock.json', 'requirements.txt', 'requirements-torch.txt'):
        assert (HERE / name).read_bytes() == (BASE_TOOL / name).read_bytes(), f'Frozen lock changed: {name}'
    dimensions = decision['static_analysis']['module_dimensions']
    registry = {k: v for k, v in read_json(DATA / 'contexts.json').items() if v['split'] == 'train'}
    assert len(registry) == 140
    write_json(SCRATCH / 'module-control.json', dimensions)
    write_json(SCRATCH / 'train-contexts.json', registry)
    frozen = {'decision_sha256': sha256(DECISION), 'baseline_config_sha256': BASE_CONFIG_SHA256,
              'sequence_constraint': sequence, 'configuration': config}
    write_json(SCRATCH / 'frozen-controls.json', frozen)
    return frozen


def snapshot():
    paths = [ROOT / p for p in git('ls-files', '-z').split('\0') if p]
    # Git-tracked eval files are byte-hashed by this separate supervisor only.
    # No raw external datasets or old adapters are required by the training worker.
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
