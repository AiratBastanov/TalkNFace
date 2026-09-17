"""Deterministic semantic-case -> target -> surface pipeline. Does not read holdout."""
import argparse
import random
from collections import Counter
from pathlib import Path

from contexts import make_contexts
from core import HERE, ROOT, SEED, VERSION, WEIGHTS, EVAL_COUNTS, digest, dumps, interpretation, term, unmark, write
from templates import families


def eligible(family, entry):
    if entry['split'] != ('dev' if family['split']=='tuning_eval' else family['split']):
        return False
    c = entry['publicContext']
    if family['intent'] in ('counter_offer', 'close_attempt') or family['op'] == 'unclear_target':
        return c['activeOffer'] is not None
    if family['op'] in ('missing_target', 'missing_target_terms'):
        return c['activeOffer'] is None
    if family['op'] == 'argument':
        return bool(c['availableArguments'])
    return True


def semantic_case(family, entry, rng):
    c = entry['publicContext']
    n = len(c['issues'])
    focus = rng.randrange(n)
    case = dict(intent=family['intent'], op=family['op'], focus=focus,
                values=[rng.randrange(len(i['values'])) for i in c['issues']], topic=entry['topicByIssue'][focus])
    op = family['op']
    if op in ('fact', 'ack', 'argument'):
        fact = rng.randrange(2)
        case.update(fact=fact, focus=fact, topic=entry['topicByIssue'][fact])
        if op == 'argument':
            case['values'][fact] = 1
    if op in ('partial', 'alternatives', 'range', 'approximate', 'unknown_value', 'contradiction'):
        case['excluded'] = [focus]
    if op == 'conditional':
        case['condition'] = (focus + 1) % n
    if op in ('inherit', 'inherit_one'):
        case['inherit'] = [i for i in range(n) if i != focus] if op == 'inherit' else [(focus + 1) % n]
        case['excluded'] = []
        active_value = next(i for i, v in enumerate(c['issues'][focus]['values'])
                            if v['id'] == c['activeOffer']['terms'][focus]['valueId'])
        case['values'][focus] = (active_value + 1 + rng.randrange(2)) % 3
    if op == 'two_topics':
        available = [t['id'] for t in c['topics']]
        case['topic'] = case['topic'] or available[0]
        case['secondaryTopic'] = next(t for t in available if t != case['topic'])
    if family['intent'] == 'pressure':
        case['tone'] = 'threat'
    if family['intent'] == 'objection':
        case['tone'] = 'accusatory' if family['id'].endswith('accusation') else 'respectful_firm'
    return case


NUMBERS = {'68': 'шестьдесят восемь', '74': 'семьдесят четыре', '82': 'восемьдесят две',
           '46': 'сорок шесть', '58': 'пятьдесят восемь', '72': 'семьдесят два',
           '36': 'тридцать шесть', '48': 'сорок восемь', '62': 'шестьдесят две',
           '600': 'шестьсот', '900': 'девятьсот', '1200': 'тысяча двести'}


