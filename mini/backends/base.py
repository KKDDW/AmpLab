# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 后端抽象
=============================================

BackendProtocol 定义引擎对底层的全部依赖。任何后端 (mph / mock / remote) 只需
实现这套方法, 就能直接被 AmpacityEngine 注入使用。

设计:
  - 用 Protocol (结构化子类型) 而非 ABC, 避免强制继承
  - 所有方法返回 dict, 形如 {"success": bool, ...}, 跟 comsol_ampacity_mcp 风格一致
  - 引擎层只看 dict 的 success 字段, 不关心具体异常类型
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class BackendProtocol(Protocol):
    """引擎对底层的全部依赖。"""

    # ---- 生命周期 ----
    def mph_start(self, cores: Optional[int] = None,
                  version: Optional[str] = None) -> Dict[str, Any]: ...
    def mph_disconnect(self) -> Dict[str, Any]: ...
    def status(self) -> Dict[str, Any]: ...

    # ---- 模型 ----
    def model_load(self, file_path: str) -> Dict[str, Any]: ...
    def model_inspect(self) -> Dict[str, Any]: ...
    def model_unload(self) -> Dict[str, Any]: ...

    # ---- 参数 ----
    def param_set(self, name: str, value: str) -> Dict[str, Any]: ...
    def param_get(self, name: str, evaluate: bool = True) -> Dict[str, Any]: ...

    # ---- 求解 + 求值 ----
    def solve_study(self, study_label: str) -> Dict[str, Any]: ...
    def evaluate(self, expression: str, unit: Optional[str] = None) -> Dict[str, Any]: ...

    # ---- 派生值 (提速: 建好后 solver 可以直接 evaluate 这个 name, 不重算) ----
    def create_max_operator(self, expression: str, label: str = "MaxOp") -> Dict[str, Any]: ...
    def create_average_operator(self, expression: str, label: str = "AvgOp") -> Dict[str, Any]: ...
