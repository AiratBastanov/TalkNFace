"""Campaign state, real ZIP integrity, strict verifier, mocked worker orchestration."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import zipfile
from common import HERE, read_json, write_json, sha256
import runner
import state
from state import GATE, OperationLock, campaign_status, reserve_campaign
import package_result
import verify_result
from verdict import decide, PREFIX
from test_support import temporary, training_fixture, selection, audit, hardware


class StateWorkflowTests(unittest.TestCase):
    def test_os_lock_prevents_real_concurrent_start(self):
        with temporary() as tmp:
            scratch=Path(tmp)
            code="import sys;sys.path.insert(0,sys.argv[1]);from state import OperationLock;from pathlib import Path\nwith OperationLock(Path(sys.argv[2])):print('UNEXPECTED')"
            with OperationLock(scratch):
                child=subprocess.run([sys.executable,'-B','-c',code,str(HERE),str(scratch)],capture_output=True,encoding='utf-8',timeout=20)
                self.assertNotEqual(child.returncode,0); self.assertIn('owns the lock',child.stderr)
            with OperationLock(scratch): pass  # OS unlock permits later non-training work.

    def test_one_shot_reservation_refuses_repeat(self):
        with temporary() as tmp:
            s=Path(tmp); a=s/'adapter'
            reserve_campaign(s,a)
            with self.assertRaises(AssertionError): reserve_campaign(s,a)
            self.assertEqual(campaign_status(s,a),'active_or_ambiguous')

    def test_prepared_train_contexts_allow_first_campaign_and_precondition_retry(self):
        with temporary() as tmp:
            s=Path(tmp); a=s/'adapter'
            for name in ('train-contexts.json','prepared-ready.json','data-1536.json'):
                write_json(s/name,{'preparation_only':True})
            self.assertEqual(campaign_status(s,a),'fresh')
            with patch.multiple(runner,SCRATCH=s), patch('runner.campaign_status',side_effect=lambda:campaign_status(s,a)), patch('runner.no_live_workers'), patch('runner.assert_ready',side_effect=RuntimeError('fixture prerequisite')):
                self.assertFalse(runner.run_campaign())
            self.assertEqual(campaign_status(s,a),'retryable_precondition')
            reserve_campaign(s,a)
            self.assertEqual(campaign_status(s,a),'active_or_ambiguous')

    def test_missing_marker_does_not_authorize_retry(self):
        for trace in ('model-load-started.json','train-1536.json','worker-started.json','training-x.log'):
            with temporary() as tmp:
                s=Path(tmp); (s/trace).write_text('{}')
                self.assertEqual(campaign_status(s,s/'adapter'),'active_or_ambiguous')
                with self.assertRaises(AssertionError): reserve_campaign(s,s/'adapter')

    def test_live_recorded_worker_blocks_even_without_campaign_marker(self):
        with temporary() as tmp:
            s=Path(tmp); write_json(s/'training-x-worker.json',{'pid':os.getpid()})
            self.assertEqual(campaign_status(s,s/'adapter'),'active_or_ambiguous')

    def test_completed_campaign_is_reporting_only(self):
        with temporary() as tmp:
            s=Path(tmp); reserve_campaign(s,s/'adapter')
            ledger=read_json(s/'campaign-ledger.json'); ledger.update(status='completed',model_load_started=True)
            write_json(s/'campaign-ledger.json',ledger); write_json(s/'outcome.json',{'verdict':PREFIX+'PASS'})
            with patch.multiple(runner,SCRATCH=s), patch('runner.campaign_status',return_value='completed'), patch('runner.supervise') as run:
                self.assertTrue(runner.run_campaign()); run.assert_not_called()

    def test_completed_failed_campaign_preserves_failure_exit(self):
        with temporary() as tmp:
            s=Path(tmp); write_json(s/'outcome.json',{'verdict':PREFIX+'FAIL'})
            with patch.multiple(runner,SCRATCH=s), patch('runner.campaign_status',return_value='completed'), patch('runner.supervise') as run:
                self.assertFalse(runner.run_campaign()); run.assert_not_called()

    def test_verified_precondition_failure_is_retryable_without_load(self):
        with temporary() as tmp:
            s=Path(tmp)
            with patch.multiple(runner,SCRATCH=s), patch('runner.campaign_status',return_value='fresh'), patch('runner.no_live_workers'), patch('runner.assert_ready',side_effect=RuntimeError('fixture prerequisite')):
                self.assertFalse(runner.run_campaign())
            self.assertEqual(campaign_status(s,s/'adapter'),'retryable_precondition')
            self.assertFalse((s/'campaign-started.json').exists())

    def test_preload_refusal_preserves_marker_and_allows_retry(self):
        with temporary() as tmp:
            s=Path(tmp); reserve_campaign(s,s/'adapter')
            write_json(s/'train-1536.json',{'model_load_started':False,'gpu_environment_blocked':True})
            write_json(s/'worker-started.json',{'pid':555001})
            m={'worker_exited':True,'returncode':1,'stop_reason':None,'worker_pid':555001,'launcher_pid':555002}
            with patch('state.process_active',return_value=False): state.release_preload_failure(read_json(s/'train-1536.json'),m,s)
            self.assertEqual(len(list(s.glob('preload-refusals/*/campaign-started.json'))),1)
            self.assertEqual(campaign_status(s,s/'adapter'),'retryable_precondition')

    def test_ambiguous_or_loaded_refusal_is_never_released(self):
        for started in (True,None):
            with temporary() as tmp:
                s=Path(tmp); reserve_campaign(s,s/'adapter')
                with self.assertRaises(AssertionError): state.release_preload_failure({'model_load_started':started,'gpu_environment_blocked':True},{},s)
                self.assertTrue((s/'campaign-started.json').exists())

    def test_repeated_prepare_reuses_validated_readiness(self):
        with temporary() as tmp:
            s=Path(tmp); write_json(s/'prepared-ready.json',{'passed':True})
            with patch.multiple(runner,SCRATCH=s), patch('runner.campaign_status',return_value='fresh'), patch('runner.capture'), patch('runner.assert_git_safe'), patch('runner.verify_model',return_value={'passed':True}), patch('runner.assert_ready') as ready, patch('runner.protect_after') as after, patch('runner.supervise') as run:
                runner.prepare(); ready.assert_called_once(); after.assert_called_once(); run.assert_not_called()

    def test_missing_preparation_audit_cannot_claim_isolation(self):
        self.assertFalse(runner.isolation_ok({}, {}, {}, {}))
        a=audit(); self.assertTrue(runner.isolation_ok(a,{'audit':a},{'audit':a},{'audit':a}))
        a['network_allowed']=True; self.assertFalse(runner.isolation_ok(a,{'audit':a},{'audit':a},{'audit':a}))

    def test_full_prepare_dispatches_real_measurement_and_cheap_tests_budgets(self):
        with temporary() as tmp:
            s=Path(tmp); write_json(s/'cuda-backend.json',{'passed':True})
            def supervisor(name,budget,cmd):
                if name.startswith('prepare-data'):
                    write_json(s/'data-1536.json',{'selection':selection()}); write_json(s/'prepare-1536-audit.json',audit())
                else: write_json(s/'tests.json',{'passed':True,'audit':audit()})
                return 0
            def project():
                for name in ('frozen-controls.json','module-control.json','train-contexts.json','integrity-before.json'): write_json(s/name,{'fixture':True})
            with patch.multiple(runner,SCRATCH=s), patch('runner.campaign_status',return_value='fresh'), patch('runner.capture'), patch('runner.assert_git_safe',return_value={'commit':'fixture'}), patch('runner.verify_model',return_value={'passed':True}), patch('runner.project',side_effect=project), patch('runner.protect_before'), patch('runner.protect_after'), patch('runner.supervise',side_effect=supervisor) as call:
                runner.prepare()
            self.assertEqual([c.args[1] for c in call.call_args_list],[600,180])
            self.assertTrue(read_json(s/'prepared-ready.json')['passed'])
            self.assertFalse((s/'campaign-started.json').exists())

    def test_entire_mocked_campaign_train_reload_verdict_and_no_second_training(self):
        with temporary() as tmp:
            s=Path(tmp); a=s/'adapter'; t,m,r,rm=training_fixture()
            def supervisor(name,budget,cmd):
                if name.startswith('resources-'):
                    write_json(s/'preflight.json',{'passed':True,'gpu':hardware()})
                elif name.startswith('training-'):
                    write_json(s/'train-1536.json',t); write_json(s/(name+'-monitor.json'),m)
                    write_json(s/'model-load-started.json',{'started':True})
                elif name=='reload':
                    write_json(s/'reload-1536.json',r); write_json(s/'reload-monitor.json',rm)
                else: self.fail('Unknown phase '+name)
                return 0
            write_json(s/'tests.json',{'passed':True,'audit':audit()}); write_json(s/'prepare-1536-audit.json',audit())
            write_json(s/'prepared-ready.json',{'git':{'commit':'fixture'}})
            write_json(s/'train-contexts.json',{'preparation_only':True})
            with patch.multiple(runner,SCRATCH=s), patch('runner.campaign_status',side_effect=lambda:campaign_status(s,a)), patch('runner.no_live_workers'), patch('runner.assert_ready'), patch('runner.capture'), patch('runner.verify_model'), patch('runner.protect_after',return_value={'passed':True}), patch('runner.reserve_campaign',side_effect=lambda:reserve_campaign(s,a)), patch('runner.supervise',side_effect=supervisor) as calls:
                self.assertTrue(runner.run_campaign())
                self.assertEqual([c.args[1] for c in calls.call_args_list],[180,1800,600])
                self.assertTrue(runner.run_campaign())
                self.assertEqual(calls.call_count,3)
            self.assertEqual(read_json(s/'outcome.json')['verdict'],PREFIX+'PASS')
            self.assertEqual(campaign_status(s,a),'completed')


class ArchiveVerifierTests(unittest.TestCase):
    def synthetic_evidence(self):
        t,m,r,rm=training_fixture(); lock=read_json(HERE/'model-lock.json'); runtime=read_json(HERE/'runtime-lock.json')
        o=dict(decide(t,m,r,True,True,True,rm),training=t,monitor=m,reload=r,reload_monitor=rm,
               integrity={'passed':True,'model':{'files':lock['files']}},isolated=True,
               preflight={'passed':True,'gpu':hardware()},training_campaigns=1,full_training_started=False,
               evaluation_started=False,local_quality_evaluation=False)
        e=package_result.evidence_for(Path('fixture-nonexistent'))
        e.update(fixture_only=True,outcome=o,selection=selection(),campaign={'status':'completed','model_load_started':True,'nonce':'fixture'},
                 campaign_reservation={'nonce':'fixture','gate':GATE,'worker_may_start':True},worker_entry={'nonce':'fixture','pid':555002},
                 model_load_entry={'started':True,'pid':555002},
                 full_training_started=False,prepare_audit=audit(),tests={'passed':True,'audit':audit()},
                 model_hash_verification={'passed':True,'files':lock['files'],'revision':lock['revision'],'repo_id':lock['repo_id']},
                 runtime={'passed':True,'python':runtime['python'],'bits':64,'pip_check_returncode':0,'mismatches':{},'unexpected_packages':[],
                          'versions':{__import__('re').sub(r'[-_.]+','-',k).lower():v for k,v in runtime['packages'].items()}},
                 cuda_backend={'passed':True,'Qwen_model_loaded':False,'gpu':hardware(),
                               'nf4':{'executed_on_cuda':True,'double_quant':True,'finite_output':True,'compute_dtype':'float16','backward':False}})
        return e

    def write_archive(self,path,e,mutation=None):
        payload={'RESULT.txt':package_result.result_text(e).encode(),'evidence.json':json.dumps(e).encode()}
        manifest={n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in payload.items()}
        if mutation=='coverage': manifest.pop('RESULT.txt')
        if mutation=='digest': manifest['evidence.json']['sha256']='0'*64
        payload['archive-manifest.json']=json.dumps(manifest).encode()
        if mutation=='extra': payload['weights.bin']=b'forbidden'
        if mutation=='contradictory_text': payload['RESULT.txt']=b'PASS'
        with zipfile.ZipFile(path,'w') as z:
            for n,b in payload.items(): z.writestr(n,b)
            if mutation=='duplicate': z.writestr('evidence.json',payload['evidence.json'])

    def test_real_archive_exact_manifest_and_no_private_files(self):
        with temporary() as tmp:
            r=Path(tmp); scratch=r/'scratch'; scratch.mkdir()
            (scratch/'training-raw.log').write_text('SECRET PROMPT hf_PRIVATE')
            write_json(scratch/'data-1536.json',{'selection':selection(),'rows':[{'prompt':'DO NOT SEND'}]})
            (scratch/'adapter_model.safetensors').write_bytes(b'DO NOT SEND')
            archive=package_result.package(scratch,r/'results',r)
            e,manifest=verify_result.inspect_zip(archive)
            self.assertEqual(set(manifest),{'RESULT.txt','evidence.json'})
            with zipfile.ZipFile(archive) as z:
                allbytes=b''.join(z.read(n) for n in z.namelist())
                self.assertNotIn(b'DO NOT SEND',allbytes); self.assertNotIn(b'SECRET PROMPT',allbytes)
            self.assertFalse(verify_result.verify_evidence(e)['certified_training_pass'])

    def test_manifest_duplicate_extra_hash_coverage_and_contradictory_text_fail(self):
        for mutation in ('duplicate','extra','digest','coverage','contradictory_text'):
            with temporary() as tmp:
                path=Path(tmp)/'fixture.zip'; self.write_archive(path,self.synthetic_evidence(),mutation)
                with self.assertRaises(ValueError): verify_result.inspect_zip(path)

    def test_crc_or_truncated_zip_rejected(self):
        with temporary() as tmp:
            path=Path(tmp)/'fixture.zip'; self.write_archive(path,self.synthetic_evidence())
            path.write_bytes(path.read_bytes()[:-15])
            with self.assertRaises(zipfile.BadZipFile): verify_result.inspect_zip(path)

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError): verify_result.unique_json('{"passed":false,"passed":true}')

    def test_fixture_pass_is_explicitly_not_hardware_certification(self):
        e=self.synthetic_evidence(); result=verify_result.verify_evidence(e,source_check=lambda e:True)
        self.assertEqual(result['failed_checks'],['fixture_is_not_hardware_evidence'],result)
        self.assertFalse(result['certified_training_pass'])

    def test_missing_or_contradictory_training_evidence_rejected(self):
        for change in ('missing','skip','micro_length','same_process','full_training','isolation','reported','hardware','model','source'):
            e=self.synthetic_evidence()
            if change=='missing': del e['outcome']['training']['actual_optimizer_steps']
            if change=='skip': e['outcome']['training']['steps'][0]['grad_scaler_skipped']=True
            if change=='micro_length': e['outcome']['training']['microbatches'][0]['tokens']=1536
            if change=='same_process': e['outcome']['reload']['worker_pid']=555002
            if change=='full_training': e['full_training_started']=True
            if change=='isolation': e['prepare_audit']={}
            if change=='reported': e['outcome']['minimum_boundary_free_bytes']=0
            if change=='hardware': e['outcome']['preflight']['gpu']['physical_MiB']=8192
            if change=='model': e['model_hash_verification']['files']={}
            result=verify_result.verify_evidence(e,source_check=lambda e:change!='source')
            self.assertGreater(len(result['failed_checks']),1,(change,result))

    def test_required_schema_fields_are_not_optional(self):
        e=self.synthetic_evidence(); del e['full_training_started']
        with self.assertRaises(ValueError): verify_result.verify_evidence(e)

    def test_source_hash_coverage_and_commit_identity_are_actually_verified(self):
        with temporary() as tmp:
            root=Path(tmp); source=root/' leading source.txt'; source.write_text('fixture source',encoding='utf-8')
            decision=root/'docs/gates/evidence/LOCAL_QWEN_QLORA_MEMORY_ARCHITECTURE_DECISION.json'
            write_json(decision,{'fixture':'byte-only'})
            names=[source.relative_to(root).as_posix(),decision.relative_to(root).as_posix()]
            pins={n:{'bytes':(root/n).stat().st_size,'sha256':sha256(root/n)} for n in names}
            pins.update({'AlagModels/Qwen3-4B/'+n:p for n,p in read_json(HERE/'model-lock.json')['files'].items()})
            identity={'commit':'a'*40,'origin':'https://github.com/AiratBastanov/TalkNFace.git','clean':True}
            e={'outcome':{'repository_commit':'a'*40,'integrity':{'passed':True,'before':pins,'after':copy.deepcopy(pins),'git':identity}},
               'prepared':{'git':identity,'configuration_sha256':sha256(HERE/'config.json')},
               'controls':{'configuration':read_json(HERE/'config.json'),'decision_sha256':sha256(decision)}}
            def git(*args): return 'a'*40+'\n' if args[0]=='rev-parse' else '\0'.join(names)+'\0'
            with patch('verify_result.ROOT',root),patch('verify_result.git',side_effect=git):
                self.assertTrue(verify_result.source_identity(e))
                source.write_text('changed source',encoding='utf-8')
                with self.assertRaises(AssertionError): verify_result.source_identity(e)
                source.write_text('fixture source',encoding='utf-8')
                e['outcome']['repository_commit']='b'*40
                with self.assertRaises(AssertionError): verify_result.source_identity(e)

    def test_package_reuse_and_replacement_preserve_old_zip(self):
        with temporary() as tmp:
            r=Path(tmp); s=r/'scratch'; s.mkdir()
            first=package_result.package(s,r/'results',r); digest=sha256(first)
            self.assertEqual(package_result.package(s,r/'results',r),first)
            write_json(s/'last-phase-error.json',{'phase':'01','message':'private exception'})
            package_result.package(s,r/'results',r)
            self.assertNotEqual(sha256(first),digest)
            self.assertEqual(sha256(s/'packaged-history'/f'{digest}.zip'),digest)

    def test_content_and_credentials_sanitization(self):
        with self.assertRaises(ValueError): package_result.sanitize({'input_ids':[1,2]})
        result=package_result.sanitize({'token':'hf_abc','error':'raw corpus row','path':r'C:\Users\Друг имя\file',
                                       'url':'https://user:pass@example.com/a?token=secret'})
        text=json.dumps(result); self.assertNotIn('raw corpus',text); self.assertNotIn('Друг',text); self.assertNotIn('secret',text)


if __name__=='__main__': unittest.main(verbosity=2)
