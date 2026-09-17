"""Supervisor-only frozen specification projection and protected byte audit."""
import argparse
import hashlib
import json
import subprocess
from common import ROOT,HERE,SCRATCH,MODEL,DATA,ADAPTER,read_json,write_json,sha256

DECISION=ROOT/'docs/gates/evidence/LOCAL_QWEN_QLORA_MEMORY_ARCHITECTURE_DECISION.json'
HISTORY=ROOT/'docs/gates/evidence/LOCAL_QWEN_QLORA_HOST_RAM_OFFLOAD_CORRECTION.json'
PINS=('328a91d3122359d5547f9d79521205bc0a46e1f79a792dfe650e99fc2d651223',
      '6cd087b316306a68c562436b5492edbcf6e16c6dba3a1308279caa5a58e21ca5',
      'e4bf436957184f4eeb86a80e9db394503f1f56446b2e6b7edeac5b81470f4ca1')


def capture(paths):
    files={name:{'bytes':(ROOT/name).stat().st_size,'sha256':sha256(ROOT/name)} for name in sorted(paths)}
    for i,pin in enumerate(PINS,1):
        assert files[f'AlagModels/Qwen3-4B/model-{i:05d}-of-00003.safetensors']['sha256']==pin
    environments={}
    for name in ('.venv-ml','.venv-qlora-smoke'):
        stats={p.relative_to(ROOT/name).as_posix():[p.stat().st_size,p.stat().st_mtime_ns]
               for p in (ROOT/name).rglob('*') if p.is_file()}
        environments[name]={'files':len(stats),'stats_sha256':hashlib.sha256(json.dumps(stats,sort_keys=True).encode()).hexdigest()}
    return {'files':files,'environments':environments}


def before():
    assert not (SCRATCH/'integrity-before.json').exists(), 'Preserve previous evidence'
    decision=read_json(DECISION); history=read_json(HISTORY)
    spec=decision['next_experiment']; config=read_json(HERE/'config.json')
    assert config==spec['configuration']
    assert decision['decision']=='LOCAL_TARGETED_LORA_NEXT'
    assert spec['allowed_training_campaigns']==1 and spec['allowed_retries']==0
    baseline=history['campaigns']['1024']
    assert config['training']==baseline['training']['configuration']['training']
    assert config['quantization']==baseline['training']['configuration']['quantization']
    assert config['activation_offload']==baseline['training']['configuration']['activation_offload']
    expected_lora=dict(baseline['training']['configuration']['lora'],target_modules=['q_proj','v_proj'])
    assert config['lora']==expected_lora
    paths=set(decision['integrity']['files'])
    paths.update(p for p in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0') if p)
    # Include existing ignored historical adapters/model metadata without parsing their tensors.
    for folder in (MODEL,ROOT/'AlagModels/adapters'):
        paths.update(p.relative_to(ROOT).as_posix() for p in folder.rglob('*') if p.is_file())
    snapshot=capture(paths)
    for name,item in decision['integrity']['files'].items():
        assert snapshot['files'][name]==item['after'], name
    write_json(SCRATCH/'integrity-before.json',snapshot)
    write_json(SCRATCH/'spec-control.json',spec)
    write_json(SCRATCH/'selection-control.json',spec['same_historical_selection'])
    write_json(SCRATCH/'comparison-control.json',{'training':baseline['training'],'monitor':baseline['monitor'],
               'decision_sha256':sha256(DECISION),'historical_sha256':sha256(HISTORY),
               'adapter_payload_analysis':decision['static_analysis']['candidates']})
    write_json(SCRATCH/'module-control.json',decision['static_analysis']['module_dimensions'])
    registry={key:value for key,value in read_json(DATA/'contexts.json').items() if value['split']=='train'}
    assert len(registry)==140
    write_json(SCRATCH/'train-contexts.json',registry)
    print(f'{len(paths)} protected hashes verified; frozen experiment and TRAIN context controls projected.')


def after():
    initial=read_json(SCRATCH/'integrity-before.json')
    final=capture(initial['files'])
    result={'before':initial,'after':final,'unchanged':initial==final}
    write_json(SCRATCH/'integrity-after.json',result)
    assert result['unchanged']
    print(f'{len(final["files"])} protected files and both environments unchanged.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['before','after']);a=p.parse_args()
    (before if a.phase=='before' else after)()
