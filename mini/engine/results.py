# -*- coding: utf-8 -*-
"""ampacity-lab (mini): PointResult 数据类
=============================================
从 engine_core 拆出来, 单独放一个文件, 方便别的模块引用 (inspection.py
不想依赖 engine_core, 反过来也别让它必须知道引擎子包)
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class PointResult:
    """一个工况的寻优结果 (frozen: 防止 emit 后被改)"""
    task_id: int
    file_name: str
    group_name: str
    env_params: Dict[str, Any]
    final_I: Optional[float] = None
    final_T: Optional[float] = None
    converged: bool = False
    iterations: int = 0
    solve_count: int = 0
    history: List[Dict] = field(default_factory=list)
    error: str = ""
    elapsed_sec: float = 0.0
    status: str = "pending"  # pending / running / success / failed / skipped

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["elapsed_sec"] = round(d["elapsed_sec"], 4)
        return d
