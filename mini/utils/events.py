# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 简单事件总线
=============================================

为什么需要?
  - engine 推数据 (result / progress / step) 不应该直接调 UI 的方法
  - 加新消费者 (CSV 导出 / 可视化 / 告警面板) 不应该改 dispatcher
  - 解耦: emitter 不认识 subscriber, subscriber 不关心是谁 emit 的

事件约定 (字符串):
  "result"      - 一个工况完成, payload: result: PointResult
  "progress"    - 进度更新, payload: current, total, elapsed
  "step"        - 单个 solver step, payload: task_id, point
  "engine_started"   - 引擎启动, payload: version, cores
  "engine_stopped"   - 引擎停止
  "file_loaded" - 模型加载, payload: path
  "file_inspected" - 模型检测, payload: path, result
  "exception"   - 任何模块异常, payload: name, error

线程模型:
  - emit() 线程安全 (锁)
  - 回调在 emit 所在线程同步执行
  - 回调里要更新 UI, 自己用 root.after
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List

from .logger import get_logger

log = get_logger(__name__)


class EventBus:
    """最小事件总线"""

    def __init__(self) -> None:
        self._subs: Dict[str, List[Callable[..., Any]]] = defaultdict(list)
        self._lock = threading.Lock()

    def on(self, event: str, fn: Callable[..., Any]) -> None:
        """订阅事件。重复订阅同一个 fn 不会去重, 想换用 off"""
        with self._lock:
            self._subs[event].append(fn)
        log.debug("subscribe %s -> %s", event, getattr(fn, "__name__", fn))

    def off(self, event: str, fn: Callable[..., Any]) -> None:
        with self._lock:
            try:
                self._subs[event].remove(fn)
            except ValueError:
                pass

    def emit(self, event: str, **payload: Any) -> None:
        """发事件。回调异常不会中断其他订阅者"""
        with self._lock:
            subs = list(self._subs.get(event, []))  # 拷贝, 防回调里 on/off 改 list
        for fn in subs:
            try:
                fn(**payload)
            except Exception as e:
                log.exception("event %s subscriber %s failed: %s",
                              event, getattr(fn, "__name__", fn), e)

    def clear(self, event: Optional[str] = None) -> None:
        with self._lock:
            if event is None:
                self._subs.clear()
            else:
                self._subs.pop(event, None)
