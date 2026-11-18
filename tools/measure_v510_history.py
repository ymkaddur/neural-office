"""Time old and recent event pages through the ordinary, continuity-checked service."""
import json
import math
from pathlib import Path
import statistics
import tempfile
import time
from unittest.mock import patch

from neural_office import continuity
from neural_office.desktop_service import DesktopService
from neural_office.ledger import Ledger


def experiment(root, projects, total):
    import psutil
    ledger = Ledger(root/'state.sqlite3')
    service = DesktopService(ledger)
    try:
        for i in range(projects):
            folder = root/str(i)
            folder.mkdir()
            ledger.register(str(i),folder)
        ids=[]
        for i in (1,2):
            attempt=ledger.reserve('0','Revisar el ejemplo público.',b'<html lang="es"><title>Ejemplo</title></html>',
                                   {'roles':1,'model':'synthetic','mode':'fixture','model_digest':'a'*64},str(i),admit=True)
            ledger.cancel(attempt)
            ids.append(attempt)
        # Fixed-size synthetic traffic. Only the two target slices belong to the attempts.
        with ledger.transaction() as con:
            left=total-con.execute('SELECT count(*) FROM events').fetchone()[0]
            assert left>=32
            for i in range(left):
                payload={'attempt':ids[0]} if i<16 else {'attempt':ids[1]} if i>=left-16 else {}
                ledger._event(con,'TEST_OBSERVATION',payload)
        with ledger.connection() as con:
            assert con.execute('SELECT count(*) FROM events').fetchone()[0]==total
        process=psutil.Process()
        samples={k:[] for k in ('early','recent')}
        for repeat in range(25):
            pair=list(zip(samples,ids))
            for key,attempt in (reversed(pair) if repeat%2 else pair):
                start=time.perf_counter_ns()
                cpu=time.process_time_ns()
                page=service.attempt_events(attempt,0,8)
                elapsed=time.perf_counter_ns()-start
                spent=time.process_time_ns()-cpu
                assert page['has_more'] and len(page['events'])==8
                assert all(e['payload'].get('attempt')==attempt for e in page['events'])
                if repeat:
                    samples[key].append((elapsed/1e6,spent/1e6,process.memory_info().rss/2**20))
        rows={}
        for name,trials in samples.items():
            wall,cpu,rss=zip(*trials)
            rows[name]={'reads':len(wall),'p50_ms':statistics.median(wall),'p95_ms':sorted(wall)[math.ceil(.95*len(wall))-1],
                        'cpu_ms_per_read':sum(cpu)/len(cpu),'max_post_read_ws_mib':max(rss)}
        observed=[]
        original=continuity.signature
        def timed_signature(con):
            start=time.perf_counter_ns()
            value=original(con)
            observed.append((time.perf_counter_ns()-start)/1e6)
            return value
        with patch.object(continuity,'signature',timed_signature):
            start=time.perf_counter_ns()
            probe=service.attempt_events(ids[0],0,8)
            end=time.perf_counter_ns()
        assert len(observed)==1 and len(probe['events'])==8
        footprint=sum(p.stat().st_size for p in root.iterdir() if p.is_file())
        return {'projects':projects,'events':total,'returned_per_read':8,'pages':rows,'fixture_file_bytes':footprint,
                'one_instrumented_read_ms':(end-start)/1e6,'within_read_signature_ms':observed[0]}
    finally:
        service.close()


if __name__=='__main__':
    rows=[]
    for projects,total in ((1,100),(50,100),(1,10000),(50,10000)):
        with tempfile.TemporaryDirectory(prefix='neural-office-event-page-') as tmp:
            rows.append(experiment(Path(tmp),projects,total))
    print(json.dumps(rows,indent=2))
