"""Fresh-process reload of base NF4 + saved adapter; one unused TRAIN forward."""
import argparse
import time
import traceback
from common import SCRATCH, ADAPTER, AccessGuard, read_json, write_json, start_safety_watch, sha256
from train_smoke import quantized_base, tensor_hash
from offload import memory


def verify(limit, result):
    import torch
    from peft import PeftModel
    torch.cuda.set_device(0)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.cuda.reset_peak_memory_stats()
    result['before_reload'] = memory(torch)
    trained = read_json(SCRATCH / f'train-{limit}.json')
    assert trained['passed']
    for name,entry in trained['adapter']['files'].items():
        assert sha256(ADAPTER/str(limit)/name)==entry['sha256']
    data = read_json(SCRATCH / f'data-{limit}.json')
    row = data['reload_row']
    assert row['id'] not in [x['id'] for x in trained['microbatches']]
    assert row['id'] not in data['selection']['selected_ids'] and row['split'] == 'train'
    model = PeftModel.from_pretrained(quantized_base(), ADAPTER / str(limit), is_trainable=False,
                                      local_files_only=True)
    model.config.use_cache = False
    model.eval()
    assert model.active_adapters == ['default']
    assert all(p.device.type == 'cuda' for p in model.parameters())
    actual = {n: tensor_hash(p) for n, p in model.named_parameters() if 'lora_' in n}
    assert actual == trained['adapter_final_tensor_hashes'], 'Reloaded adapter values differ'
    prompt = torch.tensor([row['input_ids'][:row['prompt_length']]], device='cuda')
    with torch.inference_mode(), torch.autocast('cuda', dtype=torch.float16):
        output = model(input_ids=prompt, attention_mask=torch.ones_like(prompt), use_cache=False, logits_to_keep=1)
    torch.cuda.synchronize()
    assert bool(torch.isfinite(output.logits).all())
    result.update(passed=True, active_adapters=model.active_adapters, adapter_tensors_equal=True,
                  row_id=row['id'], prompt_tokens=prompt.shape[1], logits_shape=list(output.logits.shape),
                  logits_finite=True, generated_tokens=0, quality_evaluation=False, after_reload=memory(torch))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-length', type=int, choices=[1536], default=1536)
    args = parser.parse_args()
    guard = AccessGuard('reload').install()
    start_safety_watch()
    result = {'passed': False}
    started = time.monotonic()
    try:
        verify(args.max_length, result)
        print('Fresh-process adapter reload and unused TRAIN forward passed', flush=True)
    except Exception:
        result['error'] = traceback.format_exc()
        raise
    finally:
        result.update(seconds=time.monotonic()-started, audit=guard.report())
        write_json(SCRATCH / f'reload-{args.max_length}.json', result)
