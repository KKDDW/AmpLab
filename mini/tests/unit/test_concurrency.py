"""test_concurrency.py: ConcurrencyGate 互斥 + 重入"""
import threading
import time

import pytest

from mini.utils.concurrency import ConcurrencyGate


class TestGate:
    def test_basic_acquire_release(self):
        g = ConcurrencyGate()
        assert not g.busy
        assert g.try_acquire()
        assert g.busy
        g.release()
        assert not g.busy

    def test_reentrant(self):
        g = ConcurrencyGate()
        assert g.try_acquire()
        assert g.try_acquire()   # 同线程重入
        assert g.busy
        g.release()
        assert g.busy
        g.release()
        assert not g.busy

    def test_non_owner_cannot_acquire(self):
        g = ConcurrencyGate()
        assert g.try_acquire()
        results = {}

        def attempt():
            results["got"] = g.try_acquire()

        t = threading.Thread(target=attempt)
        t.start()
        t.join()
        assert results["got"] is False
        g.release()

    def test_release_by_non_owner_raises(self):
        g = ConcurrencyGate()
        g.try_acquire()
        # 跨线程 release 应该 raise
        results = {}

        def bad_release():
            try:
                g.release()
            except RuntimeError as e:
                results["err"] = str(e)

        t = threading.Thread(target=bad_release)
        t.start()
        t.join()
        assert "non-owner" in results["err"]
        g.release()
