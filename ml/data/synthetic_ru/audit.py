"""Bounded deduplication/contamination audit. Holdout labels are never consulted.

Thresholds are registered in source BEFORE the first holdout comparison. No nearest
holdout wording is available to generation. Reports store IDs/metrics, not holdout text.
"""
import argparse
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import json
from pathlib import Path
import random
import re

from core import HERE, ROOT, SEED, digest, dumps, read, write
from validate import validate_all

HOLDOUT_SHA256 = 'c32e0b688d0f0a3d7eda547c60cffdcef74c15c95ecfa941e7741adc7be89dc1'
THRESHOLDS = dict(exact=True,token_jaccard=0.60,token_bigram_jaccard=0.38,character_ratio=0.78)


def normalize(text):
    return ' '.join(re.findall(r'[а-яa-z0-9]+',text.casefold().replace('ё','е')))


def ngrams(items,n):
    return {tuple(items[i:i+n]) for i in range(len(items)-n+1)}


def jaccard(a,b):
    return len(a&b)/len(a|b) if a or b else 0.0


def features(text):
    norm=normalize(text)
    words=norm.split()
    return norm,set(words),ngrams(words,2),ngrams(norm,3)


def similarity(left,right):
    a,ta,ba,_=left
    b,tb,bb,_=right
    return dict(exact=a==b,token_jaccard=jaccard(ta,tb),token_bigram_jaccard=jaccard(ba,bb),
                character_ratio=SequenceMatcher(None,a,b,autojunk=False).ratio())


def suspicious(metrics):
    return metrics['exact'] or any(metrics[k]>=v for k,v in THRESHOLDS.items() if k!='exact')


def read_rows(base):
    rows=[json.loads(line) for split in ('train','dev','internal_test')
          for line in (base/(split+'.jsonl')).read_text(encoding='utf-8').splitlines()]
    ev=ROOT/'evals/local-qwen/dev-ru-v1.json' if base==HERE else base/'dev-ru-v1.json'
    return rows+read(ev)['cases']


def holdout_audit(rows):
    path=ROOT/'evals/local-qwen/a01-a16.json'
    if digest(path.read_bytes())!=HOLDOUT_SHA256:
        raise ValueError('HOLDOUT_HASH_DRIFT')
    # Only id/text projections are used. No expected JSON, allowed alternatives,
    # case descriptions, baseline outputs or per-case failures enter this audit.
    holdout=[(c['id'],features(c['text'])) for c in read(path)['cases']]
    highest_by_holdout={}
    highest_by_family={}
    flagged=[]
    exact=0
    for row in rows:
        f=features(row['text'])
        for hid,hf in holdout:
            metrics=similarity(f,hf)
            score=max(metrics['token_jaccard'],metrics['token_bigram_jaccard'],metrics['character_ratio'])
            item=dict(rowId=row['id'],split=row['split'],family=row['surfaceTemplateFamilyId'],holdoutId=hid,
                      similarity={k:round(v,6) if isinstance(v,float) else v for k,v in metrics.items()})
            if score>highest_by_holdout.get(hid,(-1,None))[0]:
                highest_by_holdout[hid]=(score,item)
            key=row['surfaceTemplateFamilyId']
            if score>highest_by_family.get(key,(-1,None))[0]:
                highest_by_family[key]=(score,item)
            if suspicious(metrics):
                flagged.append(item)
            exact+=metrics['exact']
    return dict(holdout_sha256=HOLDOUT_SHA256,thresholds=THRESHOLDS,comparisons=len(rows)*len(holdout),
                exact_matches=exact,flagged=flagged,
                nearest_per_holdout=[v[1] for _,v in sorted(highest_by_holdout.items())],
                top_family_neighbors=[v[1] for v in sorted(highest_by_family.values(),key=lambda x:-x[0])[:20]],
                expected_labels_used=False,raw_model_outputs_read=False,
                limitation='Lexical checks cannot prove absence of all semantic paraphrases; nearest pairs require manual review.')


