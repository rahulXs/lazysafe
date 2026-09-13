"""module that spawns a thread."""
import threading
import time


def _worker():
    time.sleep(300)


t = threading.Thread(target=_worker)
t.daemon = True
t.start()
