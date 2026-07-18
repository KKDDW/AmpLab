# -*- coding: utf-8 -*-
"""ampacity-lab (mini): ConcurrencyGate
=============================================

一个非阻塞的并发控制门:
  - try_acquire() -> bool: 不阻塞, 抢到 True, 抢不到 False
  - release(): 释放
  - busy -> bool: 当前是否被占

跟 threading.Lock 的区别:
  - 只能 try_acquire, 不能阻塞等 (想等就 busy loop)
  - 自带"重入友好"语义: 持有者可以再 acquire (计数 +1)
  - 自带 is_busy 查询

用法:
    gate = ConcurrencyGate()
    if not gate.try_acquire():
        return Result.make_fail("engine busy")
    try:
        do_stuff()
    finally:
        gate.release()

    # 或者配合 with (Python 3.10+):
    if not gate.try_acquire():
        return Result.make_fail("engine busy")
    with gate:  # 自动 release
        do_stuff()
"""
from __future__ import annotations

import threading
from typing import Optional


class ConcurrencyGate:
    """非阻塞并发门 (支持重入)"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._owner: Optional[int] = None  # 持有者线程 id
        self._count: int = 0  # 重入次数

    @property
    def busy(self) -> bool:
        return self._count > 0

    def owner(self) -> Optional[int]:
        return self._owner

    def try_acquire(self) -> bool:
        """非阻塞抢锁; 同线程可重入"""
        tid = threading.get_ident()
        with self._lock:
            if self._count == 0:
                self._owner = tid
                self._count = 1
                return True
            if self._owner == tid:
                self._count += 1
                return True
            return False

    def release(self) -> None:
        tid = threading.get_ident()
        with self._lock:
            if self._owner != tid:
                raise RuntimeError(
                    f"release by non-owner: owner={self._owner}, caller={tid}"
                )
            self._count -= 1
            if self._count == 0:
                self._owner = None

    def __enter__(self) -> "ConcurrencyGate":
        if self._owner != threading.get_ident():
            raise RuntimeError("use try_acquire() to enter the gate")
        return self

    def __exit__(self, *exc) -> None:
        self.release()
