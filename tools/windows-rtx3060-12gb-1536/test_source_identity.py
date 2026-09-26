"""CPU/stdlib fixtures only: privacy, real Git history, immutable re-packaging."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from common import HERE, read_json, write_json, sha256
import package_result as package
import source_identity as source
import verify_result as verifier
from test_support import temporary, powershell, quote, copy_tool
import test_workflow_result as archive_fixtures


class PrivacyTests(unittest.TestCase):
    def test_canonical_origin_preserved_exactly(self):
        self.assertEqual(package.scrub_text(source.ORIGIN), source.ORIGIN)

    def test_original_defect_reproduced_by_frozen_legacy_projection(self):
        self.assertEqual(package.legacy_scrub_text(source.ORIGIN), 'http<local-path>')

    def test_https_is_not_a_drive_or_unc_path(self):
        value = 'See https://example.org/public/file and https://github.com/org/repo.git'
        self.assertEqual(package.scrub_text(value), value)

    def test_windows_user_paths_stay_private(self):
        for value in (r'C:\Users\Name\private file', 'C:/Users/Name/file', r'S:\Name\file'):
            self.assertEqual(package.scrub_text(value), '<local-path>')

    def test_unc_paths_stay_private(self):
        for value in (r'\\server\share\private file', '//server/share/private', r'\\?\C:\Users\Name\file'):
            self.assertEqual(package.scrub_text(value), '<local-path>')

    def test_posix_and_home_paths_stay_private(self):
        for value in ('/home/Name/private', '/Users/Name/file', '~/private', r'~\private'):
            self.assertEqual(package.scrub_text(value), '<local-path>')

    def test_authenticated_urls_are_redacted_including_username_only(self):
        for value in ('https://user:password@example.com/repo', 'https://secret@example.com/repo',
                      'https://user%3Asecret@example.com/repo', 'ssh://secret@example.com/repo'):
            self.assertEqual(package.scrub_text(value), '<redacted-url>')

    def test_query_fragment_and_file_urls_are_redacted(self):
        for value in ('https://example.com/file?token=secret', 'https://example.com/#secret',
                      'file:///C:/Users/Name/file', 'https://example.com:bad/path'):
            self.assertEqual(package.scrub_text(value), '<redacted-url>')

    def test_bearer_and_token_secrets_stay_private(self):
        for value in ('Bearer privateTOKEN', 'hf_PRIVATE', 'ghp_PRIVATE', 'github_pat_PRIVATE',
                      'token=privateTOKEN', 'password:privateTOKEN', 'api_key=privateTOKEN'):
            self.assertNotIn('PRIVATE', package.scrub_text(value))
            self.assertNotIn('privateTOKEN', package.scrub_text(value))

    def test_structured_secrets_and_private_content(self):
        result = package.sanitize({'access_token': 'secret', 'api_key': 'secret', 'credentials': {'user': 'secret'}})
        self.assertNotIn('secret', json.dumps(result))
        with self.assertRaises(ValueError): package.sanitize({'input_ids': [1]})

    def test_mixed_urls_paths_and_secrets_are_idempotent(self):
        values = [source.ORIGIN, 'Bearer secret', 'token=secret', r'C:\Users\Name\file',
                  '//server/share/file', 'https://u:p@example.com/a?token=secret',
                  'https://example.com/a ' + r'C:\Users\Name\private', '<repository>\\model']
        clean = package.sanitize(values)
        self.assertEqual(package.sanitize(clean), clean)


class SourceIdentityTests(unittest.TestCase):
    def setUp(self):
        tmp = temporary(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.git = source.Git(self.root)
        self.command('init', '-b', 'main')
        self.command('config', 'user.name', 'Source Fixture')
        self.command('config', 'user.email', 'fixture@example.invalid')
        self.command('config', 'core.autocrlf', 'false')
        self.command('config', 'core.hooksPath', str(self.root / 'no-hooks'))
        self.command('remote', 'add', 'origin', source.ORIGIN)
        for name in ('config.json', 'model-lock.json', 'runtime-lock.json'):
            p = self.root / source.TOOL / name; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes((HERE / name).read_bytes())
        write_json(self.root / source.DECISION, {'fixture': 'only byte hashing'})
        decision = self.root / source.DECISION
        decision.write_bytes(decision.read_bytes().replace(b'\r\n', b'\n'))
        (self.root / ' leading source.txt').write_bytes(b'fixture training source\n')
        (self.root / 'binary.bin').write_bytes(b'fixture\x00\n')
        (self.root / '.gitattributes').write_bytes(b'* text=auto eol=lf\n')
        (self.root / '.gitignore').write_bytes(b'.scratch/\n.results/\n')
        self.commit('fixture training')
        self.training_commit = self.git.text('rev-parse', 'HEAD')
        self.scratch = self.root / '.scratch'; self.scratch.mkdir()
        self.output = self.root / '.results'; self.output.mkdir()
        self.e = archive_fixtures.ArchiveVerifierTests().synthetic_evidence()
        identity = {'commit': self.training_commit, 'origin': source.ORIGIN, 'clean': True}
        snapshot = {n: source.pin(b) for n, b in self.git.blobs(self.git.tree(self.training_commit)).items()}
        model = read_json(HERE / 'model-lock.json')
        snapshot.update({'AlagModels/Qwen3-4B/' + n: p for n, p in model['files'].items()})
        self.e['outcome'].update(repository_commit=self.training_commit,
            integrity={'passed': True, 'before': snapshot, 'after': copy.deepcopy(snapshot),
                       'git': copy.deepcopy(identity), 'model': {'files': model['files']}})
        self.e['prepared'] = {'passed': True, 'git': identity,
                             'configuration_sha256': sha256(HERE / 'config.json'), 'files': {}}
        self.e['controls'] = {'configuration': read_json(HERE / 'config.json'),
                              'decision_sha256': sha256(self.root / source.DECISION)}
        names = {'data-1536.json': {'selection': self.e['selection']},
                 'frozen-controls.json': self.e['controls'], 'module-control.json': {}, 'train-contexts.json': {},
                 'tests.json': self.e['tests'], 'prepare-1536-audit.json': self.e['prepare_audit'],
                 'integrity-before.json': {'git': identity, 'files': snapshot}}
        for name, value in names.items():
            write_json(self.scratch / name, value)
            self.e['prepared']['files'][name] = sha256(self.scratch / name)
        write_json(self.scratch / 'campaign-started.json', {'supervisor_pid': 555555})
        write_json(self.scratch / 'outcome.json', self.e['outcome'])
        old = package.sanitize(self.e, self.root, scrubber=package.legacy_scrub_text)
        self.original = self.output / package.ARCHIVE
        archive_fixtures.ArchiveVerifierTests().write_archive(self.original, old)
        constants = patch.multiple(source, TRAINING_COMMIT=self.training_commit,
                                   ORIGINAL_EVIDENCE_SHA256=source.digest(old),
                                   ORIGINAL_ZIP_SHA256=sha256(self.original))
        constants.start(); self.addCleanup(constants.stop)

    def command(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args],
                                       stderr=subprocess.PIPE, timeout=15)

    def commit(self, message):
        self.command('add', '--', '.')  # Only an isolated, generated fixture repository.
        self.command('commit', '-m', message)

    def correction(self, name='README.md', value='fixture tooling correction\n'):
        (self.root / source.TOOL / name).write_text(value, encoding='utf-8')
        self.commit('fixture correction')

    def corrected_evidence(self):
        result = copy.deepcopy(self.e)
        result.update(schema_version=3, source_provenance=source.collect_provenance(self.e, self.root))
        return result

    def assert_rejected(self, evidence=None):
        with self.assertRaises((ValueError, KeyError, TypeError, subprocess.SubprocessError)):
            source.source_identity(evidence or self.e, self.root)

    def test_expected_commit_origin_and_clean_source_pass(self):
        self.assertTrue(source.source_identity(self.e, self.root))

    def test_descendant_tooling_commit_keeps_historical_training_commit(self):
        self.correction()
        e = self.corrected_evidence()
        self.assertTrue(source.source_identity(e, self.root))
        p = e['source_provenance']
        self.assertEqual(p['training_source_commit'], self.training_commit)
        self.assertNotEqual(p['packaging_git']['commit'], self.training_commit)
        self.assertEqual(p['tooling_only_proof']['load_bearing_changes'], [])

    def test_old_schema_cannot_claim_later_head(self):
        self.correction(); self.assert_rejected()

    def test_wrong_training_commit_fails_even_when_all_claims_agree(self):
        for location in (self.e['outcome'], self.e['prepared']['git'], self.e['outcome']['integrity']['git']):
            location['repository_commit' if location is self.e['outcome'] else 'commit'] = 'b' * 40
        self.assert_rejected()

    def test_wrong_origin_fails(self):
        self.e['prepared']['git']['origin'] = 'https://github.com/different/repo.git'
        self.assert_rejected()

    def test_wrong_actual_origin_fails(self):
        self.command('remote', 'set-url', 'origin', 'https://github.com/different/repo.git')
        self.assert_rejected()

    def test_authenticated_origin_not_canonicalized_to_success(self):
        self.e['prepared']['git']['origin'] = 'https://secret@github.com/AiratBastanov/TalkNFace.git'
        self.assert_rejected()

    def test_historical_dirty_state_fails(self):
        for value in (False, 1, 'true', None):
            self.e['prepared']['git']['clean'] = value
            self.assert_rejected()

    def test_current_dirty_state_fails(self):
        (self.root / ' leading source.txt').write_text('dirty', encoding='utf-8')
        self.assert_rejected()

    def test_untracked_source_fails(self):
        (self.root / 'untracked.py').write_text('dirty', encoding='utf-8')
        self.assert_rejected()

    def test_assume_unchanged_cannot_hide_source_changes(self):
        self.command('update-index', '--assume-unchanged', '--', ' leading source.txt')
        (self.root / ' leading source.txt').write_text('dirty', encoding='utf-8')
        self.assert_rejected()

    def test_git_declared_crlf_conversion_keeps_clean_identity(self):
        (self.root / ' leading source.txt').write_bytes(b'fixture training source\r\n')
        self.command('add', '--', ' leading source.txt')  # Same Git blob; refresh the fixture's index stat.
        self.assertTrue(source.source_identity(self.e, self.root))
        self.assertEqual(source.verify_checkout(self.git, self.training_commit), [' leading source.txt'])

    def test_crlf_plus_hidden_content_change_fails(self):
        self.command('update-index', '--assume-unchanged', '--', ' leading source.txt')
        (self.root / ' leading source.txt').write_bytes(b'fixture changed content\r\n')
        self.assert_rejected()

    def test_binary_content_never_receives_eol_normalization(self):
        self.command('update-index', '--assume-unchanged', '--', 'binary.bin')
        (self.root / 'binary.bin').write_bytes(b'fixture\x00\r\n')
        self.assert_rejected()

    def test_historical_snapshot_never_receives_eol_normalization(self):
        p = source.pin(b'fixture training source\r\n')
        self.e['outcome']['integrity']['before'][' leading source.txt'] = p
        self.e['outcome']['integrity']['after'][' leading source.txt'] = p
        self.assert_rejected()

    def test_malformed_missing_and_redacted_source_identity_fail(self):
        for value in (None, {}, 'bad', {'commit': 'bad', 'clean': True, 'origin': source.ORIGIN},
                      {'commit': self.training_commit, 'origin': 'http<local-path>', 'clean': True}):
            self.e['prepared']['git'] = value
            self.assert_rejected()

    def test_contradictory_integrity_git_fails(self):
        self.e['outcome']['integrity']['git']['commit'] = 'c' * 40
        self.assert_rejected()

    def test_historical_snapshot_coverage_and_bytes_remain_strict(self):
        for mutation in ('missing', 'extra', 'hash'):
            e = copy.deepcopy(self.e); pins = e['outcome']['integrity']['before']
            if mutation == 'missing': pins.pop(' leading source.txt')
            elif mutation == 'extra': pins['extra'] = source.pin(b'x')
            else: pins[' leading source.txt'] = source.pin(b'bad')
            e['outcome']['integrity']['after'] = copy.deepcopy(pins)
            self.assert_rejected(e)

    def test_changed_load_bearing_file_fails(self):
        (self.root / ' leading source.txt').write_bytes(b'changed\n')
        self.commit('fixture forbidden edit'); self.assert_rejected()

    def test_even_reverted_training_change_in_history_fails(self):
        p = self.root / ' leading source.txt'; original = p.read_bytes()
        p.write_bytes(b'changed\n'); self.commit('fixture forbidden edit')
        p.write_bytes(original); self.commit('fixture put bytes back')
        self.assert_rejected()

    def test_non_descendant_fails(self):
        self.correction()
        with self.assertRaises(subprocess.CalledProcessError):
            source.tooling_proof(self.git, self.git.text('rev-parse', 'HEAD'), self.training_commit)

    def test_provenance_is_recomputed_not_trusted(self):
        self.correction(); e = self.corrected_evidence()
        e['source_provenance']['tooling_only_proof']['protected_tree_sha256'] = '0' * 64
        self.assert_rejected(e)

    def test_campaign_numeric_evidence_cannot_be_changed(self):
        self.e['outcome']['training']['steps'][0]['loss'] += 0.1
        self.assert_rejected()

    def test_prepared_raw_artifact_cannot_be_changed(self):
        (self.scratch / 'data-1536.json').write_text('{}', encoding='utf-8')
        with self.assertRaises(ValueError): source.certify_packaging(self.e, self.scratch, self.output, self.root)

    def test_original_zip_cannot_be_substituted(self):
        self.original.write_bytes(b'not the original')
        with self.assertRaises(ValueError): source.certify_packaging(self.e, self.scratch, self.output, self.root)

    def test_actual_repack_preserves_original_raw_campaign_and_reuses_safely(self):
        self.correction()
        original_hash = sha256(self.original)
        before = {p.name: sha256(p) for p in self.scratch.iterdir() if p.is_file()}
        with patch.object(package, 'evidence_for', return_value=self.e), patch.object(package, 'process_active', return_value=False):
            archive = package.package(self.scratch, self.output, self.root)
            e, _ = verifier.inspect_zip(archive)
            self.assertTrue(source.source_identity(e, self.root))
            # A fixture may never be presented as real hardware evidence.
            result = verifier.verify_evidence(e, source_check=lambda value: source.source_identity(value, self.root))
            self.assertEqual(result['failed_checks'], ['fixture_is_not_hardware_evidence'])
            corrected_hash = sha256(archive)
            self.assertEqual(package.package(self.scratch, self.output, self.root), archive)
            self.assertEqual(sha256(archive), corrected_hash)
        self.assertEqual(sha256(self.scratch / 'packaged-history' / (original_hash + '.zip')), original_hash)
        self.assertEqual(before, {p.name: sha256(p) for p in self.scratch.iterdir() if p.is_file()})
        self.assertEqual(e['prepared']['git']['origin'], source.ORIGIN)
        self.assertEqual(e['outcome'], self.e['outcome'])


class PackageOnlyTests(unittest.TestCase):
    def test_packaging_imports_cannot_load_ml_libraries(self):
        code = '''import sys
sys.path.insert(0, sys.argv[1])
def guard(event, args):
    if event == 'import' and args[0].split('.')[0] in {'torch','transformers','peft','bitsandbytes','train_smoke','runner'}:
        raise RuntimeError('ML/training import forbidden')
sys.addaudithook(guard)
import package_result, verify_result, source_identity
'''
        with temporary() as tmp:
            probe = Path(tmp) / 'no_ml_probe.py'; probe.write_text(code, encoding='utf-8')
            r = subprocess.run([sys.executable, '-B', str(probe), str(HERE)], capture_output=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_package_cli_always_verifies_and_returns_the_verdict_exit_code(self):
        for certified in (False, True):
            with patch.object(package, 'OperationLock'), patch.object(package, 'package', return_value='fixture.zip'), \
                    patch.object(verifier, 'verify', return_value={'certified_training_pass': certified}) as check:
                self.assertEqual(package.main(), 0 if certified else 2)
                check.assert_called_once_with('fixture.zip')

    def test_packageonly_runs_only_phase05_and_propagates_verification_failure(self):
        for exit_code in (0, 2):
            with temporary() as tmp:
                root = Path(tmp); tool = copy_tool(root); calls = root / 'calls.json'
                helper = '\nfunction Resolve-FrozenPython { return ' + quote(sys.executable) + ' }\n'
                helper += 'function Test-Resources { throw "Hardware access forbidden" }\n'
                helper += 'function Invoke-Bounded { param($Executable,$Arguments,$Timeout,$Name)\n'
                helper += 'if ($Name -eq "phase-05") { & $Executable @Arguments; if ($LASTEXITCODE -ne 0) { throw "PackageOnly failed" }; return }\n'
                helper += 'if ($Name -ne "05-package") { throw "Unexpected phase" }\n'
                helper += 'ConvertTo-Json -InputObject @($Arguments) | Set-Content -LiteralPath ' + quote(calls) + ' -Encoding UTF8\n'
                helper += 'if (' + str(exit_code) + ' -ne 0) { throw "verifier exit 2 fixture" }\n}\n'
                p = tool / 'Remote.Common.ps1'; p.write_text(p.read_text(encoding='utf-8') + helper, encoding='utf-8-sig')
                r = powershell('& ' + quote(tool / 'RUN-RTX3060-12GB-REMOTE.ps1') + ' -PackageOnly')
                self.assertEqual(r.returncode == 0, exit_code == 0, r.stdout + r.stderr)
                args = json.loads(calls.read_text(encoding='utf-8-sig'))
                self.assertEqual(Path(args[-1]).name, 'package_result.py')
                self.assertFalse((root / '.tmp/rtx3060-12gb-targeted-1536-smoke/campaign-started.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
