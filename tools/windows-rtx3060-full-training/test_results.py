import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from engine import run_epoch
from full_common import ROOT, atomic, pin, read, sha
from results import collect, finalize, package, packaging_identity, write_archive
from test_support import TinyEngine, setup
from verify_result import validate_evidence, verify


class ResultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / '.tmp', prefix='full-results-')
        self.addCleanup(self.tmp.cleanup)
        self.layout, self.run, self.rows = setup(self.tmp.name, updates=2)
        run_epoch(TinyEngine(), self.layout, self.run, self.rows)
        finalize(self.layout)
        self.identity = {'kind': 'packaging_verifier', 'version': 1, 'commit': '2' * 40, 'clean': True,
                         'files': {n: {'bytes': 1, 'sha256': '2' * 64} for n in ('results.py', 'verify_result.py')}}

    def test_actual_runtime_collection_two_archives_and_verifier(self):
        result = package(self.layout, self.identity)
        for path in result.values():
            verdict = verify(Path(path))
            self.assertEqual(verdict['archive_integrity'], 'PASS')
            self.assertEqual(verdict['training_completion'], 'FIXTURE_ONLY')
            self.assertEqual(verdict['quality_evaluation'], 'NOT_RUN')
        import zipfile
        with zipfile.ZipFile(result['diagnostic']) as z:
            self.assertEqual(set(z.namelist()), {'evidence.json', 'archive-manifest.json'})
        with zipfile.ZipFile(result['adapter']) as z:
            self.assertNotIn('state.pt', z.namelist())
            self.assertNotIn('train-tokens.jsonl', z.namelist())

    def test_failure_then_repackage_later_commit_preserves_completed_facts_and_existing_archives(self):
        first = package(self.layout, self.identity)
        pins = {p: pin(p) for p in first.values()}
        original_facts = (self.layout.runtime / 'completed.json').read_bytes()
        original_run = (self.layout.runtime / 'run.json').read_bytes()
        calls = 0
        def failure(target, payload, verifier):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('C:/private/user secret=do-not-package')
            return write_archive(target, payload, verifier)
        with patch('results.write_archive', failure), self.assertRaises(OSError):
            package(self.layout, self.identity)
        self.assertEqual(read(self.layout.runtime / 'operations.json')['last_error_phase'], 'package')
        later = dict(self.identity, commit='3' * 40)
        second = package(self.layout, later)
        self.assertNotEqual(first['diagnostic'], second['diagnostic'])
        self.assertEqual((self.layout.runtime / 'completed.json').read_bytes(), original_facts)
        self.assertEqual((self.layout.runtime / 'run.json').read_bytes(), original_run)
        self.assertEqual({p: pin(p) for p in first.values()}, pins)
        evidence = collect(self.layout, later)
        self.assertEqual(evidence['run']['identity']['training_source']['commit'], '1' * 40)
        self.assertEqual(evidence['packaging']['commit'], '3' * 40)
        self.assertNotIn('do-not-package', str(evidence))
        finalize(self.layout)
        self.assertEqual((self.layout.runtime / 'completed.json').read_bytes(), original_facts)

    def test_corrupt_archive_and_mutated_completed_evidence_rejected(self):
        output = package(self.layout, self.identity)
        p = Path(output['diagnostic'])
        p.write_bytes(p.read_bytes()[:100])
        with self.assertRaises(Exception):
            verify(p)
        facts = read(self.layout.runtime / 'completed.json')
        facts['completed_updates'] = 2000
        atomic(self.layout.runtime / 'completed.json', facts)
        with self.assertRaises(ValueError):
            collect(self.layout, self.identity)

    def test_fixture_cannot_claim_real_training_or_quality_and_raw_fields_rejected(self):
        e = collect(self.layout, self.identity)
        for key, value in [('fixture_only', False), ('quality_evaluation', 'PASS'), ('raw_examples', ['private'])]:
            changed = dict(e, **{key: value})
            with self.assertRaises(ValueError):
                validate_evidence(changed)
        changed = copy.deepcopy(e)
        changed['run']['identity']['model']['revision'] = '0' * 40
        with self.assertRaises(ValueError):
            validate_evidence(changed)

    def test_interrupted_final_fact_seal_can_recover_offline(self):
        original = (self.layout.runtime / 'completed.json').read_bytes()
        (self.layout.runtime / 'completed-seal.json').unlink()
        finalize(self.layout)
        self.assertEqual((self.layout.runtime / 'completed.json').read_bytes(), original)
        self.assertEqual(read(self.layout.runtime / 'completed-seal.json'), pin(self.layout.runtime / 'completed.json'))


if __name__ == '__main__':
    unittest.main()