def corpus_similarity(rows):
    """Full exact/group checks elsewhere; bounded rare-bigram candidate search here.

    Each utterance queries its eight rarest bigrams (max 200 postings each), then
    inspects the 24 candidates sharing most queried bigrams. All rows are queries.
    Character trigrams avoid unbounded quadratic edit-distance comparisons.
    """
    fs=[features(r['text']) for r in rows]
    index=defaultdict(list)
    for i,f in enumerate(fs):
        for g in f[2]:
            index[g].append(i)
    bins=Counter()
    cross_bins=Counter()
    pairs={}
    inspected=0
    for i,(r,f) in enumerate(zip(rows,fs)):
        votes=Counter()
        for g in sorted(f[2],key=lambda x:(len(index[x]),x))[:8]:
            # Stable spread through large postings, not only the beginning/TRAIN.
            postings=index[g]
            step=max(1,(len(postings)+199)//200)
            votes.update(postings[::step][:200])
        votes.pop(i,None)
        same=sorted(votes,key=lambda j:(-votes[j],rows[j]['id']))[:24]
        cross=sorted((j for j in votes if rows[j]['split']!=r['split']),key=lambda j:(-votes[j],rows[j]['id']))[:24]
        best=best_cross=0.0
        for j in set(same+cross):
            inspected+=1
            tok=jaccard(f[2],fs[j][2])
            char=jaccard(f[3],fs[j][3])
            score=max(tok,char)
            best=max(best,score)
            if rows[j]['split']!=r['split']:
                best_cross=max(best_cross,score)
                key=tuple(sorted((r['id'],rows[j]['id'])))
                if score>=0.65:
                    pairs[key]=dict(leftId=key[0],rightId=key[1],token_bigram_jaccard=round(tok,6),character_trigram_jaccard=round(char,6),
                                    sameContext=r['contextId']==rows[j]['contextId'],sameFamily=r['surfaceTemplateFamilyId']==rows[j]['surfaceTemplateFamilyId'])
        def band(v):
            return '<0.50' if v<.5 else '0.50-0.70' if v<.7 else '0.70-0.85' if v<.85 else '0.85-0.95' if v<.95 else '>=0.95'
        bins[band(best)]+=1
        cross_bins[band(best_cross)]+=1
    top=sorted(pairs.values(),key=lambda x:-max(x['token_bigram_jaccard'],x['character_trigram_jaccard']))[:30]
    counts=Counter(r['text'] for r in rows)
    by_intent={intent:dict(rows=len(rs),unique_texts=len({r['text'] for r in rs}),
                          repeated_text_occurrences=len(rs)-len({r['text'] for r in rs}))
               for intent in sorted({r['intent'] for r in rows}) if (rs:=[r for r in rows if r['intent']==intent])}
    cross_exact=defaultdict(set)
    for r in rows:
        cross_exact[normalize(r['text'])].add(r['split'])
    return dict(scope='All main/eval rows as queries; bounded 24 within/all + 24 cross-split neighbors from eight rare bigrams',
                inspected_candidate_pairs=inspected,unique_text_count=len(counts),repeated_text_occurrences=len(rows)-len(counts),
                exact_text_context_duplicates=0,duplicates_by_intent=by_intent,
                normalized_texts_shared_across_splits=sum(len(s)>1 for s in cross_exact.values()),
                nearest_similarity_distribution=dict(bins),cross_split_nearest_distribution=dict(cross_bins),
                top_cross_split_pairs=top,
                limitation='Candidate search is bounded, not exhaustive all-pairs semantic equivalence. Repeated text in distinct public contexts is retained.')


def statistics(rows,registry):
    def count(key,items):
        return dict(sorted(Counter(r[key] for r in items).items()))
    main=[r for r in rows if r['split']!='tuning_eval']
    critical=Counter(t for r in main for t in r['criticalityTags'])
    optional=['primaryTopicId','secondaryTopicId','factIds','argument','acknowledgementFactId','offerDraft','targetOfferId']
    nulls={intent:{k:sum(r['expected'][k] in (None,[]) for r in main if r['intent']==intent) for k in optional} for intent in sorted({r['intent'] for r in main})}
    return dict(main_total=len(main),examples_per_split=count('split',rows),examples_per_intent=count('intent',main),
                intent_by_split={s:count('intent',[r for r in rows if r['split']==s]) for s in sorted({r['split'] for r in rows})},
                contexts_count=len(registry),context_counts=dict(Counter(e['split'] for e in registry.values())),domain_distribution=count('domainFamily',main),
                styles=dict(Counter(t for r in main for t in r['styleTags'])),noise=dict(Counter(t for r in main for t in r['noiseTags'])),
                noisy_count=sum(bool(r['noiseTags']) for r in main),critical_counts=dict(critical),
                critical_rates={k:v/len(main) for k,v in critical.items()},
                eval_critical_counts=dict(Counter(t for r in rows if r['split']=='tuning_eval' for t in r['criticalityTags'])),
                active_offer_context_rows=sum(registry[r['contextId']]['publicContext']['activeOffer'] is not None for r in main),
                target_offer_bindings=sum(r['expected']['targetOfferId'] is not None for r in main),
                conditional_offers=critical['conditional_offer'],argument_bindings=sum(r['expected']['argument'] is not None for r in main),
                needs_clarification_count=sum(r['expected']['needsClarification'] for r in main),null_fields_by_intent=nulls,
                field_nonnull_counts={k:sum(r['expected'][k] not in (None,[]) for r in main) for k in optional},
                contrast_pairs=len({r['contrastPairId'] for r in main if r.get('contrastPairId')}),
                surface_families=len({r['surfaceTemplateFamilyId'] for r in main}),
                semantic_families=len({r['semanticFamilyId'] for r in main}),
                identifier_styles=dict(Counter(registry[r['contextId']]['identifierStyle'] for r in main)))


def review_selection(rows):
    selection={s:[r['id'] for r in random.Random(SEED+len(s)).sample([x for x in rows if x['split']==s],25)] for s in ('train','dev','internal_test')}
    for intent in sorted({r['intent'] for r in rows}):
        selection['intent:'+intent]=[r['id'] for r in random.Random(SEED+len(intent)).sample([x for x in rows if x['intent']==intent],5)]
    selection['safety_families']=list({r['surfaceTemplateFamilyId']:r['id'] for r in rows if 'prompt_injection' in r['criticalityTags']}.values())
    return selection


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=HERE)
    parser.add_argument('--output',type=Path,default=HERE/'audit_report.json')
    args=parser.parse_args()
    base=args.data_dir.resolve()
    rows,registry=read_rows(base),read(base/'contexts.json')
    validation=validate_all(rows,registry,True)
    if validation['errors']:
        raise ValueError(dumps(validation['errors'][:10]))
    # Record the authoring boundary before opening the holdout for lexical audit.
    freeze={p.name:digest(p.read_bytes()) for p in sorted(HERE.glob('*.py'))}
    freeze['system-prompt.txt']=digest((HERE/'system-prompt.txt').read_bytes())
    freeze['contexts.json']=digest((base/'contexts.json').read_bytes())
    write(ROOT/'.tmp/synthetic-ru-pre-holdout-authoring-freeze.json',freeze)
    print('Candidate source hashes frozen; starting text-only holdout lexical audit.',flush=True)
    holdout=holdout_audit(rows)
    print(dumps(dict(holdout_comparisons=holdout['comparisons'],flagged=len(holdout['flagged']))),flush=True)
    result=dict(authoring_hashes_before_holdout_audit=freeze,validation=validation,statistics=statistics(rows,registry),
                holdout=holdout,duplicates=corpus_similarity(rows),review_selection=review_selection(rows))
    write(args.output,result)
    print(dumps(dict(validation='PASS',statistics=result['statistics'],holdout_flags=len(holdout['flagged']),
                     top_cross_split_pairs=result['duplicates']['top_cross_split_pairs'][:3])))


if __name__=='__main__':
    main()
