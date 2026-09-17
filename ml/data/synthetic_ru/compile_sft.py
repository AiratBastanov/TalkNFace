"""Export conversational prompt/completion JSONL; no TRL or model dependency."""
import argparse
import json
from pathlib import Path
from core import HERE, ROOT, KEYS, dumps, read
from validate import validate_row


def compact_context(context):
    return dict(brief=context['publicBrief'], player=context['player'],
                issues=[[i['id'],i['label'],i['unit'],{v['id']:v['label'] for v in i['values']}] for i in context['issues']],
                topics={t['id']:t['label'] for t in context['topics']},
                facts={f['id']:f['text'] for f in context['knownFacts']},
                acknowledgementFactIds=context['acknowledgementFactIds'],
                arguments=[[a['claimId'],a['label'],a['supportingFactIds'],
                            [[p['issueId'],p['valueId']] for p in a['condition']]] for a in context['availableArguments']],
                active=[context['activeOffer']['id'],{t['issueId']:t['valueId'] for t in context['activeOffer']['terms']}]
                       if context['activeOffer'] else None)


def canonical_completion(expected):
    # Source schema insertion order is the canonical top-level order; nested keys
    # also have source-contract order. Arrays preserve catalog / evidence order.
    result = {k:expected[k] for k in KEYS}
    if result['argument']:
        a=result['argument']
        result['argument']=dict(claimId=a['claimId'],supportingFactIds=a['supportingFactIds'],
                                evidenceSpan=dict(start=a['evidenceSpan']['start'],end=a['evidenceSpan']['end']))
    if result['offerDraft']:
        d=result['offerDraft']
        terms=lambda xs:[dict(issueId=t['issueId'],valueId=t['valueId']) for t in xs]
        result['offerDraft']=dict(terms=terms(d['terms']),conditionalOn=terms(d['conditionalOn']) if d['conditionalOn'] else None)
    result['evidenceSpans']=[dict(start=s['start'],end=s['end']) for s in result['evidenceSpans']]
    return dumps(result)


def compile_row(row,registry,checked=False):
    if not checked:
        errors,unknown=validate_row(row,registry)
        if errors or unknown:
            raise ValueError('Invalid SFT target: '+dumps(errors+unknown))
    return dict(prompt=[dict(role='system',content=(HERE/'system-prompt.txt').read_text(encoding='utf-8').strip()),
                        dict(role='user',content=dumps(dict(context=compact_context(registry[row['contextId']]['publicContext']),
                                                           utterance=row['text'])))],
                completion=[dict(role='assistant',content=canonical_completion(row['expected']))])


def safe_output(path):
    path=Path(path).resolve()
    # Expanded exports can be large: keep them in ignored scratch, never canonical/raw/model files.
    if not path.is_relative_to(ROOT/'.tmp'):
        raise ValueError('Expanded SFT exports must be under workspace .tmp/')
    path.parent.mkdir(parents=True,exist_ok=True)
    return path


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split',choices=['train','dev'],required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    registry=read(HERE/'contexts.json')
    target=safe_output(args.output)
    count=0
    # Exclusive output prevents accidental replacement of any prior export.
    with target.open('x',encoding='utf-8',newline='\n') as stream:
        for line in (HERE/(args.split+'.jsonl')).read_text(encoding='utf-8').splitlines():
            stream.write(dumps(compile_row(json.loads(line),registry))+'\n')
            count+=1
    print(dumps(dict(rows=count,output=str(target),format='conversational_prompt_completion',training='NOT_STARTED')))
