"""Local-only gate paths, audit boundary, and durable small JSON records."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCRATCH = ROOT / '.tmp/qlora-offload-smoke'
MODEL = ROOT / 'AlagModels/Qwen3-4B'
ADAPTER = ROOT / 'AlagModels/adapters/qlora-offload-smoke'
DATA = ROOT / 'ml/data/synthetic_ru'
TRAIN = DATA / 'train.jsonl'
FORBIDDEN = (DATA / 'dev.jsonl', DATA / 'internal_test.jsonl',
             ROOT / 'evals/local-qwen/dev-ru-v1.json', ROOT / 'evals/local-qwen/a01-a16.json')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def configure_offline():
    import tempfile
    tempfile.tempdir = str(SCRATCH)
    os.environ['TMP'] = str(SCRATCH)
    os.environ['TEMP'] = str(SCRATCH)
    for name in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_DATASETS_OFFLINE',
                 'HF_HUB_DISABLE_TELEMETRY', 'DO_NOT_TRACK'):
        os.environ[name] = '1'
    os.environ['HF_HOME'] = str(SCRATCH / 'hf')
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    sys.dont_write_bytecode = True


class AccessGuard:
    """Python audit-hook guard; not a security sandbox for arbitrary native code.

    Workers cannot read eval files, raw datasets, or prior receipts. All writes
    must stay in this gate's scratch/adapter roots; source model is read-only.
    Hash auditing is a separate process and never passes holdout contents here.
    """
    def __init__(self, phase, tokenizer_only=False):
        self.phase = phase
        self.tokenizer_only = tokenizer_only
        self.reads = set()
        self.denied = []
        self.started = time.time()

    def check(self, path, write=False):
        p = Path(path).resolve()
        if p == Path(os.devnull).resolve():
            return  # dill probes the Windows null device during torch import.
        if write:
            allowed = p.is_relative_to(SCRATCH) or p.is_relative_to(ADAPTER)
        else:
            if p.is_relative_to(ROOT):
                allowed = (p.is_relative_to(HERE) or p.is_relative_to(SCRATCH)
                           or p.is_relative_to(MODEL) or p.is_relative_to(ADAPTER)
                           or p.is_relative_to(ROOT / '.venv-qlora-smoke')
                           or p == TRAIN or p == DATA / 'system-prompt.txt'
                           or p == ROOT / 'evals/local-qwen/interpretation.schema.json'
                           or ((p.is_relative_to(DATA) or p.is_relative_to(ROOT / 'ml/baseline'))
                               and p.suffix in ('.py', '.pyc')))
            else:
                allowed = True  # installed interpreter / Windows runtime libraries
            allowed = allowed and p not in FORBIDDEN
            if self.tokenizer_only and p.is_relative_to(MODEL) and p.suffix == '.safetensors':
                allowed = False
        if not allowed:
            self.denied.append({'path': str(p), 'write': write})
            raise PermissionError(f'{self.phase}: forbidden access: {p}')
        if not write and p.is_relative_to(ROOT) and not p.is_relative_to(ROOT / '.venv-qlora-smoke'):
            self.reads.add(p.relative_to(ROOT).as_posix())

    def hook(self, event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            mode, flags = args[1], args[2]
            write = (isinstance(mode, str) and any(x in mode for x in 'wax+')) or bool(
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
            self.check(os.fsdecode(args[0]), write)
        elif event in ('os.remove', 'os.rmdir', 'os.mkdir'):
            self.check(args[0], True)
        elif event in ('os.rename', 'os.replace'):
            self.check(args[0], True)
            self.check(args[1], True)
        elif event in ('socket.connect', 'socket.getaddrinfo'):
            raise PermissionError('Network disabled in gate worker')

    def install(self):
        configure_offline()
        SCRATCH.mkdir(parents=True, exist_ok=True)
        sys.addaudithook(self.hook)
        return self

    def report(self):
        return {'phase': self.phase, 'reads': sorted(self.reads), 'denied': self.denied,
                'evaluation_file_reads': sorted(set(self.reads) & {p.relative_to(ROOT).as_posix() for p in FORBIDDEN}), 'network_allowed': False,
                'limitation': 'Python audit hooks cover Python opens; native safetensors model reads are separately hash-audited.'}


def start_safety_watch():
    """Cooperative self-exit on supervisor cancellation; OS releases owned CUDA state."""
    import threading
    name=os.environ.get('QLORA_PHASE','worker')
    stop=Path(os.environ.get('QLORA_STOP_FILE',SCRATCH/f'{name}-stop.json'))
    assert stop.resolve().is_relative_to(SCRATCH)
    write_json(SCRATCH/f'{name}-worker.json',{'pid':os.getpid(),'parent_pid':os.getppid()})
    def watch():
        while True:
            if stop.exists():
                write_json(SCRATCH/f'{name}-cancelled.json',read_json(stop))
                os._exit(75)
            time.sleep(0.1)
    thread=threading.Thread(target=watch,daemon=True);thread.start()
