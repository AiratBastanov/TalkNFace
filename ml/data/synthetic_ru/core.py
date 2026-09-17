"""Shared serialization and semantic truth. No model, holdout or external text access."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
VERSION = 'ru-v1.0.0'
SEED = 20260917
SPLITS = ('train', 'dev', 'internal_test')
SCHEMA = json.loads((ROOT / 'evals/local-qwen/interpretation.schema.json').read_text(encoding='utf-8'))
KEYS = tuple(SCHEMA['properties'])
INTENTS = SCHEMA['properties']['intent']['enum']
WEIGHTS = dict(ask_question=9, probe_interest=7, argument=9, offer=12,
              counter_offer=10, concession=9, objection=9, pressure=6,
              empathy=5, clarification=7, reveal_information=6, close_attempt=5, walk_away=6)
EVAL_COUNTS = {intent: 16+dict(offer=24,counter_offer=24,clarification=32,objection=16).get(intent,0) for intent in INTENTS}


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else dumps(value).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path).resolve()
    # All outputs must be explicitly inside this R&D area, eval-dev or .tmp.
    allowed = [HERE, ROOT / '.tmp', ROOT / 'docs/gates/evidence']
    if not any(path.is_relative_to(p) for p in allowed) and path != ROOT / 'evals/local-qwen/dev-ru-v1.json':
        raise ValueError('Refusing output outside approved derivative paths: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def u16(text):
    return len(text.encode('utf-16-le')) // 2


def unmark(marked):
    """Author-defined support intervals; offsets calculated AFTER surface/noise realization."""
    text, spans, cursor = '', [], 0
    for match in re.finditer(r'\[\[(.*?)\]\]', marked):
        text += marked[cursor:match.start()]
        start = u16(text)
        text += match[1]
        spans.append({'start': start, 'end': u16(text)})
        cursor = match.end()
    text += marked[cursor:]
    if not 1 <= len(spans) <= 4 or '[[' in text or ']]' in text:
        raise ValueError('Invalid authored evidence markup')
    return text, spans


def term(context, index, value):
    issue = context['issues'][index]
    return {'issueId': issue['id'], 'valueId': issue['values'][value]['id']}


def interpretation(case, context):
    """Build bindings from semantic case BEFORE realization, never classify Russian text."""
    intent, op = case['intent'], case['op']
    focus, values = case['focus'], case['values']
    out = dict(schemaVersion=1, intent=intent, tone=case.get('tone', 'neutral'),
               primaryTopicId=None, secondaryTopicId=None, factIds=[], argument=None,
               acknowledgementFactId=None, offerDraft=None, targetOfferId=None,
               evidenceSpans=[], needsClarification=False, clarification=None)
    if op in ('question', 'numeric_question', 'probe', 'meaning', 'boundary', 'reject_value',
              'reveal', 'argument', 'unsupported_reason', 'two_topics', 'pressure', 'empathy'):
        # Explicit public topic; a price issue without a corresponding topic stays null.
        out['primaryTopicId'] = case['topic']
    if op == 'two_topics':
        out['secondaryTopicId'] = case['secondaryTopic']
    if op in ('fact', 'ack', 'argument'):
        out['factIds'] = [context['knownFacts'][case['fact']]['id']]
    if op == 'ack':
        out['acknowledgementFactId'] = out['factIds'][0]
    if 'mentionedFact' in case:
        out['factIds'] = [context['knownFacts'][case['mentionedFact']]['id']]
        if case.get('acknowledges'):
            out['acknowledgementFactId'] = out['factIds'][0]
    if op == 'argument':
        arg = context['availableArguments'][case['fact']]
        out['argument'] = {'claimId': arg['claimId'], 'supportingFactIds': arg['supportingFactIds'][:], 'evidenceSpan': None}
    commitments = {'full', 'conditional', 'replace', 'inherit', 'inherit_one', 'partial',
                   'alternatives', 'range', 'approximate', 'unknown_value', 'contradiction', 'negated_value'}
    if op in commitments:
        excluded = case.get('excluded', [])
        terms = [term(context, i, v) for i, v in enumerate(values) if i not in excluded]
        if op in ('inherit', 'inherit_one'):
            inherited = case['inherit']
            active = {t['issueId']: t for t in context['activeOffer']['terms']}
            terms = [active[context['issues'][i]['id']] if i in inherited else term(context, i, v)
                     for i, v in enumerate(values) if i not in excluded]
        condition = [term(context, case['condition'], values[case['condition']])] if op == 'conditional' else None
        out['offerDraft'] = {'terms': terms, 'conditionalOn': condition}
        if excluded:
            out['needsClarification'] = True
            labels = ', '.join(context['issues'][i]['label'].lower() for i in excluded)
            out['clarification'] = 'Уточните точное значение: ' + labels + '.'
    if intent in ('counter_offer', 'close_attempt'):
        if context['activeOffer'] is None:
            raise ValueError('Binding intent requires active public offer')
        out['targetOfferId'] = context['activeOffer']['id']
    if op in ('missing_target', 'missing_target_terms', 'unclear_target', 'brainstorm', 'injection', 'unresolved_commitment'):
        out['needsClarification'] = True
        out['clarification'] = {
            'missing_target': 'Какой полный набор условий вы хотите согласовать?',
            'missing_target_terms': 'Уточните остальные условия: активного предложения для переноса нет.',
            'unclear_target': 'Вы имеете в виду текущее активное предложение?',
            'brainstorm': 'Это предложение для согласования или пока обсуждение вариантов?',
            'unresolved_commitment': 'Какие точные значения всех пунктов вы предлагаете?',
            'injection': 'Уточните вопрос об открытых условиях переговоров.'}[op]
        if op == 'missing_target_terms':
            out['offerDraft'] = {'terms': [term(context, focus, values[focus])], 'conditionalOn': None}
    return {key: out[key] for key in KEYS}
