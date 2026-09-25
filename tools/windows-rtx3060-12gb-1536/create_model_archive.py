"""Owner-authorized deterministic TAR export; byte operations only, no model load."""
import hashlib
import shutil
import tarfile
import time
from common import MODEL, HERE, SCRATCH, read_json, write_json, reject_reparse
from model_files import verify_model, inspect_archive, bounded_hash, check_time
from state import OperationLock

BUDGET = 600


def verify_tar_files(path, lock, deadline):
    with tarfile.open(path, 'r:') as archive:
        for entry,name in inspect_archive(archive, lock):
            digest = hashlib.sha256()
            with archive.extractfile(entry) as f:
                while block := f.read(8*2**20):
                    check_time(deadline); digest.update(block)
            assert digest.hexdigest() == lock['files'][name]['sha256'], 'TAR model pin mismatch: '+name
            print('TAR payload verified: '+name, flush=True)


def create():
    deadline=time.monotonic()+BUDGET
    folder=SCRATCH/'transfer'; reject_reparse(folder)
    folder.mkdir(parents=True,exist_ok=True)
    archive=folder/'Qwen3-4B.tar'; lock=read_json(HERE/'model-lock.json')
    verify_model(deadline=deadline)
    if not archive.exists():
        if shutil.disk_usage(folder).free < sum(p['bytes'] for p in lock['files'].values())+2**30:
            raise RuntimeError('Insufficient disk for model TAR; nothing overwritten')
        partial=folder/('Qwen3-4B-'+__import__('uuid').uuid4().hex+'.partial.tar')
        with tarfile.open(partial,'x',format=tarfile.USTAR_FORMAT) as tar:
            for name,pin in sorted(lock['files'].items()):
                check_time(deadline)
                info=tarfile.TarInfo('Qwen3-4B/'+name); info.size=pin['bytes']; info.mode=0o644; info.mtime=0
                class Reader:
                    def __init__(self, stream): self.stream=stream; self.count=0; self.report=0
                    def read(self,n):
                        check_time(deadline)
                        block=self.stream.read(n); self.count+=len(block)
                        if self.count-self.report>=256*2**20:
                            self.report=self.count; print(f'TAR writing {name}: {self.count}/{pin["bytes"]} bytes',flush=True)
                        return block
                with (MODEL/name).open('rb') as source: tar.addfile(info,Reader(source))
        verify_tar_files(partial,lock,deadline)
        partial.rename(archive)
    else:
        verify_tar_files(archive,lock,deadline)
    digest=bounded_hash(archive,deadline)
    sidecar=archive.with_suffix('.tar.sha256')
    sidecar.write_text(digest.upper()+'  '+archive.name+'\n',encoding='ascii')
    record={'archive':archive.relative_to(SCRATCH).as_posix(),'bytes':archive.stat().st_size,
            'sha256':digest,'model_files_verified':True,'deadline_seconds':BUDGET,'Qwen_checkpoint_loads':0}
    write_json(folder/'transport-receipt.json',record)
    print('ARCHIVE: '+str(archive),flush=True);print('SHA256: '+digest.upper(),flush=True)


if __name__=='__main__':
    with OperationLock(): create()
