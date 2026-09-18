"""Cross-platform advisory file locks."""
import sys
from contextlib import contextmanager


if sys.platform == 'win32':
    import msvcrt

    def _lock(handle, non_blocking=False):
        mode = msvcrt.LK_NBLCK if non_blocking else msvcrt.LK_LOCK
        msvcrt.locking(handle.fileno(), mode, 1)

    def _unlock(handle):
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock(handle, non_blocking=False):
        flags = fcntl.LOCK_EX
        if non_blocking:
            flags |= fcntl.LOCK_NB
        fcntl.flock(handle, flags)

    def _unlock(handle):
        fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def file_claim(path):
    with path.open('a') as handle:
        try:
            _lock(handle, non_blocking=True)
        except (BlockingIOError, OSError):
            yield False
            return
        try:
            yield True
        finally:
            _unlock(handle)


@contextmanager
def exclusive_file_lock(path):
    with path.open('a') as handle:
        _lock(handle, non_blocking=False)
        try:
            yield
        finally:
            _unlock(handle)
