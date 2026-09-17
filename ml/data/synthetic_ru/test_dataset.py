"""Behavioral regression and mutation tests; no inference or training."""
import copy
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from core import HERE, ROOT, KEYS, SEED, digest, dumps, interpretation, unmark, u16, write
from generate import generate, row as make_row
from validate import validate_all, validate_row, validate_context, privacy_errors, span_text
from compile_sft import compile_row, canonical_completion, safe_output
from audit import normalize, HOLDOUT_SHA256, similarity, features, suspicious


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry,cls.rows,cls.rejected=generate()

    def one(self,op=None,intent=None,**fields):
        return copy.deepcopy(next(r for r in self.rows if (op is None or r['semanticCase']['op']==op)
                                  and (intent is None or r['intent']==intent) and all(r.get(k)==v for k,v in fields.items())))

    def bad(self,row):
        errors,_=validate_row(row,self.registry)
        self.assertTrue(errors)
        return errors

    def test_seed_determinism_and_global_rng_independence(self):
        from templates import families
        from generate import eligible
        f=next(f for f in families() if f['op']=='inherit')
        cid,e=next((c,e) for c,e in self.registry.items() if eligible(f,e))
        first=make_row(f,cid,e,17)
        random.seed(9999)
        second=make_row(f,cid,e,17)
        self.assertEqual(dumps(first),dumps(second))
        self.assertNotEqual(first['semanticCase'],make_row(f,cid,e,17,seed=SEED+1)['semanticCase'])

    def test_all_records_validate_with_group_isolation(self):
        report=validate_all(self.rows,self.registry,True)
        self.assertFalse(report['errors'])
        self.assertFalse(report['unknownIds'])

    def test_schema_rejects_extra_field_missing_key_and_wrong_type(self):
        for mutate in [lambda e:e.update(score=100),lambda e:e.pop('secondaryTopicId'),lambda e:e.update(schemaVersion=True)]:
            r=self.one();mutate(r['expected']);self.bad(r)

    def test_absent_price_topic_never_invented(self):
        r=copy.deepcopy(next(r for r in self.rows if r['contextId']=='procurement.descriptive.no_price_topic'
                             and r['semanticCase']['focus']==0 and r['intent']=='ask_question'))
        self.assertIsNone(r['expected']['primaryTopicId'])
        r['expected']['primaryTopicId']='price'
        self.assertTrue(validate_row(r,self.registry)[1])

    def test_known_but_unmentioned_fact_rejected(self):
        r=self.one(intent='ask_question')
        r['expected']['factIds']=[self.registry[r['contextId']]['publicContext']['knownFacts'][0]['id']]
        self.bad(r)

    def test_acknowledgement_is_distinct_from_empathy_and_acceptance(self):
        feeling=self.one(op='empathy')
        ack=self.one(op='ack')
        accepted=self.one(op='accept')
        self.assertIsNone(feeling['expected']['acknowledgementFactId'])
        self.assertIsNotNone(ack['expected']['acknowledgementFactId'])
        self.assertIsNone(ack['expected']['targetOfferId'])
        self.assertIsNotNone(accepted['expected']['targetOfferId'])

    def test_argument_fact_and_condition_binding(self):
        r=self.one(op='argument')
        facts=self.registry[r['contextId']]['publicContext']['knownFacts']
        other=next(f['id'] for f in facts if f['id'] not in r['expected']['argument']['supportingFactIds'])
        r['expected']['argument']['supportingFactIds']=[other]
        self.bad(r)
        r=self.one(op='argument');r['semanticCase']['values'][r['semanticCase']['fact']]=2
        self.bad(r)

    def test_active_offer_id_must_be_exact(self):
        r=self.one(intent='counter_offer');r['expected']['targetOfferId']='invented-offer'
        self.assertTrue(validate_row(r,self.registry)[1])
        r=self.one(intent='close_attempt');r['expected']['targetOfferId']=None
        self.bad(r)

    def test_missing_or_unclear_offer_ref_clarifies_without_binding(self):
        for op in ('missing_target','unclear_target'):
            r=self.one(op=op)
            self.assertTrue(r['expected']['needsClarification'])
            self.assertIsNone(r['expected']['targetOfferId'])
            self.assertIsNone(r['expected']['offerDraft'])

    def test_unresolved_commitment_uses_null_draft(self):
        for intent in ('offer','counter_offer','concession'):
            r=self.one(op='unresolved_commitment',intent=intent)
            self.assertTrue(r['expected']['needsClarification'])
            self.assertIsNone(r['expected']['offerDraft'])

    def test_missing_offer_preserves_only_explicit_term(self):
        r=self.one(op='missing_target_terms')
        self.assertIsNone(r['expected']['targetOfferId'])
        self.assertEqual(len(r['expected']['offerDraft']['terms']),1)
        self.assertTrue(r['expected']['needsClarification'])

    def test_inheritance_copies_only_explicitly_retained_terms(self):
        for op in ('inherit','inherit_one'):
            r=self.one(op=op)
            c=self.registry[r['contextId']]['publicContext']
            active={t['issueId']:t['valueId'] for t in c['activeOffer']['terms']}
            draft={t['issueId']:t['valueId'] for t in r['expected']['offerDraft']['terms']}
            for index in r['semanticCase']['inherit']:
                iid=c['issues'][index]['id']
                self.assertEqual(draft[iid],active[iid])
            index=r['semanticCase']['inherit'][0]
            r['expected']['offerDraft']['terms'][index]['valueId']=next(v['id'] for v in c['issues'][index]['values'] if v['id']!=active[c['issues'][index]['id']])
            self.bad(r)

    def test_partial_counter_does_not_silently_inherit(self):
        r=self.one(op='partial',intent='counter_offer')
        self.assertTrue(r['expected']['needsClarification'])
        self.assertLess(len(r['expected']['offerDraft']['terms']),len(self.registry[r['contextId']]['publicContext']['issues']))

    def test_ambiguous_options_never_chosen(self):
        for op in ('alternatives','range','approximate','unknown_value','contradiction'):
            r=self.one(op=op);c=self.registry[r['contextId']]['publicContext']
            excluded=c['issues'][r['semanticCase']['focus']]['id']
            self.assertNotIn(excluded,[t['issueId'] for t in r['expected']['offerDraft']['terms']])
            r['expected']['needsClarification']=False;r['expected']['clarification']=None
            self.bad(r)

    def test_question_with_numbers_has_no_offer(self):
        r=self.one(op='numeric_question')
        self.assertIsNone(r['expected']['offerDraft'])

    def test_negated_value_does_not_become_term(self):
        r=self.one(op='negated_value');case=r['semanticCase'];c=self.registry[r['contextId']]['publicContext']
        i=case['focus'];negated=c['issues'][i]['values'][(case['values'][i]+1)%3]['id']
        actual=next(t for t in r['expected']['offerDraft']['terms'] if t['issueId']==c['issues'][i]['id'])
        self.assertNotEqual(actual['valueId'],negated)
        actual['valueId']=negated;self.bad(r)

    def test_conditional_terms_preserved(self):
        r=self.one(op='conditional');condition=r['expected']['offerDraft']['conditionalOn'][0]
        self.assertIn(condition,r['expected']['offerDraft']['terms'])
        r['expected']['offerDraft']['conditionalOn']=None;self.bad(r)

    def test_counterpart_question_is_not_model_clarification(self):
        r=self.one(op='meaning')
        self.assertEqual(r['intent'],'clarification')
        self.assertFalse(r['expected']['needsClarification'])
        self.assertTrue(self.one(op='partial')['expected']['needsClarification'])

    def test_injection_cannot_mutate_state_or_emit_bindings(self):
        r=self.one(op='injection')
        self.assertEqual(r['expected']['intent'],'clarification')
        self.assertTrue(r['expected']['needsClarification'])
        r['expected']['targetOfferId']='auto-accept';self.bad(r)

    def test_utf16_cyrillic_digits_dashes_punctuation_and_emoji(self):
        marked='🙂 [[Не 68, а 74]] — [[доставка в среду – без аванса]]!'
        text,spans=unmark(marked)
        self.assertEqual(spans[0]['start'],3)
        self.assertEqual(span_text(text,spans[0]),'Не 68, а 74')
        self.assertEqual(span_text(text,spans[1]),'доставка в среду – без аванса')
        self.assertIsNone(span_text(text,{'start':0,'end':1}))
        self.assertEqual(u16(text),len(text)+1)

    def test_text_or_evidence_edits_rejected(self):
        r=self.one(intent='offer');r['text']='Не '+r['text'];self.bad(r)
        r=self.one(intent='argument');r['expected']['argument']['evidenceSpan']['start']+=1;self.bad(r)

    def test_split_family_and_context_leakage_rejected(self):
        a=self.one();b=copy.deepcopy(a);b['id']='other';b['split']='internal_test'
        result=validate_all([a,b],self.registry)
        self.assertTrue(result['groupLeakage'])
        self.assertTrue(result['errors'])

    def test_duplicate_detector_checks_id_and_text_context(self):
        r=self.one();report=validate_all([r,copy.deepcopy(r)],self.registry)
        self.assertEqual(report['duplicates']['id'],1)
        self.assertEqual(report['duplicates']['text_context'],1)

    def test_duplicate_recipe_ids_fail_before_generation(self):
        from templates import families
        f=families()[0]
        with patch('generate.families',return_value=[f,f]),self.assertRaisesRegex(ValueError,'recipe ID'):
            generate()

    def test_compiler_preserves_context_and_canonical_complete_json(self):
        r=self.one(op='inherit');export=compile_row(r,self.registry)
        self.assertEqual([m['role'] for m in export['prompt']],['system','user'])
        self.assertEqual(export['completion'][0]['role'],'assistant')
        user=json.loads(export['prompt'][1]['content'])
        self.assertEqual(user['utterance'],r['text'])
        self.assertEqual(user['context']['active'][0],r['expected']['targetOfferId'])
        content=export['completion'][0]['content']
        self.assertEqual(tuple(json.loads(content)),KEYS)
        self.assertEqual(json.loads(content),r['expected'])
        shuffled=dict(reversed(list(r['expected'].items())))
        self.assertEqual(canonical_completion(shuffled),content)
        self.assertNotIn('```',content)
        self.assertNotIn('semanticCase',user)

    def test_no_hidden_state_or_identifiers(self):
        c=copy.deepcopy(next(iter(self.registry.values())))
        c['publicContext']['reservation']=100
        self.assertTrue(validate_context(c))
        for text in ['contact@example.org','+7 (999) 123-45-67','worker_id ABC']:
            self.assertTrue(privacy_errors(text))

    def test_raw_and_model_output_paths_refused(self):
        for path in [ROOT/'AlagDatasets/raw/data.json',ROOT/'AlagModels/Qwen3-4B/config.json',HERE/'train.jsonl']:
            with self.assertRaises(ValueError):safe_output(path)
        with self.assertRaises(ValueError):write(ROOT/'AlagDatasets/raw/no-write.json',{})

    def test_holdout_text_exclusion_and_audit_sensitivity(self):
        path=ROOT/'evals/local-qwen/a01-a16.json'
        self.assertEqual(digest(path.read_bytes()),HOLDOUT_SHA256)
        # Labels are not consulted; no holdout text is printed or used for generation.
        held={normalize(c['text']) for c in json.loads(path.read_text(encoding='utf-8'))['cases']}
        self.assertFalse(held & {normalize(r['text']) for r in self.rows})
        own='Предлагаю отдельный вариант для склада'
        self.assertTrue(suspicious(similarity(features(own),features(own.upper()+'!'))))


if __name__=='__main__':
    unittest.main()
