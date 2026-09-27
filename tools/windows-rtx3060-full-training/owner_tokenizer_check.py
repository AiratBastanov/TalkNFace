"""Real 8000-row compiler/tokenizer check only. The audit guard rejects model weights."""
import json
import os
import sys
import time
import uuid
from full_common import HERE, MODEL, ROOT, AccessGuard, Layout, atomic, pin, read, require
from full_data import prepare_records, project_contexts, TrainRecords, validate_order

os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # this owner-only check cannot execute CUDA


def main():
    started = time.monotonic()
    layout = Layout('qwen3-4b-v1-owner' + uuid.uuid4().hex[:8])
    layout.runtime.mkdir(parents=True)
    baseline = read(HERE / 'accepted-baseline.json')
    for name, expected in baseline['data_and_compiler_pins'].items():
        require(pin(ROOT / name) == expected, 'Data/compiler pin changed')
    tokenizer_files = {n: v for n, v in baseline['model']['files'].items() if not n.endswith('.safetensors')}
    for name, expected in tokenizer_files.items():
        require(pin(MODEL / name) == expected, 'Tokenizer pin changed')
    project_contexts(layout.runtime)
    guard = AccessGuard(layout, tokenizer_only=True).install()
    from transformers import AutoTokenizer
    from trl.trainer.sft_trainer import DataCollatorForLanguageModeling
    import torch
    from full_common import legacy
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True, trust_remote_code=False)
    summary = prepare_records(layout.runtime, tokenizer)
    records = TrainRecords(layout.runtime, summary)
    collator = DataCollatorForLanguageModeling(pad_token_id=tokenizer.pad_token_id)
    for i in range(8000):
        row = records[i]
        batch = collator([{k: row[k] for k in ('input_ids', 'labels')}])
        legacy('prepare_smoke_data').verify_labels(row, batch['labels'][0], tokenizer)
    # Negative controls use the real accepted tokenizer/labels, not an invented mask.
    for index, value in ((0, 1), (row['eos_index'], -100)):
        broken = list(row['labels'])
        broken[index] = value
        try:
            legacy('prepare_smoke_data').verify_labels(row, broken, tokenizer)
        except AssertionError:
            pass
        else:
            raise AssertionError('Corrupt prompt/EOS mask was accepted')
    records.close()
    require(not torch.cuda.is_initialized(), 'Owner check must not initialize CUDA')
    require(guard.denied == 0, 'Unexpected denied access in real preparation path')
    for name, expected in tokenizer_files.items():
        require(pin(MODEL / name) == expected, 'Tokenizer was modified')
    report = {'passed': True, 'kind': 'real_accepted_train_tokenizer_and_compiler', 'summary': summary,
              'actual_TRL_collator_masks_checked': 8000, 'negative_mask_controls': 2, 'model_weight_loads': 0, 'inference_calls': 0,
              'CUDA_initialized': False, 'optimizer_updates': 0, 'evaluation_calls': 0,
              'holdout_example_files_opened': 0, 'seconds': time.monotonic() - started}
    atomic(layout.runtime / 'owner-tokenizer-result.json', report, immutable=True)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
