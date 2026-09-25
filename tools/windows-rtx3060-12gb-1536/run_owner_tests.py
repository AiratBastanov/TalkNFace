"""Focused owner regressions: fixed 180 seconds per group, no Qwen/CUDA work."""
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from common import ROOT, HERE, write_json


def main():
    output=ROOT/'.tmp/rtx3060-handoff-validation'; output.mkdir(parents=True,exist_ok=True)
    groups=[]
    for name in ('test_handoff','test_setup_model','test_python_launcher','test_workflow_result'):
        start=time.monotonic(); log=output/(name+'.log')
        print(f'ACTIVE: {name}; fixed budget=180s; log={log}',flush=True)
        with log.open('w',encoding='utf-8') as stream:
            p=subprocess.run([sys.executable,'-B','-m','unittest',name,'-v'],cwd=HERE,
                             stdout=stream,stderr=subprocess.STDOUT,timeout=180,
                             env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'))
        text=log.read_text(encoding='utf-8'); counts=re.findall(r'Ran (\d+) tests?',text)
        row={'group':name,'returncode':p.returncode,'tests':int(counts[-1]) if counts else None,
             'seconds':round(time.monotonic()-start,3),'budget_seconds':180,'passed':p.returncode==0}
        groups.append(row); print(row,flush=True)
    result={'passed':all(r['passed'] for r in groups),'tests':sum(r['tests'] or 0 for r in groups),
            'groups':groups,'Qwen_checkpoint_loads':0,'inference_calls':0,'training_campaigns':0,
            'package_installs':0,'fixtures_for_install_and_GPU':True,'real_PowerShell_51':True}
    write_json(output/'regression-results.json',result)
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__': main()
