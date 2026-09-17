"""Strict schema, public-context and frozen semantic-oracle scoring; no repair."""
import json
import math
import re
import statistics


def strict_json(text):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('Duplicate JSON key: ' + key)
            out[key] = value
        return out

    def constant(value):
        raise ValueError('Non-JSON number: ' + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def schema_errors(value, schema, path='$'):
    """The exact keyword subset emitted by Zod for the versioned contract."""
    supported = {'$schema', 'type', 'properties', 'required', 'additionalProperties', 'anyOf',
                 'enum', 'const', 'items', 'minItems', 'maxItems', 'minLength', 'maxLength',
                 'minimum', 'maximum', 'pattern'}
    if set(schema) - supported:
        raise ValueError('Unsupported schema keywords: ' + str(set(schema) - supported))
    types = {'object': isinstance(value, dict), 'array': isinstance(value, list),
             'string': isinstance(value, str), 'null': value is None, 'boolean': type(value) is bool,
             'number': type(value) in (int, float) and math.isfinite(value),
             'integer': type(value) in (int, float) and math.isfinite(value) and int(value) == value}
    if 'anyOf' in schema:
        branches = [(branch, schema_errors(value, branch, path)) for branch in schema['anyOf']]
        if any(not errors for _, errors in branches):
            return []
        # Preserve nested object/array paths instead of hiding them behind nullable anyOf.
        compatible = [errors for branch, errors in branches if types.get(branch.get('type'), False)]
        return min(compatible, key=len) if compatible else [path + ': anyOf/type']
    if not types[schema['type']]:
        return [path + ': type ' + schema['type']]
    errors = []
    if 'const' in schema and value != schema['const']:
        errors.append(path + ': const')
    if 'enum' in schema and value not in schema['enum']:
        errors.append(path + ': enum')
    if isinstance(value, dict):
        errors += [path + '.' + k + ': required' for k in schema.get('required', []) if k not in value]
        if schema.get('additionalProperties') is False:
            errors += [path + '.' + k + ': extra key' for k in value if k not in schema['properties']]
        for key, item in value.items():
            if key in schema.get('properties', {}):
                errors += schema_errors(item, schema['properties'][key], path + '.' + key)
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0) or len(value) > schema.get('maxItems', math.inf):
            errors.append(path + ': array length')
        for i, item in enumerate(value):
            errors += schema_errors(item, schema['items'], f'{path}[{i}]')
    if isinstance(value, str):
        # JS/Zod string lengths count UTF-16 code units.
        length = len(value.encode('utf-16-le', errors='surrogatepass')) // 2
        if length < schema.get('minLength', 0) or length > schema.get('maxLength', math.inf):
            errors.append(path + ': string length')
        if 'pattern' in schema and not re.search(schema['pattern'], value):
            errors.append(path + ': pattern')
    if type(value) in (int, float):
        if value < schema.get('minimum', -math.inf) or value > schema.get('maximum', math.inf):
            errors.append(path + ': bounds')
    return errors


def span_text(text, span):
    data = text.encode('utf-16-le')
    start, end = int(span['start']), int(span['end'])
    if not 0 <= start < end <= len(data) // 2:
        return None
    try:
        return data[start * 2:end * 2].decode('utf-16-le') or None
    except UnicodeError:
        return None


def canonical(value):
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return sorted((canonical(v) for v in value), key=lambda x: json.dumps(x, sort_keys=True))
    return value


def match(expected, actual, text):
    if expected == '$valid_input_spans':
        return isinstance(actual, list) and bool(actual) and all(span_text(text, s) is not None for s in actual)
    if expected == '$valid_claim_span':
        quote = span_text(text, actual) if isinstance(actual, dict) else None
        return quote is not None and '50%' in quote and 'сырьё' in quote
    if expected == '$nonempty_clarification':
        return isinstance(actual, str) and bool(actual.strip())
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(expected) == set(actual) and all(match(v, actual[k], text) for k, v in expected.items())
    return canonical(expected) == canonical(actual)


