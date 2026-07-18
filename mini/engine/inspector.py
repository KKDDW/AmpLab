# -*- coding: utf-8 -*-
"""ampacity-lab (mini): ModelInspector
=============================================

只管: 给定文件路径, 拿到它的检测结果, 缓存, 提供查询
不求解, 不寻优。

输出格式 (我们定义的):
    {
      "success": bool,
      "file": str,
      "parameters":  [{name, value, description}, ...],
      "studies":     [{name, tag}, ...],
      "evaluations": [{name, expression}, ...],
      "suggested_current_param": str,
      "suggested_temp_expression": str,
      "suggested_temp_unit": str,
      "suggested_cached_label": str,   # <-- 派生值建好后, 这个就是 cached 名
      "warnings": [str, ...],
      "error": str,
    }

并发: 跟 BatchRunner 共享一个 gate; inspect 跟 batch 互斥, 防止模型在
batch 中途被换掉。

优化: inspect 时自动建一个 max operator (派生值), 后续 solver 可以直接
evaluate 这个 label, 不用每次重算全场 max (省 5-10x)。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..backends.base import BackendProtocol
from ..utils.concurrency import ConcurrencyGate
from ..utils.events import EventBus
from ..utils.inspection import MultiInspection
from ..utils.logger import get_logger

log = get_logger(__name__)


class ModelInspector:
    """单文件 / 多文件检测"""

    def __init__(self, backend: BackendProtocol, bus: EventBus,
                 loader, gate: ConcurrencyGate) -> None:
        self._backend = backend
        self._bus = bus
        self._loader = loader   # 用于按需 load
        self._gate = gate       # 跟 batch 互斥

        # 单文件检测缓存: file_path -> inspect_result
        self._cache: Dict[str, Dict[str, Any]] = {}

        # 最近一次检测的扁平化结果
        self.detected_studies: List[Dict[str, str]] = []
        self.detected_parameters: List[Dict[str, Any]] = []
        self.detected_evaluations: List[Dict[str, str]] = []
        self.inspection: Dict[str, Any] = {}
        # 已创建的派生值: file_path -> label (solver 优先用这个)
        self._cached_eval: Dict[str, str] = {}

    def inspect(self, file_path: str) -> Dict[str, Any]:
        """检测单个文件, 返回统一格式 dict"""
        if not self._gate.try_acquire():
            log.warning("引擎忙, 拒绝本次 inspect")
            return {"success": False, "error": "engine busy"}
        try:
            return self._inspect_locked(file_path)
        finally:
            self._gate.release()

    def _inspect_locked(self, file_path: str) -> Dict[str, Any]:
        if file_path in self._cache:
            return self._cache[file_path]

        log.info("扫描 %s", os.path.basename(file_path))

        if self._loader.current_file != file_path:
            if not self._loader.load(file_path):
                return {"success": False, "error": "load failed", "file": file_path}

        raw = self._backend.model_inspect()
        adapted = self._adapt(raw)
        self._cache[file_path] = adapted

        self.detected_studies = adapted["studies"]
        self.detected_parameters = adapted["parameters"]
        self.detected_evaluations = adapted["evaluations"]
        self.inspection = adapted

        n_p, n_s, n_e = len(adapted["parameters"]), len(adapted["studies"]), len(adapted["evaluations"])
        log.info("扫描完成: %d 参数 / %d 研究 / %d 派生值", n_p, n_s, n_e)

        self._bus.emit("file_inspected", path=file_path, result=adapted)
        return adapted

    def _auto_create_cached_eval(self, file_path: str, expression: str) -> Optional[str]:
        """接口保留 —— 现在不真建, 留给未来用 coupling operator 优化时启用.
        返回 None 表示 solver 用原表达式 evaluate.
        """
        return None

    def get_cached_eval_label(self, file_path: str) -> Optional[str]:
        """solver 问: 这个文件有没有 cached 派生值?"""
        return self._cached_eval.get(file_path)

    def inspect_many(self, file_paths: List[str]) -> MultiInspection:
        """多文件检测, 合并成 MultiInspection"""
        inspections: Dict[str, Dict[str, Any]] = {}
        for fp in file_paths:
            r = self.inspect(fp)
            if r.get("success"):
                inspections[fp] = r
        return MultiInspection.from_inspections(inspections)

    def clear_cache(self) -> None:
        self._cache.clear()
        self._cached_eval.clear()
        self.detected_studies = []
        self.detected_parameters = []
        self.detected_evaluations = []
        self.inspection = {}

    # ---- 内部 ----

    def _adapt(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """把 backend 返回的 dict 转成我们的统一格式。
        backend.model_inspect() 形如:
            {"success": True, "model": {name, file, parameters, studies, ...}}

        mph 真实返回:
            parameters -> dict {name: value}  (mph.model.parameters() 是 dict)
            studies    -> list[str]            (mph.model.studies() 是 list)
            datasets   -> list[str]            (mph.model.datasets() 是 list, evaluations 字段不在)
            materials / physics / meshes -> 各是 list[str]
        """
        m = raw.get("model", {}) or {}

        # ---- parameters: dict {name: value} 或 list[dict] 或 list[str] ----
        raw_p = m.get("parameters") or {}
        if isinstance(raw_p, dict):
            parameters = [{"name": str(k), "value": v, "description": ""}
                          for k, v in raw_p.items()]
        elif raw_p and isinstance(raw_p[0], dict):
            parameters = [{"name": p.get("name") or p.get("parameter"),
                           "value": p.get("value"),
                           "description": p.get("description", "")}
                          for p in raw_p]
        elif raw_p:
            parameters = [{"name": str(p), "value": None, "description": ""}
                          for p in raw_p]
        else:
            parameters = []

        # ---- studies: list[str] 或 list[dict] ----
        raw_s = m.get("studies") or []
        if raw_s and isinstance(raw_s[0], dict):
            studies = [{"name": s.get("name") or s.get("label") or s.get("tag"),
                        "tag": s.get("tag") or s.get("name") or ""}
                       for s in raw_s]
        else:
            studies = [{"name": str(t), "tag": str(t)} for t in raw_s]

        # ---- evaluations: mph 没这字段, 用 datasets 顶上 ----
        raw_e = m.get("evaluations") or m.get("datasets") or []
        if raw_e and isinstance(raw_e[0], dict):
            evals = [{"name": e.get("name") or e.get("label"),
                      "expression": e.get("expression", "")}
                     for e in raw_e]
        else:
            evals = [{"name": str(e), "expression": ""} for e in raw_e]

        # 其它 section 统一是 list[str]
        def _list_of_str(field):
            v = m.get(field) or []
            if v and isinstance(v[0], dict):
                return [str(d.get("name") or d.get("label") or d.get("tag"))
                        for d in v]
            return [str(x) for x in v]

        # 推断收敛变量
        param_names = {p["name"] for p in parameters if p.get("name")}
        suggested_param = "I" if "I" in param_names else (
            sorted(param_names)[0] if param_names else "I"
        )

        return {
            "success": raw.get("success", False),
            "file": m.get("file", ""),
            "parameters": parameters,
            "studies": studies,
            "evaluations": evals,
            "materials": _list_of_str("materials"),
            "physics": _list_of_str("physics"),
            "meshes": _list_of_str("meshes"),
            "geometries": _list_of_str("geometries"),
            "suggested_current_param": suggested_param,
            "suggested_temp_expression": "max(T, 1)",
            "suggested_temp_unit": "K",
            "warnings": raw.get("warnings", []),
            "error": raw.get("error", ""),
        }
