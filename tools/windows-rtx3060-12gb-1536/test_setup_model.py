"""Fresh setup/import failure boundaries mocked; TAR and filesystem operations real."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import environment
import model_files
from common import HERE, read_json, write_json, sha256
from test_support import temporary, tiny_model


def fake_venv(command, **kwargs):
    assert command[:3] == [sys.executable,'-m','venv']
    p=Path(command[3]); (p/'Scripts').mkdir(exist_ok=True)
    (p/'Scripts/python.exe').write_bytes(b'FIXTURE NEVER EXECUTED')
    (p/'pyvenv.cfg').write_text('version = 3.12.10\n')
    return subprocess.CompletedProcess(command,0)


class EnvironmentTests(unittest.TestCase):
    def fixture(self,tmp):
        r=Path(tmp); s=r/'.tmp/gate'; s.mkdir(parents=True)
        return patch.multiple(environment,ROOT=r,SCRATCH=s,VENV=r/'.venv-qlora-remote')

    def test_fresh_machine_creates_real_venv_and_locked_pip_commands(self):
        with temporary() as tmp, self.fixture(tmp), patch('environment.campaign_status',return_value='fresh'):
            calls=[]
            def run(cmd,**kw):
                calls.append((cmd,kw))
                if cmd[:3]==[sys.executable,'-m','venv']: return fake_venv(cmd,**kw)
                return subprocess.CompletedProcess(cmd,0,stdout='',stderr='')
            with patch('environment.subprocess.run',side_effect=run), patch('environment.validate_reports') as reports:
                environment.setup()
            self.assertEqual(calls[0][0][:3],[sys.executable,'-m','venv'])
            install=[(c,k) for c,k in calls if 'install' in c]
            self.assertEqual(len(install),2)
            for cmd,kw in install:
                for flag in ('--only-binary=:all:','--require-hashes','--no-deps','--isolated'): self.assertIn(flag,cmd)
                self.assertNotIn('-3.12',cmd); self.assertTrue(kw['check']); self.assertLessEqual(kw['timeout'],1500)
            reports.assert_called_once()

    def test_unmarked_valid_existing_environment_reuses_without_install(self):
        with temporary() as tmp, self.fixture(tmp), patch('environment.campaign_status',return_value='fresh'):
            environment.VENV.mkdir(); fake_venv([sys.executable,'-m','venv',str(environment.VENV)])
            with patch('environment.subprocess.run',return_value=subprocess.CompletedProcess([],0,stdout='',stderr='')) as run:
                environment.setup()
            self.assertEqual(run.call_count,1); self.assertEqual(run.call_args.args[0][-1],'check')
            self.assertTrue(read_json(environment.SCRATCH/'environment-ready.json')['reused_without_install'])

    def test_unknown_invalid_environment_is_untouched(self):
        with temporary() as tmp, self.fixture(tmp), patch('environment.campaign_status',return_value='fresh'):
            environment.VENV.mkdir(); fake_venv([sys.executable,'-m','venv',str(environment.VENV)])
            user=environment.VENV/'user.txt'; user.write_bytes(b'KEEP')
            with patch('environment.subprocess.run',return_value=subprocess.CompletedProcess([],7,stdout='',stderr='fixture mismatch')):
                with self.assertRaisesRegex(RuntimeError,'Unknown'): environment.setup()
            self.assertEqual(user.read_bytes(),b'KEEP')

    def test_unknown_partial_without_python_is_preserved(self):
        with temporary() as tmp, self.fixture(tmp), patch('environment.subprocess.run') as run:
            environment.VENV.mkdir(); (environment.VENV/'unknown').write_bytes(b'KEEP')
            with self.assertRaises(RuntimeError): environment.prepare_private_venv()
            run.assert_not_called(); self.assertTrue((environment.VENV/'unknown').exists())

    def test_owned_interrupted_venv_creation_resumes(self):
        with temporary() as tmp, self.fixture(tmp):
            with patch('environment.subprocess.run',side_effect=RuntimeError('interrupted')):
                with self.assertRaises(RuntimeError): environment.prepare_private_venv()
            anchor=read_json(environment.VENV/environment.OWNER_FILE)
            with patch('environment.subprocess.run',side_effect=fake_venv): environment.prepare_private_venv()
            self.assertEqual(anchor,read_json(environment.VENV/environment.OWNER_FILE))

    def test_owned_install_resume_preserves_previous_reports(self):
        with temporary() as tmp, self.fixture(tmp), patch('environment.campaign_status',return_value='fresh'):
            with patch('environment.subprocess.run',side_effect=fake_venv): environment.prepare_private_venv()
            owned=read_json(environment.SCRATCH/'environment-created.json'); owned.update(package_installation_started=True,stage='package_installation')
            write_json(environment.SCRATCH/'environment-created.json',owned)
            write_json(environment.SCRATCH/'pip-torch-report.json',{'fixture':'preserve'})
            with patch('environment.subprocess.run',return_value=subprocess.CompletedProcess([],1,stdout='',stderr='partial')), patch('environment.install_locked') as install:
                environment.setup(); install.assert_called_once()
            self.assertEqual(len(list(environment.SCRATCH.glob('setup-history-*/pip-torch-report.json'))),1)

    def test_pip_failure_propagates_no_readiness(self):
        with temporary() as tmp, self.fixture(tmp):
            with patch('environment.subprocess.run',side_effect=fake_venv): environment.prepare_private_venv()
            owned=read_json(environment.SCRATCH/'environment-created.json')
            with patch('environment.subprocess.run',side_effect=subprocess.CalledProcessError(9,['fixture'])):
                with self.assertRaises(subprocess.CalledProcessError): environment.install_locked(environment.VENV/'Scripts/python.exe',owned)
            self.assertFalse((environment.SCRATCH/'environment-ready.json').exists())

    def test_exact_versions_bitness_and_pip_check_enforced(self):
        lock=read_json(HERE/'runtime-lock.json')
        d=[SimpleNamespace(metadata={'Name':n},version=v) for n,v in lock['packages'].items()]
        for bits,code,expected in [(64,0,True),(32,0,False),(64,1,False)]:
            with patch('environment.importlib.metadata.distributions',return_value=d), patch('environment.struct.calcsize',return_value=bits//8), patch('environment.subprocess.run',return_value=subprocess.CompletedProcess([],code,stdout='',stderr='')):
                self.assertEqual(environment.package_check()['passed'],expected)
        d[0].version='wrong'
        with patch('environment.importlib.metadata.distributions',return_value=d), patch('environment.subprocess.run',return_value=subprocess.CompletedProcess([],0,stdout='',stderr='')):
            self.assertFalse(environment.package_check()['passed'])

    def test_wheel_hash_and_official_source_are_required(self):
        lock=read_json(HERE/'runtime-lock.json'); wheel=lock['historical_wheels'][0]
        for bad in ('hash','source','sdist'):
            with temporary() as tmp, self.fixture(tmp):
                url='https://evil.invalid/x.whl' if bad=='source' else wheel['url']
                if bad=='sdist': url=url.replace('.whl','.tar.gz')
                row={'metadata':{'name':wheel['name'],'version':wheel['version']},
                     'download_info':{'url':url,'archive_info':{'hashes':{'sha256':'wrong' if bad=='hash' else wheel['sha256']}}}}
                for phase in ('torch','packages'): write_json(environment.SCRATCH/f'pip-{phase}-report.json',{'install':[row]})
                with self.assertRaises((AssertionError,RuntimeError)): environment.validate_reports()


class ModelTests(unittest.TestCase):
    def tar(self,folder,path,extra=None):
        with tarfile.open(path,'w') as t:
            for p in folder.iterdir(): t.add(p,arcname='Qwen3-4B/'+p.name,recursive=False)
            if extra:
                info,data=extra; t.addfile(info,io.BytesIO(data) if data else None)

    def test_real_tiny_tar_import_hashes_before_publication(self):
        with temporary() as tmp:
            r=Path(tmp); lock=tiny_model(r/'source'); self.tar(r/'source',r/'model.tar')
            result=model_files.import_archive(r/'model.tar',r/'stage',lock,time.monotonic()+30,sha256(r/'model.tar'))
            self.assertTrue(result['passed']); self.assertEqual(result['files'],lock['files'])

    def test_official_ancillary_text_is_inspected_but_never_extracted(self):
        with temporary() as tmp:
            r=Path(tmp); lock=tiny_model(r/'source'); info=tarfile.TarInfo('Qwen3-4B/README.md'); info.size=4
            self.tar(r/'source',r/'model.tar',(info,b'text'))
            model_files.import_archive(r/'model.tar',r/'stage',lock,time.monotonic()+30,None)
            self.assertFalse((r/'stage/README.md').exists())

    def test_transport_checksum_mismatch_leaves_no_extraction(self):
        with temporary() as tmp:
            r=Path(tmp); lock=tiny_model(r/'source'); self.tar(r/'source',r/'model.tar')
            with self.assertRaisesRegex(ValueError,'transport'): model_files.import_archive(r/'model.tar',r/'stage',lock,time.monotonic()+30,'0'*64)
            self.assertFalse((r/'stage').exists())

    def test_new_transport_sidecar_and_historical_fallback(self):
        with temporary() as tmp:
            p=Path(tmp)/'Qwen3-4B.tar'
            self.assertEqual(model_files.transport_checksum(p),model_files.TRANSPORT_SHA256)
            sidecar=Path(str(p)+'.sha256');sidecar.write_text('A'*64+'  Qwen3-4B.tar\n')
            self.assertEqual(model_files.transport_checksum(p),'a'*64)
            self.assertEqual(model_files.transport_checksum(p,'B'*64),'b'*64)
            sidecar.write_text('A'*64+'  wrong.tar\n')
            with self.assertRaises(ValueError):model_files.transport_checksum(p)

    def test_traversal_absolute_ads_and_executables_rejected_before_extract(self):
        for name in ('../evil','/absolute','C:/evil','Qwen3-4B/x:ads','Qwen3-4B/evil.exe','Qwen3-4B/back\\slash','Qwen3-4B/trailing.'):
            with temporary() as tmp:
                r=Path(tmp); lock=tiny_model(r/'source'); info=tarfile.TarInfo(name); info.size=1
                self.tar(r/'source',r/'model.tar',(info,b'x'))
                with self.assertRaises(ValueError): model_files.import_archive(r/'model.tar',r/'stage',lock,time.monotonic()+30,None)
                self.assertFalse((r/'stage').exists())

    def test_links_duplicates_and_missing_files_rejected(self):
        for kind in ('symlink','hardlink','duplicate','missing'):
            with temporary() as tmp:
                r=Path(tmp); lock=tiny_model(r/'source')
                info=tarfile.TarInfo('Qwen3-4B/config.json'); data=b'x'
                if kind=='symlink': info.type=tarfile.SYMTYPE; info.linkname='../out'; data=b''
                elif kind=='hardlink': info.type=tarfile.LNKTYPE; info.linkname='../out'; data=b''
                elif kind=='duplicate': info.size=1
                if kind=='missing':
                    (r/'source/vocab.json').unlink(); self.tar(r/'source',r/'model.tar')
                else: self.tar(r/'source',r/'model.tar',(info,data))
                with self.assertRaises(ValueError): model_files.import_archive(r/'model.tar',r/'stage',lock,time.monotonic()+30,None)

    def test_correct_transport_does_not_substitute_for_model_pins(self):
        with temporary() as tmp:
            r=Path(tmp); lock=tiny_model(r/'source'); p=r/'source/vocab.json'; p.write_bytes(b'x'*p.stat().st_size)
            self.tar(r/'source',r/'model.tar')
            with self.assertRaisesRegex(ValueError,'MODEL_INTEGRITY_FAIL'): model_files.import_archive(r/'model.tar',r/'stage',lock,time.monotonic()+30,sha256(r/'model.tar'))
            self.assertTrue((r/'stage').exists())  # Failed stage retained for review.

    def test_fixed_archive_budget_is_not_extended(self):
        with temporary() as tmp:
            r=Path(tmp); lock=tiny_model(r/'source'); self.tar(r/'source',r/'model.tar')
            with self.assertRaises(TimeoutError): model_files.import_archive(r/'model.tar',r/'stage',lock,time.monotonic()-1,None)

    def test_valid_model_reuse_makes_no_network_request(self):
        with temporary() as tmp:
            r=Path(tmp); lock=tiny_model(r/'model'); scratch=r/'scratch'; scratch.mkdir()
            with patch.multiple(model_files,MODEL=r/'model',SCRATCH=scratch), patch('model_files.campaign_status',return_value='fresh'), patch('model_files.read_json',side_effect=lambda p: lock if Path(p).name=='model-lock.json' else read_json(p)), patch('model_files.import_archive') as imp:
                result=model_files.ensure_model('nonexistent.tar',True)
                self.assertTrue(result['reused']); self.assertFalse(result['downloaded']); imp.assert_not_called()

    def test_unknown_or_mismatched_model_is_never_overwritten(self):
        with temporary() as tmp:
            r=Path(tmp); lock=tiny_model(r/'model'); user=r/'model/vocab.json'; user.write_bytes(b'KEEP USER MODEL')
            with patch.multiple(model_files,MODEL=r/'model',SCRATCH=r/'scratch'), patch('model_files.campaign_status',return_value='fresh'), patch('model_files.read_json',side_effect=lambda p: lock if Path(p).name=='model-lock.json' else read_json(p)):
                with self.assertRaises(ValueError): model_files.ensure_model('irrelevant.tar')
            self.assertEqual(user.read_bytes(),b'KEEP USER MODEL')

    def test_fresh_without_model_requires_explicit_transfer_choice(self):
        with temporary() as tmp, patch('model_files.MODEL',Path(tmp)/'missing'), patch('model_files.campaign_status',return_value='fresh'):
            with self.assertRaisesRegex(FileNotFoundError,'ModelArchive'): model_files.ensure_model()


if __name__=='__main__': unittest.main(verbosity=2)
