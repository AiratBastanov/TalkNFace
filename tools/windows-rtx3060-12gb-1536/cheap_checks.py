"""Cheap 1536 preparation assertions; tokenizer/meta tensors only, never Qwen weights."""
from common import HERE, MODEL, SCRATCH, FORBIDDEN, AccessGuard, read_json, write_json
from configuration import validate_config, validate_adapter
from prepare_smoke_data import verify_labels
from offload import inspect_runtime


def checks():
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoTokenizer
    from trl.trainer.sft_trainer import DataCollatorForLanguageModeling
    config = validate_config()
    data = read_json(SCRATCH / 'data-1536.json')
    selection = data['selection']
    from selection import validate_selection
    validate_selection(selection)
    rows = data['rows']; reload_row = data['reload_row']
    assert data['max_length'] == config['training']['max_length'] == 1536
    assert len(rows) == 8 and len({r['id'] for r in rows}) == 8
    assert selection['source_rows_measured'] == selection['eligible_rows'] == 8000
    assert selection['observed_max_length'] == 1421 and selection['rows_above_limit'] == selection['truncated_rows'] == 0
    assert [r['id'] for r in rows] == selection['selected_ids']
    assert [r['id'] for r in rows[:4]] == selection['optimizer_step_1_ids']
    assert [r['id'] for r in rows[4:]] == selection['optimizer_step_2_ids']
    assert reload_row['id'] == selection['reload_id'] and reload_row['id'] not in selection['selected_ids']
    assert min(r['length'] for r in rows[4:]) >= max(r['length'] for r in rows[:4])
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
    collator = DataCollatorForLanguageModeling(pad_token_id=tokenizer.pad_token_id)
    for row in rows + [reload_row]:
        assert row['split'] == 'train' and row['length'] == len(row['input_ids']) <= 1536
        batch = collator([{k: row[k] for k in ('input_ids', 'labels')}])
        verify_labels(row, batch['labels'][0], tokenizer)
    dims = read_json(SCRATCH / 'module-control.json')
    class Projections(torch.nn.Module):
        def __init__(self):
            super().__init__(); self.layers = torch.nn.ModuleList()
            for _ in range(36):
                layer = torch.nn.Module()
                for name in ('q_proj', 'v_proj'):
                    layer.add_module(name, torch.nn.Linear(dims[name]['in'], dims[name]['out'], bias=False, device='meta'))
                self.layers.append(layer)
    with torch.device('meta'):
        model = get_peft_model(Projections(), LoraConfig(r=8, lora_alpha=16, target_modules=['q_proj', 'v_proj']))
    structure = validate_adapter(model)
    assert all(p.device.type == 'meta' for p in model.parameters())
    guard = AccessGuard('negative-test-1536')
    for path in FORBIDDEN:
        try: guard.check(path)
        except PermissionError: pass
        else: raise AssertionError('Evaluation access guard failed')
    return {'passed': True, 'source_rows_measured': 8000, 'complete_records_checked': 9, 'rows_prepared': 8,
            'configured_max_length': 1536, 'observed_max_length': 1421, 'truncated_rows': 0,
            'prompt_ignored': True, 'canonical_JSON_and_EOS_supervised': True, 'thinking_supervised': False,
            'structure': structure, 'installed_offload_api': inspect_runtime(), 'Qwen_checkpoint_loads': 0,
            'forward_calls': 0, 'optimizer_updates': 0}


if __name__ == '__main__':
    guard = AccessGuard('cheap-checks-1536', tokenizer_only=True).install()
    result = {'passed': False}
    try:
        result = checks()
        print('Full TRAIN envelope measured; eight longest TRAIN rows + reload / masks / q-v-r8 metadata PASS')
    finally:
        result['audit'] = guard.report()
        write_json(SCRATCH / 'tests.json', result)
