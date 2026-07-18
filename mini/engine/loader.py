# -*- coding: utf-8 -*-
"""ampacity-lab (mini): ModelLoader
=============================================

只管: 加载 / 卸载 / 记住当前模型 + 当前文件路径
不检测, 不求解。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..backends.base import BackendProtocol
from ..utils.events import EventBus
from ..utils.logger import get_logger

log = get_logger(__name__)


class ModelLoader:
    """模型加载 / 卸载 / 状态查询"""

    def __init__(self, backend: BackendProtocol, bus: EventBus) -> None:
        self._backend = backend
        self._bus = bus
        self._current_file: str = ""
        self._default_I: float = 0.0

    @property
    def current_file(self) -> str:
        return self._current_file

    @property
    def is_loaded(self) -> bool:
        return bool(self._current_file)

    @property
    def default_I(self) -> float:
        return self._default_I

    def load(self, file_path: str) -> bool:
        # 真实文件存在性检查 —— Mock 后端 (或假路径测试) 应该自己在 backend 层处理,
        # 这里只在文件不存在时给个 warning, 仍然让 backend 决定 (mock 永远 OK)
        if not os.path.exists(file_path):
            log.warning("文件可能不存在: %s (交给后端判断)", file_path)
        r = self._backend.model_load(file_path)
        if not r.get("success"):
            log.error("加载失败: %s", r.get("error"))
            return False
        self._current_file = file_path
        log.info("已加载 %s", os.path.basename(file_path))
        # 顺手读默认 I
        self._default_I = self._probe_default_I()
        log.info("默认电流 I=%.2f A", self._default_I)
        self._bus.emit("file_loaded", path=file_path)
        return True

    def unload(self) -> None:
        if not self._current_file:
            return
        try:
            self._backend.model_unload()
        except Exception as e:
            log.warning("unload 异常: %s", e)
        finally:
            self._current_file = ""
            self._default_I = 0.0

    def _probe_default_I(self) -> float:
        """试读默认电流; 读不到就 0"""
        r = self._backend.param_get("I", evaluate=True)
        if not r.get("success"):
            return 0.0
        try:
            return float(r.get("value", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
