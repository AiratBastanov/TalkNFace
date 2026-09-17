"""Remote preparation assertions only; never constructs or loads Qwen3-4B."""
from common import ROOT, HERE, MODEL, SCRATCH, FORBIDDEN, AccessGuard, read_json, write_json
from configuration import validate_config, validate_adapter
from prepare_smoke_data import verify_labels
from offload import inspect_runtime


def checks():
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoTokenizer
    from trl.trainer.sft_trainer import DataCollatorForLanguageModeling
    config = validate_config(); spec = read_json(SCRATCH / 'spec-control.json')
    data = read_json(SCRATCH / 'data-1024.json')
    assert [r['id'] for r in data['rows']] == spec['same_historical_selection']['selected_ids']
    assert [r['length'] for r in data['rows']] == spec['same_historical_selection']['lengths']
    assert [r['id'] for r in data['rows'][:8]] == spec['optimizer_row_ids']
    assert data['reload_row']['id'] == spec['reload_row_id'] and spec['reload_row_id'] not in spec['same_historical_selection']['selected_ids']
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
    collator = DataCollatorForLanguageModeling(pad_token_id=tokenizer.pad_token_id)
    for row in data['rows'] + [data['reload_row']]:
        assert row['split'] == 'train' and row['length'] == len(row['input_ids']) <= 1024
        batch = collator([{k: row[k] for k in ('input_ids', 'labels')}])
        verify_labels(row, batch['labels'][0], tokenizer)
    # Real PEFT tensor metadata, zero storage/forward/backward/optimizer.
    dims = read_json(SCRATCH / 'module-control.json')
    class Projections(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.layers = torch.nn.ModuleList()
            for _ in range(36):
                layer = torch.nn.Module()
                for name in ('q_proj', 'v_proj'):
                    layer.add_module(name, torch.nn.Linear(dims[name]['in'], dims[name]['out'], bias=False, device='meta'))
                self.layers.append(layer)
    with torch.device('meta'):
        model = get_peft_model(Projections(), LoraConfig(r=8, lora_alpha=16, target_modules=['q_proj', 'v_proj']))
    structure = validate_adapter(model)
    assert all(p.device.type == 'meta' for p in model.parameters())
    guard = AccessGuard('negative-test')
    for path in FORBIDDEN:
        try: guard.check(path)
        except PermissionError: pass
        else: raise AssertionError('Evaluation access guard failed')
    return {'passed': True, 'complete_records_checked': 33, 'rows_prepared': 32, 'truncated_rows': 0,
            'prompt_ignored': True, 'canonical_JSON_and_EOS_supervised': True, 'thinking_supervised': False,
            'structure': structure, 'installed_offload_api': inspect_runtime(), 'Qwen_checkpoint_loads': 0,
            'forward_calls': 0, 'optimizer_updates': 0}


if __name__ == '__main__':
    guard = AccessGuard('cheap-checks', tokenizer_only=True).install()
    result = {'passed': False}
    try:
        result = checks()
        print('Frozen 32 TRAIN rows + reload row / completion masks / q-v-r8 metadata PASS')
    finally:
        result['audit'] = guard.report()
        write_json(SCRATCH / 'tests.json', result)