def slots(case, entry, word_numbers=False, split='train'):
    c = entry['publicContext']
    values, focus, op = case['values'], case['focus'], case['op']
    def value_phrase(i, value):
        phrase = c['issues'][i]['values'][value]['label']
        if word_numbers:
            first, *rest = phrase.split(' ')
            if first in NUMBERS:
                phrase = ' '.join([NUMBERS[first], *rest])
        return phrase
    def clause(i, value):
        return c['issues'][i]['label'].lower() + ': ' + value_phrase(i, value)
    inherited = case.get('inherit', [])
    effective = values[:]
    if inherited:
        for i in inherited:
            effective[i] = next(j for j, v in enumerate(c['issues'][i]['values']) if v['id'] == c['activeOffer']['terms'][i]['valueId'])
    excluded = case.get('excluded', [])
    specified = [i for i in range(len(values)) if i not in (excluded or inherited)]
    fact = case.get('fact', 0)
    fact_text = c['knownFacts'][fact]['text'].rstrip('.')
    fact_text = fact_text[0].lower() + fact_text[1:]
    topic2 = next((t['label'].lower() for t in c['topics'] if t['id'] == case.get('secondaryTopic')), '')
    topic = next((t['label'].lower() for t in c['topics'] if t['id'] == case['topic']), c['issues'][focus]['label'].lower())
    argument_clause = {
        'train': f'условие «{clause(fact, 1)}» стоит учесть, потому что {fact_text}',
        'dev': f'из открытого обстоятельства «{fact_text}» привожу довод в пользу варианта «{clause(fact, 1)}»',
        'internal_test': f'при варианте «{clause(fact, 1)}» можно учесть обстоятельство «{fact_text}», поэтому считаю выбор обоснованным',
        'tuning_eval': f'я обосновываю выбор «{clause(fact, 1)}» тем, что {fact_text}',
    }[split]
    return dict(topic=topic, topic2=topic2, term=clause(focus, values[focus]),
                package='; '.join(clause(i, v) for i, v in enumerate(effective)),
                specified='; '.join(clause(i, values[i]) for i in specified),
                inherited='; '.join(clause(i, effective[i]) for i in inherited),
                condition=clause(case.get('condition', 0), values[case.get('condition', 0)]),
                choice_a=value_phrase(focus, values[focus]), choice_b=value_phrase(focus, (values[focus]+1)%3),
                other_value=value_phrase(focus, (values[focus]+1)%3), fact=fact_text,
                argument_clause=argument_clause,
                domain_title=c['publicBrief'].split('. ')[0].lower())


def surface(family, case, entry, index):
    import re
    word_numbers = index % 7 == 0
    marked = family['text'].format(**slots(case, entry, word_numbers, family['split']))
    prefix, style = [('', 'neutral'), ('Коллеги, ', 'formal'), ('Если коротко: ', 'concise'),
                     ('Давайте по делу. ', 'conversational')][int(digest([family['id'],index,'style'])[:8],16)%4]
    if prefix in ('Коллеги, ', 'Если коротко: '):
        marked = re.sub(r'^(\[\[)?([А-ЯЁ])', lambda m: (m[1] or '')+m[2].lower(), marked)
    marked = prefix + marked
    noise = []
    noise_roll = int(digest([family['id'], index, 'noise'])[:8], 16) % 100
    if noise_roll < 6:
        mode = noise_roll
        if mode == 0:
            marked = marked.lower()
            noise = ['lowercase']
        elif mode == 1:
            marked = marked.replace('.', '').replace(',', '').replace('?', '')
            noise = ['missing_punctuation']
        elif mode == 2:
            marked = 'Колеги, ' + marked
            noise = ['minor_typo']
        elif mode == 3:
            marked = '🙂 ' + marked
            noise = ['emoji']
        elif mode == 4:
            marked = 'Пжл., ' + marked
            noise = ['abbreviation']
        else:
            marked = marked.replace(': ', ' — ')
            noise = ['dash_punctuation']
    text, spans = unmark(marked)
    has_words = bool(re.search(r'\b(шестьдесят|семьдесят|восемьдесят|сорок|пятьдесят|тридцать|шестьсот|девятьсот|тысяча|три|шесть|девять|два|четыре)\b',text.lower()))
    return text, spans, [style] + (['number_words'] if has_words else []), noise


