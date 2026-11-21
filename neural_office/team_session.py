"""One idle model owned by a desktop session, reusable only by its original project."""
import threading
import time


IDLE_SECONDS = 120


def discard(engine):
    try:
        engine.terminate()
    finally:
        engine.close()


class TeamSession:
    def __init__(self, *, idle_seconds=IDLE_SECONDS):
        self._lock = threading.Lock()
        self._idle_seconds = idle_seconds
        self._idle = None
        self._timer = None
        self._closed = False

    def _clear_locked(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        idle, self._idle = self._idle, None
        return idle

    def take(self, key):
        with self._lock:
            idle = self._clear_locked()
            if idle is None:
                return None
            scope, engine, deadline = idle
            if key == scope and time.monotonic() < deadline and not self._closed:
                return engine
            discard(engine)
            return None

    def _expire(self, ticket):
        with self._lock:
            if self._idle is ticket:
                self._clear_locked()
                discard(ticket[1])

    def retain(self, key, engine, settle):
        """Publish no reusable engine until the exact seven completed calls are settled."""
        with self._lock:
            if self._closed or self._idle is not None:
                return False
            ticket = (key, engine, time.monotonic() + self._idle_seconds)
            timer = threading.Timer(self._idle_seconds, self._expire, (ticket,))
            timer.daemon = True
            timer.start()
            try:
                if not settle():
                    return False
                self._timer, self._idle = timer, ticket
                return True
            finally:
                if self._idle is not ticket:
                    timer.cancel()

    def close(self):
        with self._lock:
            self._closed = True
            idle = self._clear_locked()
            if idle is not None:
                discard(idle[1])
