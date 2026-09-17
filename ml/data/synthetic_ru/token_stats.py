"""Existing local tokenizer only. A process audit hook forbids weights/network access."""
import argparse
import json
import math
import os
from pathlib import Path
import statistics
import sys
from core import HERE, ROOT, dumps, read, write
from compile_sft import compile_row


def protect(event,args):
    if event=='open' and isinstance(args[0],(str,bytes)) and str(args[0]).lower().endswith(('.safetensors','.bin','.pt','.pth')):
        raise PermissionError('Token measurement cannot open model weights')
    if event in ('socket.connect','socket.getaddrinfo'):
        raise PermissionError('Tokenizer statistics are offline')


def percentiles(values):
    values=sorted(values)
    return dict(count=len(values),median=statistics.median(values),
                **{f'p{p}':values[math.ceil(p/100*len(values))-1] for p in (90,95,99)},max=max(values),
                fraction_at_most_1536=sum(x<=1536 for x in values)/len(values))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',type=Path,default=HERE)
    parser.add_argument('--output',type=Path,default=HERE/'token_statistics.json')
    args=parser.parse_args()
    os.environ['HF_HUB_OFFLINE']='1'
    os.environ['TRANSFORMERS_OFFLINE']='1'
    os.environ['TOKENIZERS_PARALLELISM']='false'
    sys.addaudithook(protect)
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(str(ROOT/'AlagModels/Qwen3-4B'),local_files_only=True,trust_remote_code=False)
    registry=read(args.data_dir/'contexts.json')
    by_split={}
    all_lengths=[]
    for split in ('train','dev','internal_test','tuning_eval'):
        eval_path=ROOT/'evals/local-qwen/dev-ru-v1.json' if args.data_dir==HERE else args.data_dir/'dev-ru-v1.json'
        rows=read(eval_path)['cases'] if split=='tuning_eval' else [json.loads(s) for s in (args.data_dir/(split+'.jsonl')).read_text(encoding='utf-8').splitlines()]
        lengths=[]
        for start in range(0,len(rows),128):
            batch=[compile_row(r,registry,checked=True) for r in rows[start:start+128]]
            conversations=[x['prompt']+x['completion'] for x in batch]
            tokenized=tokenizer.apply_chat_template(conversations,tokenize=True,add_generation_prompt=False,enable_thinking=False)
            ids=tokenized['input_ids'] if hasattr(tokenized,'keys') else tokenized
            lengths.extend(map(len,ids))
        by_split[split]=percentiles(lengths)
        if split!='tuning_eval':
            all_lengths.extend(lengths)
        print(dumps(dict(split=split,tokens=by_split[split])),flush=True)
    result=dict(tokenizer='existing AlagModels/Qwen3-4B',weights_opened=False,network_used=False,
                enable_thinking=False,add_generation_prompt=False,chat_template_included=True,
                sequence='system + user + assistant completion including chat special tokens',
                method='nearest-rank percentiles; exact tokenization, no truncation',all=percentiles(all_lengths),by_split=by_split)
    write(args.output,result)


if __name__=='__main__':
    main()