def row(family, cid, entry, index, seed=SEED, contrast_pair=None, fixed_case=None):
    rng = random.Random(int(digest([seed, VERSION, family['id'], cid, index])[:16], 16))
    case = fixed_case or semantic_case(family, entry, rng)
    expected = interpretation(case, entry['publicContext'])  # truth is constructed first
    text, spans, styles, noise = surface(family, case, entry, index)
    expected['evidenceSpans'] = spans
    if expected['argument']:
        expected['argument']['evidenceSpan'] = spans[0].copy()
    tags = []
    import re
    if re.search(r'\b(не|нет|без|кроме|исключаю|исключает|исключающих|исключают)\b', text.lower()):
        tags.append('negation')
    if expected['needsClarification'] and case['op'] != 'injection':
        tags.append('ambiguity')
    if case['op'] == 'injection':
        tags.append('prompt_injection')
    if case['op'] in ('inherit', 'inherit_one'):
        tags.append('counter_offer_inheritance')
    if expected['offerDraft'] and expected['offerDraft']['conditionalOn']:
        tags.append('conditional_offer')
    if family['intent'] in ('offer', 'concession', 'counter_offer', 'close_attempt'):
        tags.append('commitment')
    if cid.endswith('no_price_topic'):
        tags.append('no_plausible_topic_id')
    provenance = dict(source_type='PROJECT_SYNTHETIC', generator_version=VERSION, root_seed=seed,
                      semantic_family_id=family['semanticFamilyId'], surface_template_family_id=family['surfaceTemplateFamilyId'],
                      context_id=cid, case_index=index)
    result = dict(id='ru-'+digest([family['id'], cid, index])[:16], split=family['split'], contextId=cid,
                  text=text, expected=expected, intent=case['intent'], criticalityTags=tags,
                  semanticFamilyId=family['semanticFamilyId'], surfaceTemplateFamilyId=family['surfaceTemplateFamilyId'],
                  domainFamily=entry['domainFamily'], styleTags=styles, noiseTags=noise,
                  provenance=provenance, generatorVersion=VERSION, semanticCase=case)
    if contrast_pair:
        result['contrastPairId'] = contrast_pair
    return result


CONTRASTS = [
 ('question_need', ('ask_question','question','По пункту [[«{topic}»]] [[какие варианты есть]]?'), ('probe_interest','probe','По пункту [[«{topic}»]] [[какой вариант вам важнее и почему]]?')),
 ('offer_counter', ('offer','full','[[Выдвигаю новый пакет]]: [[{package}]].'), ('counter_offer','replace','[[Выдвигаю пакет взамен вашего активного]]: [[{package}]].')),
 ('offer_concession', ('offer','full','[[Предлагаю условия]]: [[{package}]].'), ('concession','full','[[Уступаю относительно прежней позиции до условий]]: [[{package}]].')),
 ('refusal_exit', ('objection','boundary','[[Мне не подходит ваш подход к пункту «{topic}», но переговоры продолжаю]].'), ('walk_away','exit','[[Мне не подходит ваш подход к пункту «{topic}», поэтому переговоры окончательно прекращаю]].')),
 ('feeling_fact', ('empathy','empathy','[[Понимаю ваше беспокойство по пункту «{topic}»]].'), ('empathy','ack','[[Понимаю и учитываю ваш открытый факт: {fact}]].')),
 ('ack_accept', ('empathy','ack','[[Услышал ваш факт: {fact}]]. [[Пакет этим не принимаю]].'), ('close_attempt','accept','[[Услышал ваш факт: {fact}]]. [[Текущий пакет этим принимаю целиком]].')),
 ('meaning_ambiguity', ('clarification','meaning','[[Уточните значение пункта «{topic}»]]; решение о пакете не выражаю.'), ('offer','partial','[[Предлагаю {specified}]]; [[значение другого пункта ещё не выбрал]].')),
 ('information_offer', ('reveal_information','reveal','[[Для внутреннего обсуждения записали {package}]]. [[Предложения вам пока нет]].'), ('offer','full','[[Для согласования с вами предлагаю {package}]].')),
 ('threat_boundary', ('pressure','pressure','[[Если не уступите по пункту «{topic}», добьюсь вашей замены]].'), ('objection','boundary','[[По пункту «{topic}» сам уступить не готов]].')),
]


def contrast_rows(registry, seed):
    result = []
    contexts = [(cid, e) for cid, e in registry.items() if e['publicContext']['activeOffer'] and e['split']=='train']
    for name, left, right in CONTRASTS:
        for index in range(12):
            cid, entry = contexts[(index*11) % len(contexts)]
            for side, (intent, op, text) in enumerate((left, right)):
                group = 'contrast.'+name
                family = dict(id=group+'.'+str(side), split='train', intent=intent, op=op, text=text,
                              semanticFamilyId=group, surfaceTemplateFamilyId=group)
                # Same semantic slots and surface variation; only the authored cue changes.
                rng = random.Random(int(digest([seed, group, cid, index])[:16],16))
                case = semantic_case(family, entry, rng)
                if name == 'ack_accept':
                    case.update(fact=0, mentionedFact=0, acknowledges=True)
                item = row(family, cid, entry, index, seed, group+f'.{index}', case)
                result.append(item)
    return result