def emitted_references(obj, case):
    """Inspect identifiable raw refs even if an unrelated schema field is invalid."""
    if not isinstance(obj, dict):
        return [], []
    context = case['publicContext']
    unknown, invented = [], []

    def known(field, value, allowed):
        if isinstance(value, str) and value not in allowed:
            entry = {'field': field, 'value': value}
            if entry not in unknown:
                unknown.append(entry)
        return isinstance(value, str) and value in allowed

    def refs(field, values, allowed):
        if isinstance(values, list):
            for value in values:
                known(field, value, allowed)

    topics = {t['id'] for t in context['topics']}
    facts = {f['id'] for f in context['knownFacts']}
    for field in ['primaryTopicId', 'secondaryTopicId']:
        known(field, obj.get(field), topics)
    refs('factIds', obj.get('factIds'), facts)
    known('acknowledgementFactId', obj.get('acknowledgementFactId'), context['acknowledgementFactIds'])
    active = context['activeOffer']
    known('targetOfferId', obj.get('targetOfferId'), [active['id']] if active else [])
    argument = obj.get('argument')
    if isinstance(argument, dict):
        known('argument.claimId', argument.get('claimId'), {a['claimId'] for a in context['availableArguments']})
        refs('argument.supportingFactIds', argument.get('supportingFactIds'), facts)
    draft = obj.get('offerDraft')
    if isinstance(draft, dict):
        issues = {i['id']: {v['id'] for v in i['values']} for i in context['issues']}
        expected = case['expected']['offerDraft']
        expected_terms = expected['terms'] if expected else []
        for field in ['terms', 'conditionalOn']:
            if not isinstance(draft.get(field), list):
                continue
            for term in draft[field]:
                if not isinstance(term, dict):
                    continue
                issue, value = term.get('issueId'), term.get('valueId')
                valid_issue = known('offerDraft.' + field + '.issueId', issue, issues)
                values = issues.get(issue, set()) if isinstance(issue, str) else set()
                valid_value = known('offerDraft.' + field + '.valueId', value, values)
                pair = {'issueId': issue, 'valueId': value}
                if field == 'terms' and valid_issue and valid_value and pair not in expected_terms and pair not in invented:
                    invented.append(pair)
    return unknown, invented


def public_semantics(obj, case):
    context, text = case['publicContext'], case['text']
    errors, unknown = [], []

    def known(path, value, allowed):
        if value is not None and value not in allowed:
            unknown.append({'field': path, 'value': value})
            errors.append(path + ': unknown ID/value')

    topics = {x['id'] for x in context['topics']}
    facts = {x['id'] for x in context['knownFacts']}
    for key in ['primaryTopicId', 'secondaryTopicId']:
        known(key, obj[key], topics)
    if obj['secondaryTopicId'] is not None and obj['secondaryTopicId'] == obj['primaryTopicId']:
        errors.append('secondaryTopicId: duplicate primary topic')
    for fact in obj['factIds']:
        known('factIds', fact, facts)
    if len(set(obj['factIds'])) != len(obj['factIds']):
        errors.append('factIds: duplicates')
    known('acknowledgementFactId', obj['acknowledgementFactId'], context['acknowledgementFactIds'])
    active = context['activeOffer']
    known('targetOfferId', obj['targetOfferId'], [active['id']] if active else [])
    if obj['intent'] in ['counter_offer', 'close_attempt'] and obj['targetOfferId'] is None:
        errors.append('targetOfferId: current offer required')
    if obj['intent'] not in ['counter_offer', 'close_attempt'] and obj['targetOfferId'] is not None:
        errors.append('targetOfferId: unexpected binding')
    for i, span in enumerate(obj['evidenceSpans']):
        if span_text(text, span) is None:
            errors.append(f'evidenceSpans[{i}]: invalid UTF-16 bounds')
    arg = obj['argument']
    if arg:
        catalog = {a['claimId']: a for a in context['availableArguments']}
        known('argument.claimId', arg['claimId'], catalog)
        for fact in arg['supportingFactIds']:
            known('argument.supportingFactIds', fact, facts)
        if arg['claimId'] in catalog and set(arg['supportingFactIds']) != set(catalog[arg['claimId']]['supportingFactIds']):
            errors.append('argument.supportingFactIds: claim mismatch')
        if span_text(text, arg['evidenceSpan']) is None:
            errors.append('argument.evidenceSpan: invalid UTF-16 bounds')
    if obj['intent'] == 'argument' and arg is None:
        errors.append('argument: missing binding')
    if obj['needsClarification'] != (isinstance(obj['clarification'], str) and bool(obj['clarification'].strip())):
        errors.append('clarification: inconsistent clarification flag')
    draft = obj['offerDraft']
    if draft:
        issues = {x['id']: {v['id'] for v in x['values']} for x in context['issues']}
        terms = draft['terms']
        ids = [t['issueId'] for t in terms]
        if len(set(ids)) != len(ids):
            errors.append('offerDraft.terms: duplicate issue')
        for field in ['terms', 'conditionalOn']:
            for t in draft[field] or []:
                known('offerDraft.' + field + '.issueId', t['issueId'], issues)
                known('offerDraft.' + field + '.valueId', t['valueId'], issues.get(t['issueId'], set()))
        if set(ids) != set(issues) and not obj['needsClarification']:
            errors.append('offerDraft: incomplete package without clarification')
        for t in draft['conditionalOn'] or []:
            if t not in terms:
                errors.append('offerDraft.conditionalOn: condition missing from terms')
    if obj['intent'] in ['offer', 'counter_offer', 'concession'] and draft is None and not obj['needsClarification']:
        errors.append('offerDraft: binding intent without terms or clarification')
    return errors, unknown


