"""Windows UI timing probe. Copied into a temporary test peer, never into the pilot."""
import json
from pathlib import Path
import runpy
import time

from .attachments import AttachmentStore


def main():
    work = Path(__file__).resolve().parents[2]
    settings = json.loads((work / 'timing-probe.json').read_bytes())
    release = work / 'release-latest'
    read_report = AttachmentStore.report

    def defer_latest(store, project_id, report_id, *, thread_id='main'):
        result = read_report(store, project_id, report_id, thread_id=thread_id)
        if report_id == settings['latest_id'] and not release.exists():
            (work / 'latest-held').write_text(result['id'], encoding='ascii')
            deadline = time.monotonic() + 25
            while not release.exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError('The UI test did not release the retained delivery')
                time.sleep(.025)
        return result

    AttachmentStore.report = defer_latest
    source = Path(settings['package']) / 'neural_office/desktop_stdio.py'
    return runpy.run_path(str(source), run_name='neural_office.measured_stdio')['main']()


if __name__ == '__main__':
    raise SystemExit(main())