def generate(seed=SEED):
    registry, recipes = make_contexts(), families()
    if len({f['id'] for f in recipes}) != len(recipes):
        raise ValueError('Duplicate semantic/surface recipe ID')
    rows = contrast_rows(registry, seed)
    seen = {(x['contextId'], x['text']) for x in rows}
    rejected = []
    for split, size in [('train',8000), ('dev',1000), ('internal_test',1000), ('tuning_eval',sum(EVAL_COUNTS.values()))]:
        present = Counter(x['intent'] for x in rows if x['split'] == split)
        for intent, weight in WEIGHTS.items():
            target = size * weight // 100 if split != 'tuning_eval' else EVAL_COUNTS[intent]
            needed = target - present[intent]
            selected = [f for f in recipes if f['split'] == split and f['intent'] == intent]
            for fi, family in enumerate(selected):
                count = needed // len(selected) + (fi < needed % len(selected))
                allowed = [(cid,e) for cid,e in sorted(registry.items()) if eligible(family,e)]
                rng = random.Random(int(digest([seed, family['id'], 'contexts'])[:16],16))
                rng.shuffle(allowed)
                index, accepted = 0, 0
                while accepted < count:
                    if index > 20000:
                        raise RuntimeError('Family exhausted: '+family['id'])
                    cid, entry = allowed[index % len(allowed)]
                    item = row(family, cid, entry, index, seed)
                    index += 1
                    pair = (cid,item['text'])
                    if pair in seen:
                        rejected.append(dict(family=family['id'], case_index=index-1, reason='duplicate_text_context'))
                        continue
                    seen.add(pair)
                    rows.append(item)
                    accepted += 1
    return registry, rows, rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE)
    parser.add_argument('--check', action='store_true', help='Compare generated bytes; do not overwrite locked data.')
    args = parser.parse_args()
    output = args.output.resolve()
    if output != HERE and not output.is_relative_to(ROOT / '.tmp'):
        raise ValueError('Generation only allowed in R&D folder or workspace .tmp; raw sources are immutable')
    registry, rows, rejected = generate()
    from validate import validate_all
    report = validate_all(rows, registry, require_counts=True)
    if report['errors']:
        write(ROOT / '.tmp/synthetic-ru-generation-failures.json', report)
        raise ValueError(dumps(report['errors'][:5]))
    blobs = {'contexts.json': __import__('json').dumps(registry,ensure_ascii=False,indent=2)+'\n'}
    for split in ('train','dev','internal_test'):
        blobs[split+'.jsonl'] = ''.join(dumps(x)+'\n' for x in rows if x['split']==split)
    eval_data = dict(version='dev-ru-v1', TUNING_EVAL_ALLOWED=True, source_type='PROJECT_SYNTHETIC',
                     contextRegistry='ml/data/synthetic_ru/contexts.json', cases=[x for x in rows if x['split']=='tuning_eval'])
    blobs['dev-ru-v1.json'] = __import__('json').dumps(eval_data,ensure_ascii=False,indent=2)+'\n'
    # Once created, INTERNAL_TEST is immutable. A mismatching regeneration cannot overwrite it.
    internal = output / 'internal_test.jsonl'
    if output == HERE and internal.exists() and internal.read_bytes() != blobs['internal_test.jsonl'].encode():
        raise ValueError('INTERNAL_TEST_LOCKED: create a new versioned gate, do not rewrite this holdout')
    for name, content in blobs.items():
        target = ROOT/'evals/local-qwen/dev-ru-v1.json' if name=='dev-ru-v1.json' and output==HERE else output/name
        if args.check:
            if target.read_bytes() != content.encode():
                raise ValueError('Reproduction mismatch: '+str(target))
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(content,encoding='utf-8',newline='\n')
    if not args.check:
        write(output/'generation_report.json', dict(seed=SEED, generatorVersion=VERSION,
              families=len(families())+len(CONTRASTS), rejectedCandidates=rejected, validation=report,
              internal_test_lock_sha256=digest(blobs['internal_test.jsonl'].encode())))
    print(dumps(dict(reproducible=args.check, rows=len(rows), contexts=len(registry), validation=report)))


if __name__ == '__main__':
    main()
