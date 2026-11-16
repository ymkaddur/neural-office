"""Optional regression: supply the separately retained historical V5 directory.

No model or credentials are used. Unauthorized requests must never reach upstream.
"""
import http.client
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

BASE=Path(sys.argv.pop(1)).resolve()
sys.path.insert(0,str(BASE/'runtime'))
from gateway45 import SingleFlightServer, SingleFlightHandler
from protocol import MAX_BODY


class CloseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.finished=threading.Event();self.durations=[]
        parent=self
        class Observed(SingleFlightHandler):
            def finish(self):
                start=time.perf_counter()
                try:super().finish()
                finally:parent.durations.append(time.perf_counter()-start);parent.finished.set()
        self.server=SingleFlightServer(('127.0.0.1',0),self.tmp.name,token='x'*48,live=True,testing=True)
        self.server.RequestHandlerClass=Observed
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01})
        self.thread.start();self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(3)

    def connection(self):return http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=2)

    def headers(self,c,length):
        c.putrequest('POST','/api/chat');c.putheader('X-Neural-Office-Session','invalid')
        c.putheader('Content-Length',str(length));c.endheaders()

    def test_delayed_body_retains_401_and_never_opens_upstream(self):
        # Only the test client's connection is constructed before the patch.
        for delay in (0,.001,.01,.05):
            for n in range(20):
                c=self.connection()
                try:
                    with patch('gateway45.http.client.HTTPConnection',side_effect=AssertionError('UPSTREAM_REACHED')):
                        self.headers(c,100);time.sleep(delay);c.send(b'x'*100)
                        response=c.getresponse();body=response.read()
                        self.assertEqual(response.status,401);self.assertIn(b'OPERATOR_SESSION_REQUIRED',body)
                finally:c.close()

    def test_absent_body_does_not_hold_worker_indefinitely(self):
        c=self.connection()
        try:
            self.headers(c,MAX_BODY)
            self.assertEqual(c.getresponse().status,401)
            self.assertTrue(self.finished.wait(1.5))
            self.assertLess(self.durations[-1],1.5)
        finally:c.close()

    def test_aborted_client_is_released(self):
        c=self.connection();self.headers(c,100);c.close()
        self.assertTrue(self.finished.wait(1.5))

    def test_excess_sender_is_bounded_without_claiming_reliable_status(self):
        c=self.connection()
        try:
            self.headers(c,MAX_BODY*2)
            try:c.send(b'x'*(MAX_BODY*2))
            except OSError:pass
            self.assertTrue(self.finished.wait(1.5))
            self.assertLess(self.durations[-1],1.5)
        finally:c.close()

    def test_health_route_keeps_normal_response(self):
        c=self.connection()
        try:
            c.request('GET','/health');r=c.getresponse();self.assertEqual(r.status,200);r.read()
        finally:c.close()


if __name__=='__main__':unittest.main()
