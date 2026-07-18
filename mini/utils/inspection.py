# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 检测结果模型 (section 注册制)
=============================================

设计:
  - 把每个 section (parameters / studies / evaluations / materials / ...) 看成同构
  - SectionInfo dataclass 描述一个 section 的所有字段
  - SECTION_REGISTRY: 集中注册所有 section
  - MultiInspection.from_inspections() 遍历 registry, 通用聚合, 不再写一堆 if

加新 section (比如 "physics") 只需在 SECTION_REGISTRY 加一行。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# SectionInfo
# ---------------------------------------------------------------------------

@dataclass
class SectionInfo:
    """一个 section 在多文件下的聚合结果"""
    common: Set[str] = field(default_factory=set)
    partial: Dict[str, List[str]] = field(default_factory=dict)            # name -> owners
    per_file: Dict[str, Dict[str, Any]] = field(default_factory=dict)      # file -> name -> detail
    per_file_unique: Dict[str, Set[str]] = field(default_factory=dict)     # file -> 独有


# ---------------------------------------------------------------------------
# Section 定义
# ---------------------------------------------------------------------------

@dataclass
class SectionDef:
    """一个 section 的元信息: 名字 + 怎么从 inspect 原始数据里抽 items"""
    name: str
    extract: Any  # Callable[[inspect_dict], List[Dict[str, Any]]]
    # 每个 item 必须至少有 'name' 字段


# 内置的抽 item 函数
def _extract_parameters(ins: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = ins.get("parameters") or []
    if isinstance(raw, dict):
        return [{"name": str(k), "value": v, "description": ""}
                for k, v in raw.items()]
    if raw and isinstance(raw[0], dict):
        return [{"name": p.get("name") or p.get("parameter"),
                 "value": p.get("value"),
                 "description": p.get("description", "")}
                for p in raw]
    return [{"name": str(p), "value": None, "description": ""} for p in raw]


def _extract_studies(ins: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = ins.get("studies") or []
    if raw and isinstance(raw[0], dict):
        return [{"name": s.get("name") or s.get("label") or s.get("tag"),
                 "tag": s.get("tag") or s.get("name") or ""}
                for s in raw]
    return [{"name": str(t), "tag": str(t)} for t in raw]


def _extract_evaluations(ins: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = ins.get("evaluations") or ins.get("datasets") or []
    if raw and isinstance(raw[0], dict):
        return [{"name": e.get("name") or e.get("label"),
                 "expression": e.get("expression", "")}
                for e in raw]
    return [{"name": str(e), "expression": ""} for e in raw]


def _extract_name_list(ins: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    """通用: section 是一组字符串名 (materials, physics, meshes, ...)"""
    raw = ins.get(key) or []
    if isinstance(raw, dict):
        return [{"name": str(k)} for k in raw.keys()]
    if raw and isinstance(raw[0], dict):
        return [{"name": str(d.get("name") or d.get("label") or d.get("tag"))}
                for d in raw]
    return [{"name": str(x)} for x in raw]


# 注册表
SECTION_REGISTRY: Dict[str, SectionDef] = {
    "parameters":  SectionDef("parameters",  _extract_parameters),
    "studies":     SectionDef("studies",     _extract_studies),
    "evaluations": SectionDef("evaluations", _extract_evaluations),
    "materials":   SectionDef("materials",
                              lambda ins: _extract_name_list(ins, "materials")),
    "physics":     SectionDef("physics",
                              lambda ins: _extract_name_list(ins, "physics")),
    "meshes":      SectionDef("meshes",
                              lambda ins: _extract_name_list(ins, "meshes")),
    "geometries":  SectionDef("geometries",
                              lambda ins: _extract_name_list(ins, "geometries")),
}


def register_section(name: str, extract_fn) -> None:
    """运行时注册新 section (供插件用)"""
    SECTION_REGISTRY[name] = SectionDef(name, extract_fn)


# ---------------------------------------------------------------------------
# MultiInspection
# ---------------------------------------------------------------------------

@dataclass
class MultiInspection:
    """多文件检测的汇总结果"""
    file_count: int = 0
    file_paths: List[str] = field(default_factory=list)
    sections: Dict[str, SectionInfo] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def __getitem__(self, key: str) -> SectionInfo:
        return self.sections[key]

    def available_params(self) -> List[str]:
        """参数下拉候选 (common 在前, 其他按字母序)"""
        sec = self.sections.get("parameters")
        if not sec:
            return ["I"]
        common = sorted(sec.common)
        others: Set[str] = set(sec.partial.keys())
        for s in sec.per_file_unique.values():
            others.update(s)
        others -= sec.common
        return common + sorted(others) or ["I"]

    def section_names(self) -> List[str]:
        return list(self.sections.keys())

    @classmethod
    def from_inspections(cls, inspections: Dict[str, Dict[str, Any]]) -> "MultiInspection":
        """inspections: {file_path: inspect_dict} -> MultiInspection
        每个 inspect_dict 形如:
            {"parameters": [...], "studies": [...], "evaluations": [...], ...}
        (字段可以缺, 缺的 section 跳过)
        """
        if not inspections:
            return cls(file_count=0, file_paths=[])

        file_paths = list(inspections.keys())
        n = len(file_paths)
        warnings: List[str] = []
        for r in inspections.values():
            warnings.extend(r.get("warnings", []))

        # 遍历注册表, 聚合每个 section
        sections: Dict[str, SectionInfo] = {}
        for sec_name, sec_def in SECTION_REGISTRY.items():
            # 哪些文件有这个 section?
            per_file_sets: Dict[str, Set[str]] = {}
            per_file_detail: Dict[str, Dict[str, Any]] = {}
            for fp, raw in inspections.items():
                items = sec_def.extract(raw)
                names = {it["name"] for it in items if it.get("name")}
                if names:
                    per_file_sets[fp] = names
                per_file_detail[fp] = {it["name"]: it for it in items if it.get("name")}

            if not per_file_sets:
                continue  # 整个 section 没人有

            common = set.intersection(*per_file_sets.values()) if per_file_sets else set()

            # partial: n>2 时, 出现 2..n-1 次的名字
            partial: Dict[str, List[str]] = {}
            if n > 2:
                name_to_files: Dict[str, List[str]] = {}
                for fp, names in per_file_sets.items():
                    for nm in names:
                        name_to_files.setdefault(nm, []).append(fp)
                for nm, owners in name_to_files.items():
                    if nm in common:
                        continue
                    if 1 < len(owners) < n:
                        partial[nm] = owners

            # per_file_unique
            per_file_unique: Dict[str, Set[str]] = {}
            for fp, names in per_file_sets.items():
                if n <= 1:
                    per_file_unique[fp] = set()
                    continue
                others = set.union(*(s for f, s in per_file_sets.items() if f != fp))
                per_file_unique[fp] = names - others

            sections[sec_name] = SectionInfo(
                common=common,
                partial=partial,
                per_file=per_file_detail,
                per_file_unique=per_file_unique,
            )

        return cls(
            file_count=n,
            file_paths=file_paths,
            sections=sections,
            warnings=warnings,
        )
