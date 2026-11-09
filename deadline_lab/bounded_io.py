"""Deadline-bounded line framing for our owned POSIX child processes.

A readable pipe is not necessarily a complete line. Never call blocking readline
following select: a child can write half a greeting and hang indefinitely.
"""
from __future__ import annotations
import math
import os
import select
import time


class LineReader:
    def __init__(self, fd: int, maximum: int = 4096):
        if type(fd) is not int or fd < 0 or type(maximum) is not int or maximum < 1:
            raise ValueError('invalid pipe descriptor or line limit')
        self.fd = fd
        self.maximum = maximum
        self.buffer = bytearray()

    def read(self, timeout: float) -> str | None:
        """Return one ASCII line without LF, or None at the absolute deadline.

        Partial input is retained for a later read. EOF, non-ASCII and oversized
        frames are errors, never successful readiness observations. One reader
        must own the fd. This is for POSIX pipes, not arbitrary Windows handles.
        """
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('timeout must be positive and finite')
        deadline = time.monotonic() + timeout
        while True:
            end = self.buffer.find(b'\n')
            if end >= 0:
                if end > self.maximum:
                    raise ValueError('oversized child line')
                raw = bytes(self.buffer[:end])
                del self.buffer[:end + 1]
                return raw.decode('ascii', errors='strict')
            if len(self.buffer) > self.maximum:
                raise ValueError('oversized child line')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            try:
                ready, _, _ = select.select([self.fd], [], [], remaining)
                if not ready:
                    return None
                data = os.read(self.fd, min(4096, self.maximum + 1 - len(self.buffer)))
            except InterruptedError:
                continue
            if not data:
                raise EOFError('child pipe closed before a complete line')
            self.buffer.extend(data)
