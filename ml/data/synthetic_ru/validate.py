"""Strict contract/catalog checks plus semantic truth and corpus isolation checks."""
import argparse
from collections import Counter, defaultdict
import copy
import json
import re
import sys

from core import HERE, ROOT, SCHEMA, SEED, VERSION, INTENTS, EVAL_COUNTS, digest, dumps, interpretation, read, write
sys.path.insert(0, str(ROOT/'ml/baseline'))
# Pure helpers only. Never call score/match, load holdout labels or run baseline.
from scoring import schema_errors, public_semantics, span_text

PUBLIC_KEYS = {'revision','turnNumber','player','publicBrief','issues','topics','knownFacts',
               'acknowledgementFactIds','availableArguments','activeOffer'}
PRIVATE_KEYS = {'reservation','utility','trust','tension','aspiration','score','scoring','outcome',
                'hiddenFacts','hiddenInterests','witnessTraces','demographics','personality','worker_id','assignment_id',
                'privateBrief','batna','goals','interests','participants','policy','evaluation'}
PII = [re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}'),
       re.compile(r'(?:\+7|\+1|\+44)\s*\(?\d{3}\)?[\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}'),
       re.compile(r'\b(?:worker_id|assignment_id|MTurk|big-five|demographics|personality)\b',re.I),
       re.compile(r'\b(?:ул\.|улица|проспект|e-mail|email)\s',re.I)]

_RECIPES = None


def recipe_for(row):
    global _RECIPES
    if _RECIPES is None:
        from templates import families
        from generate import CONTRASTS
        _RECIPES = {(f['semanticFamilyId'],f['intent'],f['op']): f for f in families()}
        for name,left,right in CONTRASTS:
            for side,(intent,op,text) in enumerate((left,right)):
                group='contrast.'+name
                _RECIPES[(group,intent,op)]=dict(id=group+'.'+str(side),split='train',intent=intent,op=op,text=text,
                                               semanticFamilyId=group,surfaceTemplateFamilyId=group)
    return _RECIPES[(row['semanticFamilyId'],row['intent'],row['semanticCase']['op'])]


def privacy_errors(value, path='$'):
    errors = []
    if isinstance(value,dict):
        errors += [path+'.'+k+': private field' for k in value if k in PRIVATE_KEYS]
        for k,v in value.items():
            errors += privacy_errors(v,path+'.'+k)
    elif isinstance(value,list):
        for i,v in enumerate(value):
            errors += privacy_errors(v,f'{path}[{i}]')
    elif isinstance(value,str):
        errors += [path+': obvious identifier' for p in PII if p.search(value)]
    return errors


def validate_context(entry):
    c = entry['publicContext']
    errors = privacy_errors(c)
    if set(c) != PUBLIC_KEYS:
        errors.append('context: public allowlist mismatch')
    if set(c['player']) != {'roleId','label','briefing'}:
        errors.append('context: player allowlist mismatch')
    facts = {f['id'] for f in c['knownFacts']}
    issues = {i['id']: {v['id'] for v in i['values']} for i in c['issues']}
    topics = {t['id'] for t in c['topics']}
    if len(issues)!=len(c['issues']) or len(topics)!=len(c['topics']) or len(facts)!=len(c['knownFacts']):
        errors.append('context: duplicate catalog ID')
    if not set(c['acknowledgementFactIds']) <= facts:
        errors.append('context: unknown acknowledgement fact')
    if any(t is not None and t not in topics for t in entry['topicByIssue']):
        errors.append('context: bad topic fixture mapping')
    for arg in c['availableArguments']:
        if not set(arg['supportingFactIds']) <= facts:
            errors.append('context: unknown argument facts')
        for p in arg['condition']:
            if p['issueId'] not in issues or p['valueId'] not in issues.get(p['issueId'],set()):
                errors.append('context: unknown argument condition')
    if c['activeOffer']:
        terms = c['activeOffer']['terms']
        if {t['issueId'] for t in terms} != set(issues) or len(terms)!=len(issues):
            errors.append('context: active offer not complete')
        if any(t['valueId'] not in issues.get(t['issueId'],set()) for t in terms):
            errors.append('context: active offer value')
    return errors


