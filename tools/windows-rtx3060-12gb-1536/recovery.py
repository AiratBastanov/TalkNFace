"""Owner-side identification/backup of the specific interrupted materializer.

No installer is executed. This helper never repairs unknown files or touches
historical gates; repair is the reviewed source delivered in this directory.
"""
import json
from pathlib import Path
import shutil
from common import sha256, write_json


def identify_partial(source, candidate):
    inventory = []
    for path in sorted(Path(candidate).rglob('*')):
        if path.is_symlink() or path.is_junction(): raise ValueError('Ambiguous reparse point')
        if not path.is_file(): continue
        rel = path.relative_to(candidate); original = Path(source) / rel
        if not original.is_file() or rel.name == 'RUN-1536-REMOTE.ps1': raise ValueError('Unrelated candidate file: '+str(rel))
        if path.suffix in ('.py','.ps1','.json','.md','.txt'):
            expected = original.read_text(encoding='utf-8-sig')
            for old,new in [('RTX3070_TARGETED_LORA_1536_ENVELOPE','RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE'),
                            ('RTX3070_TARGETED_QV_R8_1536','RTX3060_12GB_TARGETED_QV_R8_1536'),
                            ('rtx3070-targeted-1536-smoke','rtx3060-12gb-targeted-1536-smoke')]:
                expected = expected.replace(old,new)
            actual = path.read_text(encoding='utf-8-sig')
            if rel.name == 'config.json':
                config = json.loads(expected)
                config['remote_resources'].update(physical_vram_min_MiB=12000,gpu_index=0,gpu_capability=[8,6],
                    nvidia_min_free_before_training_MiB=10800,cuda_min_free_before_training_MiB=10500,
                    minimum_boundary_free_bytes=268435456,comfortable_boundary_free_bytes=536870912)
                matches = json.loads(actual) == config
            else: matches = actual == expected
        else: matches = path.read_bytes() == original.read_bytes()
        if not matches: raise ValueError('Ambiguous candidate content: '+str(rel))
        inventory.append({'path':rel.as_posix(),'bytes':path.stat().st_size,'sha256':sha256(path)})
    if not inventory: raise ValueError('Empty candidate is not the identified interruption')
    return inventory


def preserve_partial(source, candidate, backup):
    inventory = identify_partial(source, candidate)
    backup = Path(backup)
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copytree(candidate, backup / 'partial-gate')
    for row in inventory:
        assert sha256(backup / 'partial-gate' / row['path']) == row['sha256']
    write_json(backup / 'inventory.json', inventory)
    return inventory
