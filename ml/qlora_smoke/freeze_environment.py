"""Capture exact successful installed versions and official wheel provenance."""
import importlib.metadata
import platform
from urllib.parse import urlparse, unquote
from packaging.version import Version
from common import ROOT, HERE, SCRATCH, read_json, write_json, sha256


def main():
    installed = {d.metadata['Name']: d.version for d in importlib.metadata.distributions()}
    assert all(not Version(v).is_prerelease and not Version(v).is_devrelease for v in installed.values())
    report = read_json(SCRATCH / 'pip-report.json')
    provenance = []
    for item in report['install']:
        download = item['download_info']
        url = download['url']
        parsed = urlparse(url)
        assert parsed.hostname in ('files.pythonhosted.org', 'download.pytorch.org', 'download-r2.pytorch.org')
        assert unquote(parsed.path).endswith('.whl')
        assert not item.get('is_yanked', False)
        provenance.append({'name': item['metadata']['name'], 'version': item['metadata']['version'],
                           'url': url, 'sha256': download['archive_info']['hashes']['sha256']})
    # pip itself comes from the already-installed Python's bundled wheel.
    import ensurepip
    for wheel in (ROOT.__class__(ensurepip.__file__).parent / '_bundled').glob('*.whl'):
        provenance.append({'name': 'pip', 'version': installed['pip'], 'source': str(wheel),
                           'sha256': sha256(wheel), 'origin': 'Python 3.12.10 bundled ensurepip wheel'})
    requirements = ('# Verified isolated Windows Python 3.12.10 binary-only smoke environment.\n'
                    '--only-binary=:all:\n--extra-index-url https://download.pytorch.org/whl/cu126\n' +
                    '\n'.join(f'{k}=={v}' for k, v in sorted(installed.items(), key=lambda x: x[0].lower())) + '\n')
    (HERE / 'requirements.txt').write_text(requirements, encoding='utf-8', newline='\n')
    baseline = dict(line.split('==') for line in (ROOT / 'ml/baseline/requirements.txt').read_text().splitlines()
                    if '==' in line and not line.startswith('#'))
    differences = {name: {'baseline': baseline[name], 'smoke': version}
                   for name, version in installed.items() if name in baseline and version != baseline[name]}
    write_json(SCRATCH / 'environment.json', {'python': platform.python_version(), 'installed': installed,
                                            'wheels': provenance, 'binary_only': True, 'prereleases': False,
                                            'core_stack_preserved': True,
                                            'private_environment_transitive_differences': differences,
                                            'fsspec_note': 'datasets 5.0.1 requires <=2026.6.0; private environment only.'})
    print(f'{len(installed)} exact versions pinned; {len(provenance)} wheels recorded')


if __name__ == '__main__':
    main()
