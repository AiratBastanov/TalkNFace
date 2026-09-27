"""Small durable records and paths for V1. No ML imports or model execution."""
import contextlib
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LEGACY = ROOT / 'tools/windows-rtx3060-12gb-1536'
DATA = ROOT / 'ml/data/synthetic_ru'
MODEL = ROOT / 'AlagModels/Qwen3-4B'
ORIGIN = 'https://github.com/AiratBastanov/TalkNFace.git'
GATE = 'QWEN3_4B_FULL_TRAINING_PREPARATION'
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read(path):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'Duplicate JSON key')
            result[k] = v
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, 'Nonfinite JSON'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pin(path):
    return {'bytes': Path(path).stat().st_size, 'sha256': sha(path)}


def atomic(path, value, immutable=False, preserve_order=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with tmp.open('xb') as stream:
        payload = json.dumps(value, ensure_ascii=True, sort_keys=False, separators=(',', ':'), allow_nan=False).encode() if preserve_order else canonical(value)
        stream.write(payload + b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    if immutable:
        # Windows rename refuses an existing destination. Never rewrite run facts.
        require(not path.exists(), 'Immutable record already exists')
        tmp.rename(path)
    else:
        os.replace(tmp, path)


def no_links(path):
    path = Path(path).absolute()
    for p in (path, *path.parents):
        require(not p.is_symlink() and not p.is_junction(), 'Reparse point refused')
    return path.resolve()


class Layout:
    def __init__(self, run_id, root=ROOT):
        require(bool(re.fullmatch(r'qwen3-4b-v1(?:-[a-z0-9]{1,32})?', run_id)), 'Invalid V1 RunId')
        self.run_id = run_id
        self.base = no_links(root / '.tmp/qwen3-4b-full-training' / run_id)
        self.runtime = self.base / 'runtime'
        self.checkpoints = self.base / 'checkpoints'
        self.adapter = self.base / 'adapter'
        self.results = no_links(root / 'handoff-results/qwen3-4b-full-training' / run_id)
        for p in (self.runtime, self.checkpoints, self.adapter):
            no_links(p)


class OperationLock:
    """OS byte-range lock: process death releases it; a stale file is harmless."""
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        no_links(self.path)
        self.stream = self.path.open('a+b')
        if self.stream.tell() == 0:
            self.stream.write(b'0')
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise RuntimeError('Another operation owns this run') from None
        return self

    def __exit__(self, *unused):
        if os.name == 'nt':
            import msvcrt
            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        self.stream.close()


def legacy(name):
    if str(LEGACY) not in sys.path:
        sys.path.append(str(LEGACY))
    return importlib.import_module(name)


def config():
    return read(HERE / 'candidate-v1.json')


def offline(runtime):
    import tempfile
    runtime.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(runtime)
    for k in ('TMP', 'TEMP'):
        os.environ[k] = str(runtime)
    for k in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_DATASETS_OFFLINE',
              'HF_HUB_DISABLE_TELEMETRY', 'DO_NOT_TRACK'):
        os.environ[k] = '1'
    os.environ['HF_HOME'] = str(runtime / 'hf')
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    sys.dont_write_bytecode = True


class AccessGuard:
    """Defense in depth for Python I/O, not a native-code security sandbox."""
    def __init__(self, layout, tokenizer_only=False):
        self.layout, self.tokenizer_only = layout, tokenizer_only
        self.denied = 0

    def check(self, path, write=False):
        p = Path(path).resolve()
        if p == Path(os.devnull).resolve():
            return
        if write:
            ok = p.is_relative_to(self.layout.base)
        elif p.is_relative_to(ROOT):
            ok = (p.is_relative_to(HERE) or p.is_relative_to(LEGACY)
                  or p.is_relative_to(self.layout.base) or p.is_relative_to(MODEL)
                  or p.is_relative_to(Path(sys.prefix).resolve())
                  or p in (DATA / 'train.jsonl', DATA / 'system-prompt.txt',
                           ROOT / 'evals/local-qwen/interpretation.schema.json')
                  or (p.suffix in ('.py', '.pyc') and
                      (p.is_relative_to(DATA) or p.is_relative_to(ROOT / 'ml/baseline'))))
        else:
            ok = True  # installed Python/Windows libraries
        if self.tokenizer_only and p.is_relative_to(MODEL) and p.suffix == '.safetensors':
            ok = False
        if not ok:
            self.denied += 1
            raise PermissionError('TRAIN-only I/O boundary')

    def hook(self, event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            mode, flags = args[1:3]
            write = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)))
            self.check(os.fsdecode(args[0]), write)
        elif event in ('os.remove', 'os.rmdir', 'os.mkdir'):
            self.check(args[0], True)
        elif event in ('os.rename', 'os.replace'):
            self.check(args[0], True)
            self.check(args[1], True)
        elif event.startswith('socket.') and event != 'socket.__new__':
            raise PermissionError('Network disabled')

    def install(self):
        offline(self.layout.runtime)
        sys.addaudithook(self.hook)
        return self


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True, encoding='utf-8',
                                   timeout=30, creationflags=NO_WINDOW).strip()


def operational_error(layout, phase, error_type, code):
    # Never mutate run.json, checkpoint receipts or completed.json here.
    path = layout.runtime / 'operations.json'
    old = read(path) if path.exists() else {}
    atomic(path, dict(old, last_error_phase=phase, error_type=error_type,
                      native_returncode=code, updated_unix=time.time()))


@contextlib.contextmanager
def phase(layout, name, **details):
    atomic(layout.runtime / 'phase.json', dict(phase=name, started_unix=time.time(), **details))
    yield