def score(raw, case, schema):
    result = {'json_valid': False, 'schema_valid': False, 'semantic_valid': False,
              'expected_primary_intent': case['expected']['intent'], 'actual_primary_intent': None,
              'primary_intent_correct': False, 'critical_term_correct': False,
              'clarification_expected': case['expected']['needsClarification'], 'clarification_actual': None,
              'clarification_correct': False, 'clarification_flag_correct': False,
              'id_scan_performed': False, 'unknown_ids': [], 'invented_terms': [],
              'full_expected_structure_match': False, 'field_failures': {}, 'schema_errors': [], 'semantic_errors': []}
    try:
        obj = strict_json(raw)
        result['json_valid'] = True
    except (ValueError, TypeError) as error:
        result['field_failures']['$json'] = str(error)
        return result
    if isinstance(obj, dict):
        result['actual_primary_intent'] = obj.get('intent')
        result['primary_intent_correct'] = obj.get('intent') == case['expected']['intent']
        result['clarification_actual'] = obj.get('needsClarification')
        result['clarification_flag_correct'] = (type(obj.get('needsClarification')) is bool
            and obj['needsClarification'] == case['expected']['needsClarification'])
        result['unknown_ids'], result['invented_terms'] = emitted_references(obj, case)
        result['id_scan_performed'] = True
    result['schema_errors'] = schema_errors(obj, schema)
    result['schema_valid'] = not result['schema_errors']
    if result['schema_errors']:
        result['field_failures']['$schema'] = result['schema_errors']
        return result
    errors, unknown = public_semantics(obj, case)
    result['unknown_ids'] = list({(item['field'], item['value']): item for item in result['unknown_ids'] + unknown}.values())
    expected = case['expected']
    for key, wanted in expected.items():
        actual = obj[key]
        options = case.get('allowedAlternatives', {}).get(key, [wanted])
        if not any(match(option, actual, case['text']) for option in options):
            result['field_failures'][key] = {'expected': options if len(options) > 1 else wanted, 'actual': actual}
    # A legal domain value can still be an invented commitment; expose both categories.
    if result['invented_terms']:
        errors.append('offerDraft.terms: terms absent from utterance/explicit inheritance')
    if case['critical']:
        for key in case['criticalFields']:
            if key in result['field_failures']:
                errors.append(key + ': frozen commitment/negation safety mismatch')
    if case['id'] == 'A03' and 'argument' in result['field_failures']:
        errors.append('argument: cashflow claim/predicate evidence mismatch')
    if case['id'] == 'A05' and obj['needsClarification']:
        if not re.search(r'цен|95|100|сумм', obj['clarification'] or '', re.IGNORECASE):
            result['field_failures']['clarification'] = 'Must ask about unresolved price/alternatives'
            errors.append('clarification: unresolved price not addressed')
    result['semantic_errors'] = errors
    result['semantic_valid'] = not errors
    result['clarification_correct'] = (result['clarification_flag_correct']
        and 'clarification' not in result['field_failures']
        and (not case['ambiguity'] or result['semantic_valid']))
    result['critical_term_correct'] = (not errors and all(k not in result['field_failures'] for k in case['criticalFields']))
    result['full_expected_structure_match'] = not result['field_failures'] and not errors
    if errors:
        result['field_failures']['$semantic'] = errors
    return result


def rate(rows, key):
    correct = sum(bool(r[key]) for r in rows)
    return {'correct': correct, 'total': len(rows), 'rate': correct / len(rows) if rows else None}


def metrics(rows, cases):
    by_id = {c['id']: c for c in cases}
    critical = [r for r in rows if by_id[r['case_id']]['critical']]
    ambiguous = [r for r in rows if by_id[r['case_id']]['ambiguity']]
    clear = [r for r in rows if not by_id[r['case_id']]['expected']['needsClarification']]
    output = {name: rate(rows, key) for name, key in [
        ('PRIMARY_INTENT_ACCURACY', 'primary_intent_correct'), ('JSON_VALID_RATE', 'json_valid'),
        ('SCHEMA_VALID_RATE', 'schema_valid'), ('SEMANTIC_VALID_RATE', 'semantic_valid'),
        ('FULL_EXPECTED_STRUCTURE_MATCH', 'full_expected_structure_match')]}
    output['CRITICAL_COMMITMENT_ACCURACY'] = rate(critical, 'critical_term_correct')
    output['AMBIGUITY_CLARIFICATION_ACCURACY'] = rate(ambiguous, 'clarification_correct')
    output['UNKNOWN_ID_RATE'] = {'count': sum(bool(r['unknown_ids']) for r in rows), 'total': len(rows),
                                 'assessed_json_objects': sum(r.get('id_scan_performed', False) for r in rows),
                                 'rate': sum(bool(r['unknown_ids']) for r in rows) / len(rows) if rows else None}
    output['UNNECESSARY_CLARIFICATION_RATE'] = {'count': sum(r['clarification_actual'] is True for r in clear),
        'total': len(clear), 'rate': sum(r['clarification_actual'] is True for r in clear) / len(clear) if clear else None}
    latencies = sorted(r['latency_seconds'] for r in rows)
    output['latency_seconds'] = {'mean': statistics.mean(latencies), 'median': statistics.median(latencies),
                                 'p95_nearest_rank': latencies[math.ceil(0.95 * len(latencies)) - 1]} if rows else None
    output['tokens_per_second_including_prefill'] = sum(r['output_token_count'] for r in rows) / sum(latencies) if rows else None
    return output
