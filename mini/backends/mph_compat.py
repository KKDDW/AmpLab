# -*- coding: utf-8 -*-
"""ampacity-lab (mini): MphCompatBackend
=============================================

后端实现: 把 mini.mph_compat.core 适配成 BackendProtocol。

为什么不用 comsol_ampacity_mcp?
  comsol_ampacity_mcp 整个目录已搬到 mini/mph_compat/, core.py 把我们用到
  的 6-7 个函数集中暴露, 不 import server.py 顶层 (那个会 import FastMCP)。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..utils.logger import get_logger
from .base import BackendProtocol

log = get_logger(__name__)


class MphCompatBackend:
    """mini.mph_compat.core 的薄适配层, 实现 BackendProtocol"""

    def __init__(self) -> None:
        self._core: Any = None
        self._available: bool = False
        self._load()

    def _load(self) -> None:
        try:
            from ..mph_compat import core
            self._core = core
            self._available = core.is_available()
            if self._available:
                log.info("MphCompatBackend 就绪 (mini.mph_compat.core)")
            else:
                log.warning("mph Python 包不可用, 后端方法调用会失败")
        except Exception as e:
            log.error("mini.mph_compat 导入失败: %s", e)
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def _check(self) -> Optional[Dict[str, Any]]:
        if not self._available:
            return {"success": False, "error": "mph backend not available"}
        if self._core is None:
            return {"success": False, "error": "core not loaded"}
        return None

    # ---- 生命周期 ----

    def mph_start(self, cores: Optional[int] = None,
                  version: Optional[str] = None) -> Dict[str, Any]:
        err = self._check()
        if err:
            return err
        try:
            return self._core.mph_start(cores=cores, version=version)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def mph_disconnect(self) -> Dict[str, Any]:
        if self._core is None:
            return {"success": True}
        try:
            return self._core.mph_disconnect()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def status(self) -> Dict[str, Any]:
        if not self._available or self._core is None:
            return {"available": False, "connected": False}
        try:
            return self._core.mph_status()
        except Exception as e:
            return {"available": True, "connected": False, "error": str(e)}

    # ---- 模型 ----

    def model_load(self, file_path: str) -> Dict[str, Any]:
        err = self._check()
        if err:
            return err
        if not os.path.exists(file_path):
            return {"success": False, "error": f"file not found: {file_path}"}
        try:
            return self._core.model_load(file_path)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def model_inspect(self) -> Dict[str, Any]:
        err = self._check()
        if err:
            return err
        try:
            return self._core.model_inspect()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def model_unload(self) -> Dict[str, Any]:
        if self._core is None:
            return {"success": True}
        try:
            return self._core.mph_disconnect()
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---- 参数 ----

    def param_set(self, name: str, value: str) -> Dict[str, Any]:
        err = self._check()
        if err:
            return err
        try:
            return self._core.param_set(name, value)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def param_get(self, name: str, evaluate: bool = True) -> Dict[str, Any]:
        err = self._check()
        if err:
            return err
        try:
            return self._core.param_get(name, evaluate=evaluate)
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---- 求解 + 求值 ----

    def solve_study(self, study_label: str) -> Dict[str, Any]:
        if self._core is None:
            return {"success": False, "error": "core not loaded"}
        try:
            return self._core.solve_study(study_label)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def evaluate(self, expression: str, unit: Optional[str] = None) -> Dict[str, Any]:
        err = self._check()
        if err:
            return err
        try:
            return self._core.evaluate(expression, unit=unit)
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---- 派生值 ----

    def create_max_operator(self, expression: str, label: str = "MaxOp") -> Dict[str, Any]:
        err = self._check()
        if err:
            return err
        try:
            return self._core.create_max_operator(expression, label=label)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_average_operator(self, expression: str, label: str = "AvgOp") -> Dict[str, Any]:
        err = self._check()
        if err:
            return err
        try:
            return self._core.create_average_operator(expression, label=label)
        except Exception as e:
            return {"success": False, "error": str(e)}
