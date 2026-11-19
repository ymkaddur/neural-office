"""Launcher preflight for the pinned binary readers on Windows."""
from importlib import metadata
from io import BytesIO
from pathlib import Path
import sys


def ready(requirements):
    pins = [line.split(' --hash=')[0].strip().split('==') for line in requirements.read_text('utf-8').splitlines()
            if '==' in line and not line.lstrip().startswith('#')]
    try:
        import pypdfium2.raw
        from PIL import Image
        if not pins or not all(metadata.version(name) == version for name, version in pins):
            return False
        if not pypdfium2.raw.FPDF_GetPageCount:
            return False
        for format_name in ('PNG', 'JPEG'):
            buffer = BytesIO()
            Image.new('RGB', (1, 1)).save(buffer, format=format_name)
            buffer.seek(0)
            with Image.open(buffer) as reopened:
                reopened.load()
        return True
    except (ImportError, OSError, ValueError, AttributeError):
        return False


if __name__ == '__main__':
    print('available' if ready(Path(sys.argv[1])) else 'missing')
