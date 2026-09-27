"""CPU/stdlib regressions and read-only checks of optional immutable result ZIPs."""
import ast
import copy
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
import zipfile

from common import HERE, ROOT, read_json, write_json, sha256
import package_result as package
import source_identity as source
import verify_result as verifier
from test_support import temporary, powershell, quote, copy_tool
import test_workflow_result as archive_fixtures


# Exact public wheel row read from the SHA256-pinned remote raw supplement.
# No credentials, query, fragment or private machine path is present.
RAW_HF_XET = {
    'name': 'hf-xet', 'version': '1.6.0',
    'url': 'https://files.pythonhosted.org/packages/98/b7/'
           '8c59a66d15205024662f1d66968136f13893f96df1ddc5087e2e281fc95f/'
           'hf_xet-1.6.0-cp38-abi3-win_amd64.whl',
    'sha256': 'fb4fadde1b2b70bf4c0c14a6dccbe7194b1c28947fefd5bbe3fed9d940676c3b',
}
RAW_FILE_PINS = {
    'wheel-provenance.json': '966a1308be3a6c29f750b58ed32c8210a3a1ae4b15c89dbde6c75bdc13846a7f',
    'prepared-ready.json': 'ee3ce3b90c122e033b40d9d1fbc1b74ab99c8ae2b9da6450f9c306fe656ca63d',
    'integrity-before.json': '2b26fe3ca441cf13d61b34de3864e3f84f30ed7df9f028391b763c8cd29f0101',
    'outcome.json': '1375e39da1b86fdb0785e4a84a2204bbdd69ea9cbeff025d6db3ba8b62697607',
}


def wheel_records():
    """Public wheel examples plus the actual raw hf-xet record, not an inferred URL."""
    names = {'torch', 'accelerate'}
    return [row for row in read_json(HERE / 'runtime-lock.json')['historical_wheels']
            if row['name'] in names] + [copy.deepcopy(RAW_HF_XET)]


def structural_diff(a, b, path=''):
    missing = object()
    if isinstance(a, dict) and isinstance(b, dict):
        return [p for key in sorted(a.keys() | b.keys())
                for p in structural_diff(a.get(key, missing), b.get(key, missing),
                                         path + '.' + key if path else key)]
    if isinstance(a, list) and isinstance(b, list):
        return [p for i in range(max(len(a), len(b)))
                for p in structural_diff(a[i] if i < len(a) else missing,
                                         b[i] if i < len(b) else missing, path + '[' + str(i) + ']')]
    return [path] if type(a) is not type(b) or a != b else []


def materialize_diagnostics(scratch, e):
    """Write isolated diagnostic inputs for the real evidence_for() reader.

    This is not a copy of private datasets or a new hardware result. Real-input
    tests label archive-derived stand-ins; end-to-end tests use fixture pins.
    """
    fields = {'outcome.json': 'outcome', 'prepared-ready.json': 'prepared',
              'campaign-ledger.json': 'campaign', 'campaign-started.json': 'campaign_reservation',
              'worker-started.json': 'worker_entry', 'model-load-started.json': 'model_load_entry',
              'package-integrity.json': 'runtime', 'wheel-provenance.json': 'wheel_provenance',
              'cuda-backend.json': 'cuda_backend', 'model-verification.json': 'model_hash_verification',
              'prepare-1536-audit.json': 'prepare_audit', 'tests.json': 'tests', 'frozen-controls.json': 'controls'}
    for filename, key in fields.items():
        write_json(scratch / filename, e[key])
    write_json(scratch / 'data-1536.json', {'selection': e['selection']})
    write_json(scratch / 'last-phase-error.json', {'phase': e['last_error_phase']})


def record_package_failure(scratch):
    # Execute only this diagnostic writer from the unchanged wrapper helper.
    # No phase, Python environment resolver, hardware probe or worker is called.
    result = powershell('. ' + quote(HERE / 'Remote.Common.ps1') +
                        '; $script:ScratchRoot = ' + quote(scratch) +
                        "; Write-PhaseFailure '5' 'Synthetic PackageOnly failure'")
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)


