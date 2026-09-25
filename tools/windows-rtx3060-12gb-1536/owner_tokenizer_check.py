"""Optional OWNER check: real accepted tokenizer/compiler, ZERO model loads.

Run with an already installed accepted environment under a fixed 180 s owner
test budget. This does not create target preparation or campaign readiness.
"""
import json
from pathlib import Path
import time
import uuid
import common
from common import ROOT, HERE, MODEL, DATA, read_json, write_json, sha256
import prepare_smoke_data
from selection import validate_selection


def main():
    started=time.monotonic()
    scratch=ROOT/'.tmp/rtx3060-handoff-validation'/('owner-tokenizer-'+uuid.uuid4().hex)
    scratch.mkdir(parents=True)
    # Supervisor projects TRAIN contexts before the worker's read guard exists.
    registry={k:v for k,v in read_json(DATA/'contexts.json').items() if v['split']=='train'}
    assert len(registry)==140
    write_json(scratch/'train-contexts.json',registry)
    pinned=read_json(HERE/'model-lock.json')['files']
    names=[n for n in pinned if not n.endswith('.safetensors')]
    before={n:sha256(MODEL/n) for n in names}
    assert all(before[n]==pinned[n]['sha256'] for n in names)
    common.SCRATCH=scratch; prepare_smoke_data.SCRATCH=scratch
    guard=common.AccessGuard('owner-tokenizer-only',tokenizer_only=True).install()
    data=prepare_smoke_data.prepare(1536)
    assert validate_selection(data['selection'])
    after={n:sha256(MODEL/n) for n in names}
    assert after==before
    report={'passed':True,'selection':data['selection'],'seconds':time.monotonic()-started,
            'tokenizer_hashes_unchanged':True,'audit':guard.report(),'Qwen_checkpoint_loads':0,
            'inference_calls':0,'optimizer_updates':0,'training_campaigns':0,'evaluation_calls':0,
            'owner_hardware_pass_claimed':False,'prepared_ready_created':False}
    write_json(scratch/'owner-tokenizer-check.json',report)
    print(json.dumps(report,ensure_ascii=True),flush=True)


if __name__=='__main__': main()
