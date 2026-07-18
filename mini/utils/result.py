# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 统一返回类型
=============================================

所有引擎方法 (start_engine / load_mph / inspect_mph / compute_ampacity / ...) 都
返回 Result 而不是裸 bool / dict / 抛异常。调用方只需:
    res = eng.start_engine()
    if not res.ok:
        log.error(res.error)
    else:
        log.info(res.data)

设计:
  - frozen dataclass, 防调用方改了它
  - .ok / .error / .data 三个属性, 直观
  - Result.ok(data=...) / Result.make_fail(error=...) 工厂方法
  - 与 dict 互转: Result.from_dict / .to_dict(), 跟 comsol_ampacity_mcp 风格兼容
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Result:
    """统一返回类型"""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    # ---- 便捷属性 ----

    @property
    def ok(self) -> bool:
        return self.success

    @property
    def value(self) -> Any:
        """data 里的第一个 value (约定俗成)"""
        if not self.data:
            return None
        if len(self.data) == 1:
            return next(iter(self.data.values()))
        return self.data

    # ---- 工厂方法 ----

    @staticmethod
    def make_ok(**data) -> "Result":
        return Result(success=True, data=dict(data), error="")

    @staticmethod
    def make_fail(error: str, **extra) -> "Result":
        return Result(success=False, data=dict(extra), error=error)

    # ---- 与 dict 互转 (兼容 comsol_ampacity_mcp 风格) ----

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Result":
        if not isinstance(d, dict):
            return Result.make_fail(f"expected dict, got {type(d).__name__}")
        # 兼容: {"success": bool, "error": str, ...} 或 {"success": True, "data": {...}}
        success = bool(d.get("success", False))
        error = str(d.get("error", ""))
        # 剩余字段都算 data
        data = {k: v for k, v in d.items()
                if k not in ("success", "error")}
        return Result(success=success, data=data, error=error)

    def to_dict(self) -> Dict[str, Any]:
        d = {"success": self.success}
        if self.error:
            d["error"] = self.error
        d.update(self.data)
        return d

    def __bool__(self) -> bool:
        return self.success

    def __repr__(self) -> str:
        if self.success:
            return f"Result.ok({self.data})"
        return f"Result.make_fail({self.error!r})"