class PrivacyTests(unittest.TestCase):
    def test_canonical_origin_preserved_exactly(self):
        self.assertEqual(package.scrub_text(source.ORIGIN), source.ORIGIN)

    def test_original_defect_reproduced_by_frozen_legacy_projection(self):
        self.assertEqual(package.legacy_scrub_text(source.ORIGIN), 'http<local-path>')

    def test_public_pypi_and_pytorch_wheel_urls_are_preserved(self):
        for row in wheel_records():
            if row['name'] != 'hf-xet':
                with self.subTest(name=row['name']):
                    self.assertEqual(package.sanitize(row), row)

    def test_hf_filename_and_authenticated_query_wheel_urls_stay_redacted(self):
        urls = [row['url'] for row in wheel_records() if row['name'] == 'hf-xet']
        urls += ['https://user:password@files.pythonhosted.org/package.whl',
                 'https://files.pythonhosted.org/package.whl?token=private',
                 'https://download.pytorch.org/whl/package.whl#private']
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(package.sanitize({'url': url}), {'url': '<redacted-url>'})

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


class LegacyProjectionTests(unittest.TestCase):
    def test_modern_sanitizer_is_unchanged_from_delivered_correction(self):
        baseline = source.Git(ROOT).raw('cat-file', 'blob',
            'd356d10ddb26af39fd3f2102e63b6c1eed3581c2:' + source.TOOL + 'package_result.py')
        current = ast.parse(Path(package.__file__).read_text(encoding='utf-8'))
        def policy(tree):
            names = {'scrub_text', 'sanitize', 'URL', 'TOKEN', 'PRIVATE_KEYS', 'SECRET_KEYS', 'OMIT_KEYS'}
            return [ast.dump(n) for n in tree.body if
                    isinstance(n, ast.FunctionDef) and n.name in names or
                    isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)]
        self.assertEqual(policy(ast.parse(baseline)), policy(current))

    def test_frozen_implementation_matches_historical_ast_without_execution(self):
        raw = source.Git(ROOT).raw('cat-file', 'blob', source.TRAINING_COMMIT + ':' + source.TOOL + 'package_result.py')
        self.assertEqual(source.pin(raw)['sha256'], 'e3f64d99c476b80ca9f5da88a37864b8634fabb302c0528ef76b47153307730c')
        historical = ast.parse(raw)
        current = ast.parse(Path(package.__file__).read_text(encoding='utf-8'))
        names = {'legacy_sanitize': 'sanitize', 'legacy_scrub_text': 'scrub_text',
                 'LEGACY_PRIVATE_KEYS': 'PRIVATE_KEYS', 'LEGACY_SECRET_KEYS': 'SECRET_KEYS',
                 'LEGACY_OMIT_KEYS': 'OMIT_KEYS'}

        class HistoricalNames(ast.NodeTransformer):
            def visit_Name(self, node):
                return ast.copy_location(ast.Name(id=names.get(node.id, node.id), ctx=node.ctx), node)

        def body(tree, name):
            function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            return [ast.dump(HistoricalNames().visit(copy.deepcopy(n))) for n in function.body
                    if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                            and isinstance(n.value.value, str))]

        for old, new in (('sanitize', 'legacy_sanitize'), ('scrub_text', 'legacy_scrub_text')):
            self.assertEqual(body(historical, old), body(current, new))
        for name in ('PRIVATE_KEYS', 'SECRET_KEYS', 'OMIT_KEYS'):
            assignment = next(n for n in historical.body if isinstance(n, ast.Assign)
                              and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))
            self.assertEqual(ast.literal_eval(assignment.value), getattr(package, 'LEGACY_' + name))

    def test_historical_wheel_url_damage_and_redaction_order(self):
        urls = [source.ORIGIN] + [row['url'] for row in wheel_records()]
        urls += ['https://user:password@files.pythonhosted.org/package.whl',
                 'https://files.pythonhosted.org/package.whl?token=secret#fragment']
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(package.legacy_sanitize({'url': url}), {'url': 'http<local-path>'})
        self.assertEqual(package.legacy_scrub_text('http://example.org/a.whl'), 'htt<local-path>')
        self.assertEqual(package.legacy_scrub_text('prefix https://example.org/a.whl trailing text'),
                         'prefix http<local-path>')

    def test_legacy_traversal_is_independent_of_modern_privacy_policy(self):
        value = {'token': 'secret', 'api_key': 'historically retained', 'error': 'omitted',
                 'wheels': wheel_records(), 'path': r'C:\Users\Name\private', 'count': 2}
        before = copy.deepcopy(value)
        with patch.object(package, 'sanitize', side_effect=AssertionError('Modern sanitizer invoked')), \
                patch.object(package, 'scrub_text', side_effect=AssertionError('Modern scrubber invoked')), \
                patch.object(package, 'SECRET_KEYS', {'count'}):
            projected = package.legacy_sanitize(value)
            self.assertEqual(package.legacy_sanitize(value), projected)
        self.assertEqual(value, before)
        self.assertEqual(projected['token'], '<redacted>')
        self.assertEqual(projected['api_key'], 'historically retained')
        self.assertNotIn('error', projected)
        self.assertEqual(projected['path'], '<local-path>')
        self.assertEqual(projected['count'], 2)
        with self.assertRaises(ValueError): package.legacy_sanitize({'input_ids': [1]})


