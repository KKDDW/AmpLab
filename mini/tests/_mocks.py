# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 测试用 mock
=============================================

放测试用的假后端 (MockBackend), 真代码 (mini/backends/) 不再引用.

跟 mini/backends/base.py 的关系:
  - 这里定义 MockBackend, 实现 mini.backends.base.BackendProtocol 接口
  - tests/ 下的 conftest.py / test_inspector.py 都从这里 import

跟真代码的关系:
  - 真生产代码 (engine_core / bootstrap) 只用 MphCompatBackend
  - MockBackend 只在 tests/ 里被引用
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional

from ..utils.logger import get_logger
from ..backends.base import BackendProtocol

log = get_logger(__name__)


class MockBackend:
    """完全离线的假后端, 跑得快, 给测试用.

    模拟行为:
      - 模型加载 "成功" (返回假元数据)
      - 求解: 立刻返回 success (50ms 模拟延迟)
      - 求值: 用 I -> T 的简单解析式 (默认 T = 25 + 0.05*I + 1e-5*I^2)
    """

    def __init__(
            self,
            evaluate_fn: Optional[Callable[[float], float]] = None,
            models: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        # 默认 I -> T 的关系: T = 25 + 0.05*I + 0.00001*I^2
        # 在 I=1300 时 T ≈ 25 + 65 + 16.9 = 106.9
        self._evaluate_fn = evaluate_fn or self._default_eval
        # 假元数据
        self._models = models or [
            {
                "name": "demo",
                "file": "demo.mph",
                "comsol_version": "6.4",
                "parameters": ["I", "T_amb", "sigma"],
                "studies": ["研究 1", "研究 2"],
                "evaluations": ["max(T, 1)"],
                "materials": ["Copper", "Insulation"],
                "physics": ["Heat", "Current"],
            }
        ]
        self._loaded_model: Optional[Dict[str, Any]] = None
        self._param_values: Dict[str, float] = {"I": 0.0, "T_amb": 25.0, "sigma": 5.7e7}
        self._connected: bool = True
        self._solve_count: int = 0
        self._evaluations: Dict[str, str] = {}   # mock: 假装建好的派生值 label -> expr
        log.info("MockBackend 就绪 (离线模式)")

    @staticmethod
    def _default_eval(I: float) -> float:
        return 25.0 + 0.05 * I + 1e-5 * I * I

    # ---- 生命周期 ----

    def mph_start(self, cores: Optional[int] = None,
                  version: Optional[str] = None) -> Dict[str, Any]:
        self._connected = True
        return {"success": True, "version": "mock-1.0", "cores": cores or 4}

    def mph_disconnect(self) -> Dict[str, Any]:
        self._connected = False
        return {"success": True}

    def status(self) -> Dict[str, Any]:
        return {
            "available": True,
            "connected": self._connected,
            "version": "mock-1.0",
            "cores": 4,
            "current_model": self._loaded_model["name"] if self._loaded_model else None,
        }

    # ---- 模型 ----

    def model_load(self, file_path: str) -> Dict[str, Any]:
        # Mock: 假装任何路径都加载成功 (mock 的本意就是无真文件)
        m = self._models[0].copy()
        m["file"] = file_path
        self._loaded_model = m
        self._param_values["I"] = 0.0
        self._solve_count = 0
        return {"success": True, "model": {"name": m["name"], "file": file_path}}

    def model_inspect(self) -> Dict[str, Any]:
        if self._loaded_model is None:
            return {"success": False, "error": "no model loaded"}
        return {
            "success": True,
            "model": dict(self._loaded_model),  # 浅拷贝防外部改
        }

    def model_unload(self) -> Dict[str, Any]:
        self._loaded_model = None
        return {"success": True}

    # ---- 参数 ----

    def param_set(self, name: str, value: str) -> Dict[str, Any]:
        try:
            self._param_values[name] = float(value)
        except ValueError:
            self._param_values[name] = 0.0
        return {"success": True, "parameter": name, "value": value}

    def param_get(self, name: str, evaluate: bool = True) -> Dict[str, Any]:
        if name not in self._param_values:
            return {"success": False, "error": f"unknown param: {name}"}
        return {
            "success": True,
            "parameter": name,
            "value": self._param_values[name],
            "evaluated": evaluate,
        }

    # ---- 求解 + 求值 ----

    def solve_study(self, study_label: str) -> Dict[str, Any]:
        self._solve_count += 1
        # 模拟 50-150ms 延迟
        import time
        time.sleep(0.05)
        return {"success": True, "study": study_label, "solve_count": self._solve_count}

    def evaluate(self, expression: str, unit: Optional[str] = None) -> Dict[str, Any]:
        I = self._param_values.get("I", 0.0)
        try:
            if "max(T" in expression or "T" in expression:
                T = self._evaluate_fn(I)
            else:
                T = 0.0
        except Exception as e:
            return {"success": False, "error": str(e)}
        return {"success": True, "value": T, "unit": unit or "K"}

    # ---- 派生值 (mock 不真建, 假装成功) ----

    def create_max_operator(self, expression: str, label: str = "MaxOp") -> Dict[str, Any]:
        self._evaluations[label] = expression
        return {"success": True, "label": label, "expression": expression}

    def create_average_operator(self, expression: str, label: str = "AvgOp") -> Dict[str, Any]:
        self._evaluations[label] = expression
        return {"success": True, "label": label, "expression": expression}
