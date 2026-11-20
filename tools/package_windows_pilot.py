"""Build the testable Windows pilot from tracked runtime sources and the compiled host."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
HOST = 'desktop/src-tauri/target/release/neural-office-desktop.exe'
GUIDE = 'docs/PILOTO_WINDOWS.md'
RUNTIME_FILES = ('Start-NeuralOffice-Desktop.ps1', 'requirements-readers-windows.txt',
                 'examples/audit-sample.html', 'LICENSE', GUIDE)


def package(exe, notices, output):
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    archive = subprocess.check_output(['git', 'archive', '--format=zip', commit, '--',
                                       'neural_office', *RUNTIME_FILES], cwd=ROOT)
    with ZipFile(io.BytesIO(archive)) as sources:
        files = {name: sources.read(name) for name in sources.namelist()
                 if name.startswith('neural_office/') and name.endswith('.py')}
        for name in RUNTIME_FILES:
            files['LEEME.md' if name == GUIDE else name] = sources.read(name)
    if not {'neural_office/desktop_stdio.py', 'neural_office/check_readers.py'} <= files.keys():
        raise ValueError('Missing desktop runtime')

    manifest = (notices / 'components.json').read_bytes()
    data = json.loads(manifest)
    files['native-notices/components.json'] = manifest
    files['native-notices/README.md'] = (notices / 'README.md').read_bytes()
    records = [data['own_license'], *(n for c in data['components'] for n in c['notices'])]
    for record in records:
        name = PurePosixPath(record['path'])
        path = (notices / name).resolve()
        if not path.is_relative_to(notices.resolve()) or name.as_posix() != record['path']:
            raise ValueError('Unexpected notice path')
        contents = path.read_bytes()
        if hashlib.sha256(contents).hexdigest() != record['sha256']:
            raise ValueError(f'Notice digest differs: {name}')
        files['native-notices/' + name.as_posix()] = contents
    files[HOST] = exe.read_bytes()
    files['SOURCE_COMMIT'] = (commit + '\n').encode('ascii')
    files['SHA256SUMS'] = ''.join(f'{hashlib.sha256(files[name]).hexdigest()}  {name}\n'
                                  for name in sorted(files)).encode('utf-8')
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        candidate = Path(temp) / 'pilot.zip'
        with ZipFile(candidate, 'w') as dest:
            for name, content in sorted(files.items()):
                dest.writestr(ZipInfo(name), content, compress_type=ZIP_DEFLATED)
        candidate.replace(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', required=True, type=Path)
    parser.add_argument('--notices', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    package(args.exe, args.notices, args.output)