class ImmutableZipTests(unittest.TestCase):
    """Read all three immutable ZIPs; never reconstruct raw values from redactions."""
    @classmethod
    def setUpClass(cls):
        directory = Path(os.environ.get('RTX3060_LEGACY_EVIDENCE_DIR', ROOT / '.tmp/rtx3060-legacy-review'))
        cls.paths = [directory / name for name in
                     ('original.zip', 'repackaged.zip', 'RTX3060_LEGACY_RAW_CAMPAIGN_EVIDENCE.zip')]
        if not all(p.is_file() for p in cls.paths):
            raise unittest.SkipTest('Immutable ZIP inputs unavailable; set RTX3060_LEGACY_EVIDENCE_DIR')
        cls.pins = [source.ORIGINAL_ZIP_SHA256, '9c04661bd9959b8eb73015c36d479b5cacc5bf9ceae90c412582dab70b014fda',
                    '7fc6e17e924457e845c73d560aa7749b3830877b01f821609fe9b2fbc9f46b60']
        if [sha256(p) for p in cls.paths] != cls.pins:
            raise AssertionError('Immutable diagnostic ZIP SHA256 mismatch')
        cls.old, cls.new = [verifier.inspect_zip(p)[0] for p in cls.paths[:2]]
        with zipfile.ZipFile(cls.paths[2]) as archive:
            if len(archive.namelist()) != 4 or set(archive.namelist()) != set(RAW_FILE_PINS) or archive.testzip() is not None:
                raise AssertionError('Raw supplement ZIP coverage/CRC failure')
            cls.raw = {}
            for name, expected in RAW_FILE_PINS.items():
                data = archive.read(name)
                if source.pin(data)['sha256'] != expected:
                    raise AssertionError('Raw supplement file SHA256 mismatch: ' + name)
                cls.raw[name] = verifier.unique_json(data)
        # The remote root is read from the actual record solely for path redaction;
        # its private spelling is never embedded in source or printed by tests.
        cls.remote_root = PureWindowsPath(cls.raw['outcome.json']['training']['adapter']['config']['base_model_name_or_path']).parents[1]
        cls.completed = copy.deepcopy(source.campaign_payload(cls.new))
        cls.completed.update(wheel_provenance=cls.raw['wheel-provenance.json'],
                             prepared=cls.raw['prepared-ready.json'], outcome=cls.raw['outcome.json'])

    @classmethod
    def tearDownClass(cls):
        if [sha256(p) for p in cls.paths] != cls.pins:
            raise AssertionError('Immutable diagnostic ZIP was modified')

    def test_recursive_diff_is_only_schema_provenance_origins_and_wheel_urls(self):
        expected = ['outcome.integrity.git.origin', 'prepared.git.origin', 'schema_version', 'source_provenance']
        expected += ['wheel_provenance.wheels_installed_this_setup[' + str(i) + '].url' for i in range(60)]
        self.assertEqual(structural_diff(self.old, self.new), expected)

    def test_real_raw_supplement_matches_original_canonical_bytes_and_modern_pin(self):
        before = copy.deepcopy(self.completed)
        self.assertEqual(source.digest(self.old), source.ORIGINAL_EVIDENCE_SHA256)
        self.assertEqual(source.legacy_digest(self.completed, self.remote_root), source.ORIGINAL_EVIDENCE_SHA256)
        projected = package.legacy_sanitize(self.completed, self.remote_root)
        self.assertEqual(structural_diff(self.old, projected), [])
        def canonical(value):
            return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
        self.assertEqual(canonical(projected), canonical(self.old))
        self.assertEqual(package.sanitize(self.completed, self.remote_root), source.campaign_payload(self.new))
        self.assertEqual(source.sanitized_digest(self.completed, self.remote_root), source.SANITIZED_EVIDENCE_SHA256)
        self.assertEqual(source.digest(source.campaign_payload(self.new)), source.SANITIZED_EVIDENCE_SHA256)
        self.assertEqual(self.completed, before)

    def test_actual_raw_hf_xet_is_the_public_regression_value(self):
        actual = next(row for row in self.raw['wheel-provenance.json']['wheels_installed_this_setup'] if row['name'] == 'hf-xet')
        self.assertEqual(actual, RAW_HF_XET)
        url = urlsplit(actual['url'])
        self.assertEqual((url.scheme, url.netloc, url.username, url.password, url.query, url.fragment),
                         ('https', 'files.pythonhosted.org', None, None, '', ''))
        self.assertEqual(package.legacy_sanitize(actual)['url'], 'http<local-path>')
        self.assertEqual(package.sanitize(actual)['url'], '<redacted-url>')

    def test_raw_source_identity_and_preparation_pin_agree_with_original(self):
        ready = self.raw['prepared-ready.json']; before = self.raw['integrity-before.json']; outcome = self.raw['outcome.json']
        self.assertEqual(ready, self.new['prepared'])
        self.assertEqual(ready['files'], self.old['prepared']['files'])
        self.assertEqual(ready['files']['integrity-before.json'], RAW_FILE_PINS['integrity-before.json'])
        self.assertEqual(ready['git'], before['git'])
        self.assertEqual(ready['git'], outcome['integrity']['git'])
        self.assertEqual(source.GitIdentity.parse(ready['git']).commit, source.TRAINING_COMMIT)
        self.assertEqual(before['files'], self.old['outcome']['integrity']['before'])
        self.assertEqual(before['files'], outcome['integrity']['before'])
        self.assertEqual(before['files'], outcome['integrity']['after'])

    def test_all_supplied_raw_sections_match_both_zip_projections(self):
        for filename, section in (('wheel-provenance.json', 'wheel_provenance'),
                                  ('prepared-ready.json', 'prepared'), ('outcome.json', 'outcome')):
            with self.subTest(section=section):
                self.assertEqual(package.legacy_sanitize(self.raw[filename], self.remote_root), self.old[section])
                self.assertEqual(package.sanitize(self.raw[filename], self.remote_root), self.new[section])

    def test_failure_is_one_lossy_redaction_after_legacy_projection_not_sixty(self):
        self.assertEqual(source.legacy_digest(self.new), 'acc63f3a1558fe942ba506fa25310405443c0494c5a849f33b978822a352ba3d')
        rows = self.new['wheel_provenance']['wheels_installed_this_setup']
        redacted = [i for i, row in enumerate(rows) if row['url'] == '<redacted-url>']
        self.assertEqual([rows[i]['name'] for i in redacted], ['hf-xet'])
        projected = package.legacy_sanitize(source.campaign_payload(self.new))
        self.assertEqual(structural_diff(self.old, projected),
                         ['wheel_provenance.wheels_installed_this_setup[' + str(i) + '].url' for i in redacted])

    def test_all_non_sanitization_campaign_fields_remain_identical(self):
        def campaign_fields(value):
            value = copy.deepcopy(value)
            value.pop('schema_version'); value.pop('source_provenance', None)
            value['prepared']['git'].pop('origin'); value['outcome']['integrity']['git'].pop('origin')
            for row in value['wheel_provenance']['wheels_installed_this_setup']: row.pop('url')
            return value
        self.assertEqual(campaign_fields(self.old), campaign_fields(self.new))


    def test_real_input_production_reader_exposes_and_binds_phase05_drift(self):
        with temporary() as tmp:
            scratch = Path(tmp)
            # Four files use exact supplement bytes. Other diagnostics use ZIP
            # stand-ins, not a claim that all current remote scratch was captured.
            materialize_diagnostics(scratch, self.completed)
            with zipfile.ZipFile(self.paths[2]) as archive:
                for name in RAW_FILE_PINS:
                    (scratch / name).write_bytes(archive.read(name))
            baseline = package.evidence_for(scratch)
            self.assertEqual(baseline, self.completed)
            self.assertEqual(source.legacy_digest(baseline, self.remote_root), source.ORIGINAL_EVIDENCE_SHA256)
            record_package_failure(scratch)
            actual = package.evidence_for(scratch)
            self.assertEqual(structural_diff(actual, self.completed), ['last_error_phase'])
            self.assertEqual((baseline['last_error_phase'], actual['last_error_phase']), ('4', '5'))
            self.assertEqual(structural_diff(package.legacy_sanitize(actual, self.remote_root), self.old),
                             ['last_error_phase'])
            self.assertEqual(source.legacy_digest(actual, self.remote_root),
                             '3375114d6a2b22d1da7d14709573e21e86b507ab0fa597f1466d0a000be30a2c')
            self.assertEqual(source.sanitized_digest(actual, self.remote_root),
                             '76bfc6796c21d5bd765ad1289a41be4b7dccdee018bd17ec4bbadb912946589f')
            before = {p.name: sha256(p) for p in scratch.iterdir()}
            bound = source.bind_completed_campaign(actual, self.old, self.remote_root)
            self.assertEqual(bound, baseline)
            self.assertEqual(package.legacy_sanitize(bound, self.remote_root), self.old)
            self.assertEqual(package.sanitize(bound, self.remote_root), source.campaign_payload(self.new))
            self.assertEqual(source.legacy_digest(bound, self.remote_root), source.ORIGINAL_EVIDENCE_SHA256)
            self.assertEqual(source.sanitized_digest(bound, self.remote_root), source.SANITIZED_EVIDENCE_SHA256)
            self.assertEqual(actual['last_error_phase'], '5')
            self.assertEqual(before, {p.name: sha256(p) for p in scratch.iterdir()})


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
        self.e['wheel_provenance'] = {'passed': True, 'wheels_installed_this_setup': wheel_records()}
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
        old = package.legacy_sanitize(self.e, self.root)
        self.original = self.output / package.ARCHIVE
        archive_fixtures.ArchiveVerifierTests().write_archive(self.original, old)
        constants = patch.multiple(source, TRAINING_COMMIT=self.training_commit,
                                   ORIGINAL_EVIDENCE_SHA256=source.digest(old),
                                   SANITIZED_EVIDENCE_SHA256=source.sanitized_digest(self.e, self.root),
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
        result = package.sanitize(self.e, self.root)
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

    def test_archived_campaign_numeric_evidence_cannot_be_changed(self):
        self.correction(); e = self.corrected_evidence()
        e['outcome']['training']['steps'][0]['loss'] += 0.1
        self.assert_rejected(e)

    def test_redacted_wheel_metadata_cannot_change(self):
        self.correction(); original = self.corrected_evidence()
        for key, value in (('name', 'unknown'), ('version', '0.0'), ('sha256', '0' * 64)):
            with self.subTest(key=key):
                e = copy.deepcopy(original)
                row = next(row for row in e['wheel_provenance']['wheels_installed_this_setup']
                           if row['url'] == '<redacted-url>')
                row[key] = value
                self.assert_rejected(e)

    def test_arbitrary_redaction_cannot_be_replaced_with_a_public_url(self):
        self.correction(); e = self.corrected_evidence()
        row = next(row for row in e['wheel_provenance']['wheels_installed_this_setup'] if row['name'] == 'torch')
        row['url'] = '<redacted-url>'
        self.assert_rejected(e)

    def test_archive_verification_is_non_mutating_and_never_inverts_redaction(self):
        self.correction(); e = self.corrected_evidence(); before = copy.deepcopy(e)
        with patch.object(source, 'legacy_digest', side_effect=AssertionError('Cannot invert archive redaction')):
            self.assertTrue(source.source_identity(e, self.root))
        self.assertEqual(e, before)
        e['prepared']['git']['origin'] = 'http<local-path>'
        self.assert_rejected(e)

    def test_raw_public_url_change_hidden_by_legacy_scrubbing_fails_modern_pin(self):
        row = next(row for row in self.e['wheel_provenance']['wheels_installed_this_setup'] if row['name'] == 'torch')
        row['url'] = 'https://files.pythonhosted.org/different.whl'
        self.assertEqual(source.legacy_digest(self.e, self.root), source.ORIGINAL_EVIDENCE_SHA256)
        self.assertNotEqual(source.sanitized_digest(self.e, self.root), source.SANITIZED_EVIDENCE_SHA256)
        self.assert_rejected()

    def test_sanitized_provenance_pin_is_recomputed_not_trusted(self):
        self.correction(); e = self.corrected_evidence()
        e['source_provenance']['sanitized_evidence_sha256'] = '0' * 64
        self.assert_rejected(e)

    def test_frozen_projection_alone_cannot_invert_modern_redaction(self):
        clean = package.sanitize(self.e, self.root)
        self.assertNotEqual(source.legacy_digest(clean, self.root), source.ORIGINAL_EVIDENCE_SHA256)
        self.assertEqual(source.legacy_digest(self.e, self.root), source.ORIGINAL_EVIDENCE_SHA256)
        with self.assertRaisesRegex(ValueError, 'Completed campaign differs'):
            source.collect_provenance(clean, self.root)

    def test_prepared_raw_artifact_cannot_be_changed(self):
        (self.scratch / 'data-1536.json').write_text('{}', encoding='utf-8')
        with self.assertRaises(ValueError): source.certify_packaging(self.e, self.scratch, self.output, self.root)

    def test_original_zip_cannot_be_substituted(self):
        self.original.write_bytes(b'not the original')
        with self.assertRaises(ValueError): source.certify_packaging(self.e, self.scratch, self.output, self.root)

    def production_scratch(self):
        """An isolated scratch/Git fixture, with every production input present.

        The production reader sets fixture_only=False. Its certificate is valid
        ONLY under these locally patched fixture pins, never the real campaign
        pins. No fixture archive is retained or delivered as hardware evidence.
        """
        e = copy.deepcopy(self.e)
        e['last_error_phase'] = '4'
        e['campaign_reservation']['supervisor_pid'] = 555555
        materialize_diagnostics(self.scratch, e)
        actual = package.evidence_for(self.scratch)
        old = package.legacy_sanitize(actual, self.root)
        archive_fixtures.ArchiveVerifierTests().write_archive(self.original, old)
        constants = patch.multiple(source, ORIGINAL_EVIDENCE_SHA256=source.digest(old),
                                   SANITIZED_EVIDENCE_SHA256=source.sanitized_digest(actual, self.root),
                                   ORIGINAL_ZIP_SHA256=sha256(self.original))
        constants.start(); self.addCleanup(constants.stop)
        return actual, old

    def test_production_repackage_after_phase05_failure_is_certified_and_readonly(self):
        baseline, old = self.production_scratch()
        self.correction()
        original_hash = sha256(self.original)
        # No mock of evidence_for, certify_packaging, Git, digests or verifier.
        # Only the generated supervisor PID is treated as already exited.
        with patch.object(package, 'process_active', return_value=False):
            archive = package.package(self.scratch, self.output, self.root)
            first_hash = sha256(archive)
            record_package_failure(self.scratch)
            actual = package.evidence_for(self.scratch)
            self.assertEqual(structural_diff(actual, baseline), ['last_error_phase'])
            self.assertNotEqual(source.legacy_digest(actual, self.root), source.digest(old))
            self.correction(value='fixture PackageOnly integration correction\n')
            before = {p.name: sha256(p) for p in self.scratch.iterdir() if p.is_file()}
            archive = package.package(self.scratch, self.output, self.root)
            published, _ = verifier.inspect_zip(archive)
            result = verifier.verify_evidence(published,
                source_check=lambda value: source.source_identity(value, self.root))
            self.assertEqual(result, {'archive_integrity': 'PASS',
                'training_gate': 'RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_SMOKE_PASS',
                'certified_training_pass': True, 'failed_checks': []})
            self.assertEqual(published['schema_version'], 3)
            self.assertEqual(source.campaign_payload(published), package.sanitize(baseline, self.root))
            self.assertEqual(published['last_error_phase'], '4')
            self.assertEqual(package.evidence_for(self.scratch)['last_error_phase'], '5')
            corrected_hash = sha256(archive)
            self.assertNotEqual(first_hash, corrected_hash)
            self.assertEqual(package.package(self.scratch, self.output, self.root), archive)
            self.assertEqual(sha256(archive), corrected_hash)
            self.assertEqual(before, {p.name: sha256(p) for p in self.scratch.iterdir() if p.is_file()})
        for pin in (original_hash, first_hash):
            self.assertEqual(sha256(self.scratch / 'packaged-history' / (pin + '.zip')), pin)
        # The same fixture publication cannot pass the real immutable campaign pin.
        self.assertNotEqual(source.digest(source.campaign_payload(published)),
                            'd5ba0e4a5ab44d76b957abfa92e4795eb61ddee3594e37288dd6a712c737ecd7')

    def test_phase05_recovery_does_not_hide_campaign_or_url_mutations(self):
        baseline, _ = self.production_scratch()
        mutations = (
            ('outcome', 'training', 'steps', 0, 'loss'),
            ('outcome', 'training', 'steps', 0, 'memory', 'free_bytes'),
            ('outcome', 'training', 'adapter', 'files', 'adapter_config.json', 'sha256'),
            ('outcome', 'repository_commit'), ('selection', 'selected_lengths', 0),
            ('model_hash_verification', 'revision'), ('controls', 'decision_sha256'),
            ('campaign', 'nonce'), ('wheel_provenance', 'wheels_installed_this_setup', 0, 'url'),
        )
        for path in mutations:
            with self.subTest(path=path):
                e = copy.deepcopy(baseline); e['last_error_phase'] = '5'
                parent = e
                for key in path[:-1]: parent = parent[key]
                value = parent[path[-1]]
                parent[path[-1]] = value + 1 if isinstance(value, (int, float)) else (
                    'https://example.org/changed.whl' if path[-1] == 'url' else 'changed')
                materialize_diagnostics(self.scratch, e)
                with patch.object(package, 'process_active', return_value=False), self.assertRaises(ValueError):
                    package.package(self.scratch, self.output, self.root)
                self.assertEqual(sha256(self.original), source.ORIGINAL_ZIP_SHA256)

    def test_phase05_recovery_requires_exact_original_zip(self):
        self.production_scratch()
        record_package_failure(self.scratch)
        self.original.write_bytes(b'substituted original fixture')
        with patch.object(package, 'process_active', return_value=False), self.assertRaisesRegex(ValueError, 'Original result ZIP'):
            package.package(self.scratch, self.output, self.root)

    def test_phase05_recovery_keeps_prepared_artifact_hashes_strict(self):
        self.production_scratch()
        record_package_failure(self.scratch)
        # This private prepared file is not projected into evidence_for().
        (self.scratch / 'train-contexts.json').write_bytes(b'{"changed":true}')
        with patch.object(package, 'process_active', return_value=False), self.assertRaisesRegex(ValueError, 'Prepared artifact changed'):
            package.package(self.scratch, self.output, self.root)

    def test_only_exact_phase05_diagnostic_can_use_original_phase(self):
        baseline, old = self.production_scratch()
        for phase in (None, '0', '1', '2', '3', '6', '04', '05', 4, 5, True):
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                source.bind_completed_campaign(dict(baseline, last_error_phase=phase), old, self.root)
        changed = dict(old, last_error_phase='5')
        with self.assertRaisesRegex(ValueError, 'Original evidence digest mismatch'):
            source.bind_completed_campaign(dict(baseline, last_error_phase='5'), changed, self.root)

    def test_phase05_binding_requires_raw_completed_campaign(self):
        baseline, old = self.production_scratch()
        for schema, status in ((3, 'completed'), (2, 'active')):
            e = dict(baseline, schema_version=schema, last_error_phase='5',
                     campaign=dict(baseline['campaign'], status=status))
            with self.assertRaisesRegex(ValueError, 'Expected raw completed campaign'):
                source.bind_completed_campaign(e, old, self.root)

    def test_direct_raw_and_published_digest_checks_do_not_ignore_error_phase(self):
        self.correction()
        raw = dict(self.e, last_error_phase='5')
        with self.assertRaisesRegex(ValueError, 'Completed campaign differs'):
            source.collect_provenance(raw, self.root)
        published = self.corrected_evidence()
        published['last_error_phase'] = '5'
        self.assert_rejected(published)

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
            first_corrected_hash = sha256(archive)
            self.correction(value='fixture second tooling correction\n')
            archive = package.package(self.scratch, self.output, self.root)
            e, _ = verifier.inspect_zip(archive)
            self.assertTrue(source.source_identity(e, self.root))
            corrected_hash = sha256(archive)
            self.assertNotEqual(first_corrected_hash, corrected_hash)
            self.assertEqual(package.package(self.scratch, self.output, self.root), archive)
            self.assertEqual(sha256(archive), corrected_hash)
        self.assertEqual(sha256(self.scratch / 'packaged-history' / (original_hash + '.zip')), original_hash)
        self.assertEqual(sha256(self.scratch / 'packaged-history' / (first_corrected_hash + '.zip')), first_corrected_hash)
        self.assertEqual(before, {p.name: sha256(p) for p in self.scratch.iterdir() if p.is_file()})
        self.assertEqual(e['prepared']['git']['origin'], source.ORIGIN)
        self.assertEqual(e['outcome'], self.e['outcome'])
        self.assertEqual(e['wheel_provenance'], package.sanitize(self.e['wheel_provenance']))


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
