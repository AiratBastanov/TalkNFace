"""Explicit synthetic fixtures; never imported by a production worker."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from common import HERE, ROOT, read_json, write_json
from selection import STEP1, STEP2, RELOAD
from state import GATE
from verdict import decide

VALIDATION = ROOT / '.tmp/rtx3060-handoff-validation'
VALIDATION.mkdir(parents=True, exist_ok=True)


def temporary(): return tempfile.TemporaryDirectory(dir=VALIDATION, prefix='fixture ')


def quote(value): return "'" + str(value).replace("'", "''") + "'"


def powershell(code, timeout=30):
    env = dict(os.environ)
    env.pop('RTX3060_RESOLVED_PYTHON', None)
    return subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-Command',
                           '[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);'+code],
                          capture_output=True, encoding='utf-8', errors='strict', timeout=timeout, env=env)


def common_ps(): return '. ' + quote(HERE / 'Remote.Common.ps1') + ';'


def copy_tool(root):
    tool = Path(root) / 'tools/windows-rtx3060-12gb-1536'; tool.mkdir(parents=True)
    for path in HERE.iterdir():
        if path.is_file(): shutil.copy2(path, tool / path.name)
    return tool


def audit():
    return {'network_allowed':False,'evaluation_file_reads':[],'denied':[],'reads':['ml/data/synthetic_ru/train.jsonl'],
            'phase':'fixture','limitation':'Python audit hooks; not an OS sandbox'}


def selection():
    top = [{'rank':i+1,'id':f'fixture-{i+1}','length':n} for i,n in enumerate(STEP2+STEP1+[RELOAD])]
    one, two = [r['id'] for r in top[4:8]], [r['id'] for r in top[:4]]
    return {'source_rows_measured':8000,'eligible_rows':8000,'configured_max_length':1536,'observed_max_length':1421,
            'rows_above_limit':0,'truncated_rows':0,'selected_ids':one+two,'selected_lengths':STEP1+STEP2,
            'optimizer_step_1_ids':one,'optimizer_step_2_ids':two,'optimizer_step_1_lengths':list(STEP1),
            'optimizer_step_2_lengths':list(STEP2),'reload_id':top[8]['id'],'reload_length':RELOAD,
            'top9_by_length':top,'all_length_max':1421}


def hardware():
    return {'name':'NVIDIA GeForce RTX 3060','cuda_name':'NVIDIA GeForce RTX 3060','physical_MiB':12288,
            'cuda_capacity_bytes':12287*2**20,'capability':[8,6],'cuda_runtime':'12.6','free_MiB':11500,
            'torch':{'free_bytes':11000*2**20}}


def memory():
    return {'free_bytes':600*2**20,'allocated_bytes':9000*2**20,'reserved_bytes':11000*2**20,
            'peak_allocated_bytes':10000*2**20,'peak_reserved_bytes':11500*2**20,'total_bytes':12287*2**20,
            'host_available_bytes':18*2**30}


def monitor(budget=1800):
    return {'returncode':0,'worker_exited':True,'worker_pid':555002,'launcher_pid':555001,'stop_reason':None,
            'watchdog_seconds':budget,'seconds':20,'samples':100,'gpu_samples':80,'gpu_sampler_error':None,
            'gpu_initial':{'total_MiB':12288},'gpu_min_free_MiB':800,'gpu_peak_used_MiB':11488,
            'pagefile_available_all':True,'gpu_process_counters_available':True,'gpu_process_shared_peak_bytes':400*2**20,
            'gpu_process_dedicated_peak_bytes':10000*2**20,'host_available_before_bytes':20*2**30,
            'host_min_available_bytes':14*2**30,'pagefile_peak_delta_bytes':0,'unrelated_processes_terminated':[]}


def training_fixture():
    s = selection()
    micros = [{'id':s['selected_ids'][i],'tokens':n,'step':i//4+1,'accumulation':i%4+1,'loss':2.0,
               'gradient_norm':0.2,'gradient_tensors':144,'gradients_finite':True,'memory':memory()} for i,n in enumerate(STEP1+STEP2)]
    steps = [{'step':i+1,'token_counts':s[f'optimizer_step_{i+1}_lengths'],'row_ids':s[f'optimizer_step_{i+1}_ids'],
              'loss':2.0,'gradient_norm':0.2,'gradient_tensors':144,'gradients_finite':True,'nonzero_gradient_tensors':72,
              'grad_scaler_skipped':False,'memory':memory()} for i in range(2)]
    train = {'passed':True,'model_load_started':True,'full_training_started':False,'configuration':read_json(HERE/'config.json'),
             'gpu_before_load':hardware(),'fair_start':{'fair':True},'actual_optimizer_steps':2,'steps':steps,'microbatches':micros,
             'nan_inf':False,'selection':s,'adapter_structure':{'trainable_parameters':2949120,'A_tensors':72,'B_tensors':72,
             'target_counts':{'q_proj':36,'v_proj':36}},'trainable_parameters':2949120,'all_parameters_on_cuda':True,
             'only_adapters_trainable':True,'quantized_modules':252,'use_cache':False,
             'optimizer':{'requested':'paged_adamw_8bit','is_paged':True,'optim_bits':8,'kwargs':{'lr':0.0002}},
             'completion_mask':{'prompt_ignored':True,'complete_json_supervised':True,'eos_supervised':True,'padding_ignored':True,
                                'verified_rows':8,'thinking_supervised':False},
             'offload_verified':True,'gradient_checkpointing':True,'checkpointed_decoder_layers':36,'offload':{'contexts':288},
             'after_training':memory(),'before_load':memory(),'after_preparation':memory(),'cuda_oom':False,
             'adapter_change':{'changed_tensors':144,'total_adapter_tensors':144,
                              'examples':[{'initial_sha256':'a'*64,'final_sha256':'b'*64,'max_abs_delta':0.1}]},
             'adapter':{'files':{n:{'bytes':100,'sha256':'a'*64} for n in ('adapter_model.safetensors','adapter_config.json')},
                        'config':read_json(HERE/'config.json')['lora']},
             'adapter_final_tensor_hashes':{f'fixture-{i}':'a'*64 for i in range(144)},'worker_pid':555002,'audit':audit()}
    reload = {'passed':True,'logits_finite':True,'adapter_tensors_equal':True,'fresh_process':True,'worker_pid':555003,
              'training_worker_pid':555002,'row_id':s['reload_id'],'complete_record_tokens':1387,'prompt_tokens':1000,
              'generated_tokens':0,'quality_evaluation':False,'configured_max_length':1536,'active_adapters':['default'],'audit':audit()}
    return train, monitor(), reload, monitor(600)


def tiny_model(folder):
    """Tiny bytes with a fixture-only lock; never a real checkpoint."""
    folder = Path(folder); folder.mkdir(parents=True)
    values = {'config.json':{'model_type':'qwen3','hidden_size':2560,'num_hidden_layers':36},
              'model.safetensors.index.json':{'metadata':{'total_size':8044936192},
                'weight_map':{str(i):f'model-{i:05d}-of-00003.safetensors' for i in range(1,4)}},
              'tokenizer.json':{},'tokenizer_config.json':{},'vocab.json':{}}
    for n,v in values.items(): write_json(folder/n,v)
    for i in range(1,4): (folder/f'model-{i:05d}-of-00003.safetensors').write_bytes(b'FIXTURE-NOT-A-MODEL'+bytes([i]))
    from common import sha256
    return {'repo_id':'fixture/no-model','revision':'fixture','files':{p.name:{'bytes':p.stat().st_size,'sha256':sha256(p)} for p in folder.iterdir()}}
