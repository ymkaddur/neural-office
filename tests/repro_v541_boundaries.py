"""Compare the three audit signatures against a selected checkout, Windows only.

Only synthetic temporary ledgers/processes are used; no model or remote path is opened.
The selected checkout is imported, never edited. Run separately from unittest discovery.
"""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
from unittest.mock import patch
import uuid


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--expect', choices=('baseline','fixed'), required=True)
    args=parser.parse_args()
    if os.name!='nt': parser.error('Native Windows is required')
    sys.path.insert(0,str(args.repo.resolve(strict=True)))
    from neural_office import continuity
    from neural_office.ledger import Ledger, Denied
    from neural_office.runner import run, recover
    from neural_office.windows_job import Job
    from neural_office.files import capture_html
    from neural_office.legacy import snapshot, reconcile, rebind
    html=b'<html lang="en"><title>Fixture</title></html>'
    profile={'mode':'fixture','model':'synthetic','model_digest':'a'*64,'roles':1}
    results={}

    with tempfile.TemporaryDirectory() as folder:
        ledger=Ledger(Path(folder)/'synthetic.sqlite3')
        original_seal=continuity.seal
        def interrupted(con):
            original_seal(con)
            raise OSError('INJECTED_BEFORE_INITIAL_COMMIT')
        try:
            with patch.object(continuity,'seal',interrupted): ledger.initialize()
        except OSError as exc: results['first_error']=str(exc)
        with closing(sqlite3.connect(ledger.path)) as con:
            results['schema_after_failure']=con.execute('PRAGMA user_version').fetchone()[0]
        results['witness_bytes_after_failure']=continuity.witness_path(ledger.path).stat().st_size
        try:
            continuity.protect(ledger)
            results['enrollment_retry']='PROTECTED'
        except Denied as exc: results['enrollment_retry']=str(exc)

    with tempfile.TemporaryDirectory() as folder:
        ledger=Ledger(Path(folder)/'synthetic.sqlite3'); ledger.initialize(); ledger.register('p',folder)
        attempt=ledger.reserve('p','Audit synthetic HTML.',html,profile,'first',admit=True)
        entered=threading.Event(); resume=threading.Event(); started=threading.Event(); leave=threading.Event()
        owned={}; failures=[]
        class Backend:
            def __init__(self,name,*_):
                entered.set()
                if not resume.wait(10): raise RuntimeError('FIXTURE_CONSTRUCTOR_TIMEOUT')
                self.job=Job(name); owned['backend']=self
            def start(self):
                self.job.start([sys.executable,'-B','-c','import time;time.sleep(20)'])
                until=time.monotonic()+5
                while not self.job.active() and time.monotonic()<until: time.sleep(.01)
                started.set()
                if not leave.wait(10): raise RuntimeError('FIXTURE_START_TIMEOUT')
            def infer(self,payload):
                return {'done':True,'message':{'content':'Synthetic advisory text.'}}
            def request_stop(self): self.job.terminate()
            def terminate(self): self.job.terminate()
            def close(self): self.job.close()
        def work():
            try: run(ledger,attempt,1,Backend)
            except Exception as exc: failures.append(str(exc))
        worker=threading.Thread(target=work); worker.start()
        second=None
        try:
            assert entered.wait(5), 'Fixture did not reach constructor'
            try: results['recovery_during_constructor']=recover(ledger,attempt)
            except Denied as exc: results['recovery_during_constructor']=str(exc)
            if results['recovery_during_constructor']=='FAILED':
                other=ledger.reserve('p','Audit synthetic HTML.',html,profile,'second',admit=True)
                generation=ledger.acquire(other,'Local\\Synthetic_'+uuid.uuid4().hex)
                second=(other,generation)
            resume.set(); assert started.wait(5), 'Fixture did not start'
            results['old_job_active']=owned['backend'].job.active()
            results['lease_reassigned']=ledger.status()['lease']['attempt']!=attempt
            leave.set(); worker.join(10)
            assert not worker.is_alive(), 'Fixture controller did not finish'
            results['runner_errors']=failures
            if second: ledger.release_after_termination(*second,failed=True)
        finally:
            resume.set(); leave.set(); worker.join(15)
            if worker.is_alive(): raise RuntimeError('FIXTURE_CONTROLLER_UNRESOLVED')

    unc=r'\\synthetic.invalid\share'
    def inspect():
        with snapshot(unc): pass
    operations=(lambda:capture_html(unc+r'\input.html',unc),
                lambda:capture_html(unc+r'\input.html',r'C:\synthetic'),
                inspect,lambda:reconcile(None,unc),lambda:rebind(None,'synthetic',unc))
    results['path_order']=[]
    for operation in operations:
        with patch.object(Path,'resolve',side_effect=AssertionError('RESOLUTION_BEFORE_DENIAL')):
            try: operation()
            except AssertionError as exc: results['path_order'].append(str(exc))
            except Denied as exc:
                if 'NETWORK' not in str(exc): raise
                results['path_order'].append('EARLY_DENIAL')
            else: raise AssertionError('Excluded path was admitted')
    print(json.dumps(results,indent=2))
    assert results['schema_after_failure']==1 and results['witness_bytes_after_failure']==0
    if args.expect=='baseline':
        assert results['enrollment_retry']=='CONTINUITY_UPGRADE_REQUIRED_RUN_PROTECT'
        assert results['recovery_during_constructor']=='FAILED' and results['lease_reassigned']
        assert results['old_job_active']>0 and 'STALE_LEASE' in results['runner_errors']
        assert results['path_order']==['RESOLUTION_BEFORE_DENIAL']*5
    else:
        assert results['enrollment_retry']=='PROTECTED'
        assert results['recovery_during_constructor']=='OFFICE_RUNNER_STILL_ACTIVE'
        assert not results['lease_reassigned'] and not results['runner_errors']
        assert results['path_order']==['EARLY_DENIAL']*5


if __name__=='__main__': main()
