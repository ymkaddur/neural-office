"""Isolated Windows controller fixture for the renderer recovery regression."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import uuid

from neural_office.desktop_service import DesktopService
from neural_office.ledger import Ledger
from neural_office.windows_job import Job


def main():
    database, project, thread, report = sys.argv[1:]
    root = Path(database).resolve().parent
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith('oficina-v535-'):
        raise ValueError('The interruption test requires its private temporary office.')
    admitted = threading.Event()

    class WaitingProvider:
        def __init__(self, name, profile, log):
            self.job = Job(name)

        def start(self):
            self.job.start([sys.executable, '-I', '-c', 'import time; time.sleep(55)'])

        def infer(self, payload):
            admitted.set()
            threading.Event().wait(50)
            raise TimeoutError('The harness did not interrupt its controller in time.')

        def request_stop(self):
            pass

        def terminate(self):
            self.job.terminate()

        def close(self):
            self.job.close()

    model = dict(mode='fixture', model='proveedor-controlado', model_digest='a'*64)
    service = DesktopService(Ledger(database),backend_factory=WaitingProvider,model_discovery=lambda:[model])
    grant = service.preview_excerpts(project,thread,report,model['model_digest'],'Revisa solamente los fragmentos autorizados de esta prueba.')
    attempt = service.start(grant['approval_token'],str(uuid.uuid4()),grant['expected_revision'])
    if not admitted.wait(12):
        raise RuntimeError('The controlled provider did not receive its call.')
    print(json.dumps(dict(attempt=attempt['id'],report=report)),flush=True)
    if sys.stdin.readline().strip()!='interrupt':
        raise RuntimeError('The test harness did not request the interruption.')
    # Exit without service shutdown to exercise the real job close and orphaned lease.
    os._exit(0)


if __name__=='__main__':
    main()
