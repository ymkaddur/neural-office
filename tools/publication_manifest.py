"""Check canonical repository bytes, or refresh the release inventory from the Git index."""
import argparse
import hashlib
import io
from pathlib import Path
import subprocess
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'PUBLICATION_MANIFEST.sha256'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='use files staged for the next commit')
    args = parser.parse_args()
    tree = subprocess.check_output(['git', 'write-tree'], cwd=ROOT, text=True).strip() if args.write else 'HEAD'
    archive = subprocess.check_output(['git', '-c', 'core.autocrlf=false', '-c', 'core.eol=lf',
                                       'archive', '--format=zip', tree], cwd=ROOT)
    with ZipFile(io.BytesIO(archive)) as snapshot:
        names = sorted(n for n in snapshot.namelist() if not n.endswith('/') and n != MANIFEST)
        expected = ''.join(f'{hashlib.sha256(snapshot.read(n)).hexdigest()}  {n}\n' for n in names).encode('utf-8')
        if args.write:
            (ROOT / MANIFEST).write_bytes(expected)
        elif expected != snapshot.read(MANIFEST):
            raise SystemExit('Publication manifest differs. Stage the intended files and run tools/publication_manifest.py --write.')
    print(f'{len(names)} tracked files in the publication manifest.')


if __name__ == '__main__':
    main()
