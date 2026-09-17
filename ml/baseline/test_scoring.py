"""Targeted safety checks for the eval harness, not training examples."""
import copy
import json
from pathlib import Path
import unittest
from scoring import score, schema_errors, strict_json

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / 'evals/local-qwen/a01-a16.json').read_text(encoding='utf-8'))['cases']
SCHEMA = json.loads((ROOT / 'evals/local-qwen/interpretation.schema.json').read_text(encoding='utf-8'))


def valid(case):
    obj = copy.deepcopy(case['expected'])
    span = {'start': 0, 'end': len(case['text'].encode('utf-16-le')) // 2}
    obj['evidenceSpans'] = [span]
    if obj['argument']:
        obj['argument']['evidenceSpan'] = span.copy()
    if obj['needsClarification']:
        obj['clarification'] = case['source']['expected'][:240]
    return obj


class ScoringSafety(unittest.TestCase):
    def scored(self, number, transform=lambda obj: None):
        case = CASES[number - 1]
        obj = valid(case)
        transform(obj)
        return score(json.dumps(obj, ensure_ascii=False), case, SCHEMA)

    def test_all_frozen_expected_structures_are_valid(self):
        for case in CASES:
            with self.subTest(case=case['id']):
                result = score(json.dumps(valid(case), ensure_ascii=False), case, SCHEMA)
                self.assertTrue(result['full_expected_structure_match'], result)

    def test_json_is_not_repaired(self):
        for raw in ['```json\n{}\n```', '{"x":1,"x":2}', '{"x":NaN}', '{} explanation', '{']:
            self.assertFalse(score(raw, CASES[0], SCHEMA)['json_valid'])

    def test_schema_rejects_extra_state_and_wrong_boolean(self):
        for change in [lambda x: x.update(score=100), lambda x: x.update(needsClarification='false')]:
            self.assertFalse(self.scored(1, change)['schema_valid'])

    def test_nullable_schema_reports_the_nested_failing_field(self):
        result = self.scored(4, lambda x: x['offerDraft'].update(conditionalOn=[]))
        self.assertFalse(result['schema_valid'])
        self.assertTrue(any('offerDraft.conditionalOn' in error for error in result['schema_errors']))

    def test_unknown_id_and_stale_offer_are_not_accepted(self):
        for number, change in [(1, lambda x: x.update(primaryTopicId='made-up')),
                               (14, lambda x: x.update(targetOfferId='old-offer'))]:
            result = self.scored(number, change)
            self.assertTrue(result['schema_valid'])
            self.assertFalse(result['semantic_valid'])
            self.assertTrue(result['unknown_ids'])

    def test_negated_legal_price_is_still_unsafe(self):
        def change(x):
            x['offerDraft']['terms'].append({'issueId': 'PRICE', 'valueId': '105'})
        result = self.scored(5, change)
        self.assertFalse(result['critical_term_correct'])
        self.assertTrue(result['invented_terms'])

    def test_unknown_ids_are_visible_despite_schema_failure(self):
        result = self.scored(1, lambda x: x.update(primaryTopicId='made-up', evidenceSpans=[]))
        self.assertFalse(result['schema_valid'])
        self.assertEqual(result['unknown_ids'], [{'field': 'primaryTopicId', 'value': 'made-up'}])

    def test_invented_legal_terms_are_visible_despite_schema_failure(self):
        def change(x):
            x['evidenceSpans'] = []
            x['offerDraft']['terms'][0]['valueId'] = '110'
        result = self.scored(4, change)
        self.assertFalse(result['schema_valid'])
        self.assertEqual(result['invented_terms'], [{'issueId': 'PRICE', 'valueId': '110'}])
        self.assertEqual(result['unknown_ids'], [])

    def test_ambiguous_commitment_needs_safe_clarification(self):
        def change(x):
            x['offerDraft']['terms'].append({'issueId': 'PRICE', 'valueId': '105'})
        result = self.scored(5, change)
        self.assertTrue(result['clarification_flag_correct'])
        self.assertFalse(result['clarification_correct'])

    def test_conditional_concession_cannot_be_unconditional(self):
        result = self.scored(7, lambda x: x['offerDraft'].update(conditionalOn=None))
        self.assertFalse(result['critical_term_correct'])

    def test_incomplete_binding_requires_clarification(self):
        result = self.scored(4, lambda x: x['offerDraft']['terms'].pop())
        self.assertFalse(result['semantic_valid'])

    def test_invalid_utf16_and_argument_evidence_fail(self):
        self.assertFalse(self.scored(1, lambda x: x.update(evidenceSpans=[{'start': 0, 'end': 1999}]))['semantic_valid'])
        self.assertFalse(self.scored(3, lambda x: x['argument'].update(evidenceSpan={'start': 0, 'end': 1}))['full_expected_structure_match'])


if __name__ == '__main__':
    unittest.main()
