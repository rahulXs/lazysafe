"""module with SE04: process-global registration."""

import atexit
import signal


def cleanup():
    pass


atexit.register(cleanup)
signal.signal(signal.SIGINT, lambda s, f: None)