def validate_row(row, registry):
    errors, unknown = [], []
    if row['contextId'] not in registry:
        return ['context: unknown context'], ['contextId']
    context = registry[row['contextId']]['publicContext']
    if registry[row['contextId']]['split'] != ('dev' if row['split']=='tuning_eval' else row['split']):
        errors.append('context split leakage')
    obj = row['expected']
    errors += schema_errors(obj,SCHEMA)
    if errors:
        return errors,unknown
    sem,unknown = public_semantics(obj,dict(publicContext=context,text=row['text']))
    errors += sem
    errors += privacy_errors(obj) + privacy_errors(row['text'])
    truth = interpretation(row['semanticCase'],context)
    truth['evidenceSpans'] = obj['evidenceSpans']
    if truth['argument']:
        truth['argument']['evidenceSpan'] = obj['argument']['evidenceSpan'] if obj['argument'] else None
    if truth != obj:
        errors.append('semantic case: changed truth or null discipline')
    if row['intent'] != obj['intent'] or obj['intent'] not in INTENTS:
        errors.append('intent metadata mismatch')
    if obj['argument']:
        span = obj['argument']['evidenceSpan']
        if not any(s['start'] <= span['start'] < span['end'] <= s['end'] for s in obj['evidenceSpans']):
            errors.append('argument span not covered')
        arg = next((a for a in context['availableArguments'] if a['claimId']==obj['argument']['claimId']),None)
        case = row['semanticCase']
        if arg:
            for condition in arg['condition']:
                idx = next(i for i,v in enumerate(context['issues']) if v['id']==condition['issueId'])
                if context['issues'][idx]['values'][case['values'][idx]]['id'] != condition['valueId']:
                    errors.append('argument condition not supported by semantic case')
    if row['semanticCase']['op']=='injection':
        forbidden = ['argument','offerDraft','targetOfferId','acknowledgementFactId','primaryTopicId','secondaryTopicId']
        if any(obj[k] is not None for k in forbidden) or obj['factIds'] or obj['intent']!='clarification':
            errors.append('injection emitted bindings')
    prov = row['provenance']
    if prov != dict(source_type='PROJECT_SYNTHETIC',generator_version=VERSION,root_seed=SEED,
                    semantic_family_id=row['semanticFamilyId'],surface_template_family_id=row['surfaceTemplateFamilyId'],
                    context_id=row['contextId'],case_index=prov.get('case_index')):
        errors.append('provenance mismatch')
    if not 0 < len(row['text'].encode('utf-16-le'))//2 <= 2000:
        errors.append('text outside contract bounds')
    # Verify the immutable authored realization, not a heuristic classifier.
    # A valid target attached to edited/negated language must fail validation.
    from generate import surface
    try:
        family=recipe_for(row)
        text,spans,styles,noise=surface(family,row['semanticCase'],registry[row['contextId']],prov['case_index'])
        if row['text']!=text or obj['evidenceSpans']!=spans or row['styleTags']!=styles or row['noiseTags']!=noise:
            errors.append('authored realization or evidence mismatch')
        if obj['argument'] and obj['argument']['evidenceSpan']!=spans[0]:
            errors.append('argument evidence differs from authored support')
    except (KeyError,ValueError,IndexError):
        errors.append('unknown or malformed semantic recipe')
    return errors,unknown


def validate_all(rows,registry,require_counts=False):
    errors, unknown = [], []
    groups = defaultdict(set)
    ids, pairs, canonical = set(),set(),set()
    duplicate_counts = Counter()
    for cid,entry in registry.items():
        errors += [dict(id=cid,error=e) for e in validate_context(entry)]
    for row in rows:
        err,refs = validate_row(row,registry)
        errors += [dict(id=row['id'],error=e) for e in err]
        unknown.extend(refs)
        for kind,value,seen in [('id',row['id'],ids),('text_context',(row['text'],row['contextId']),pairs),
                                ('canonical',dumps({k:v for k,v in row.items() if k not in ('id','split','provenance')}),canonical)]:
            if value in seen:
                duplicate_counts[kind] += 1
                errors.append(dict(id=row['id'],error='duplicate '+kind))
            seen.add(value)
        for key in ('semanticFamilyId','surfaceTemplateFamilyId','contrastPairId'):
            if row.get(key):
                groups[(key,row[key])].add(row['split'])
    leakage = [dict(kind=k[0],family=k[1],splits=sorted(v)) for k,v in groups.items() if len(v)>1]
    errors += [dict(id=x['family'],error='split group leakage') for x in leakage]
    counts = Counter(x['split'] for x in rows)
    if require_counts:
        if counts != dict(train=8000,dev=1000,internal_test=1000,tuning_eval=sum(EVAL_COUNTS.values())):
            errors.append(dict(error='count mismatch',counts=dict(counts)))
        train_intents = Counter(x['intent'] for x in rows if x['split']=='train')
        if set(train_intents)!=set(INTENTS) or min(train_intents.values()) < 350:
            errors.append(dict(error='train intent floor',counts=dict(train_intents)))
        main = [x for x in rows if x['split']!='tuning_eval']
        critical = Counter(t for x in main for t in x['criticalityTags'])
        if critical['negation'] < 1000 or critical['ambiguity'] < 1000 or not 300<=critical['prompt_injection']<=500:
            errors.append(dict(error='critical coverage below threshold',counts=dict(critical)))
        noisy = sum(bool(x['noiseTags']) for x in main)
        if not 500 <= noisy <= 800:
            errors.append(dict(error='noise outside 5-8 percent',count=noisy))
    return dict(rows=len(rows),schema_and_semantic_valid=len(rows)-len({x['id'] for x in errors if 'id'in x}),
                errors=errors, unknownIds=unknown,duplicates=dict(duplicate_counts),groupLeakage=leakage,counts=dict(counts))


def load_rows():
    rows=[]
    for split in ('train','dev','internal_test'):
        rows += [json.loads(line) for line in (HERE/(split+'.jsonl')).read_text(encoding='utf-8').splitlines()]
    rows += read(ROOT/'evals/local-qwen/dev-ru-v1.json')['cases']
    return rows


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    args=parser.parse_args()
    result=validate_all(load_rows(),read(HERE/'contexts.json'),True)
    if args.output:
        write(args.output,result)
    print(dumps(result))
    raise SystemExit(bool(result['errors']))
