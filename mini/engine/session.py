# -*- coding: utf-8 -*-
"""ampacity-lab (mini): SessionManager
=============================================

只管一件事: 引擎启停 + 全局状态。
不加载模型, 不求解, 不寻优。
"""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from ..backends.base import BackendProtocol
from ..utils.events import EventBus
from ..utils.logger import get_logger

log = get_logger(__name__)


class SessionManager:
    """启停 + 状态"""

    def __init__(self, backend: BackendProtocol, bus: EventBus) -> None:
        self._backend = backend
        self._bus = bus
        self._connected: bool = False
        self._version: Optional[str] = None
        self._cores: Optional[int] = None
        # 启停是重型操作, 加锁防并发 start
        self._lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def info(self) -> Dict[str, Any]:
        return {
            "connected": self._connected,
            "version": self._version,
            "cores": self._cores,
        }

    def start(self, version: str = "latest",
              cores: Optional[int] = None) -> bool:
        with self._lock:
            if self._connected:
                log.info("session 已在运行, 跳过 start")
                return True
            r = self._backend.mph_start(cores=cores,
                                        version=None if version == "latest" else version)
            if not r.get("success"):
                log.error("start 失败: %s", r.get("error"))
                return False
            self._connected = True
            self._version = r.get("version", "?")
            self._cores = r.get("cores", "?")
            log.info("session 就绪: COMSOL %s / %s 核", self._version, self._cores)
            self._bus.emit("engine_started", version=self._version, cores=self._cores)
            return True

    def stop(self) -> None:
        with self._lock:
            if not self._connected:
                return
            try:
                self._backend.mph_disconnect()
            except Exception as e:
                log.warning("disconnect 异常: %s", e)
            finally:
                self._connected = False
                self._bus.emit("engine_stopped")
                log.info("session 已断开")
