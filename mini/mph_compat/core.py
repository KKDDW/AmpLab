# -*- coding: utf-8 -*-
"""ampacity-lab (mini): mph_compat.core
=============================================

从 comsol_ampacity_mcp 搬过来后, 把我们用到的几个核心函数重新暴露在一处,
不依赖 server.py 顶层 (server.py 顶层 import FastMCP, 我们不跑 MCP server)。

不依赖 FastMCP, 不 import server.py, 只用:
  - .backends.mph_backend  (核心)
  - .tools.results         (派生值创建)

导出:
  - mph_start / mph_disconnect / model_load / model_inspect / etc
  - solve_study           (server._solve_study_by_tag 的等价实现)
  - create_max_operator   (tools.results.results_create_max_operator)
  - create_average_operator
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .backends import mph_backend
from .tools import results as results_tools

# ---- 生命周期 ----

def mph_start(cores: Optional[int] = None,
              version: Optional[str] = None) -> Dict[str, Any]:
    return mph_backend.mph_start(cores=cores, version=version)


def mph_disconnect(*args, **kwargs) -> Dict[str, Any]:
    """断开。接任意参数都忽略, 防止调用方传错崩。"""
    return mph_backend.mph_disconnect()


def mph_status(*args, **kwargs) -> Dict[str, Any]:
    try:
        return mph_backend.mph_status()
    except Exception as e:
        return {"available": False, "connected": False, "error": str(e)}


# ---- 模型 ----

def model_load(file_path: str) -> Dict[str, Any]:
    return mph_backend.model_load(file_path)


def model_inspect(*args, **kwargs) -> Dict[str, Any]:
    return mph_backend.model_inspect()


def model_unload(*args, **kwargs) -> Dict[str, Any]:
    return mph_backend.mph_disconnect()


# ---- 参数 ----

def param_set(name: str, value: str) -> Dict[str, Any]:
    return mph_backend.param_set(name, value)


def param_get(name: str, evaluate: bool = True) -> Dict[str, Any]:
    return mph_backend.param_get(name, evaluate=evaluate)


# ---- 求值 ----

def evaluate(expression: str, unit: Optional[str] = None,
            dataset: Optional[str] = None) -> Dict[str, Any]:
    return mph_backend.results_evaluate(expression, unit=unit, dataset=dataset)


# ---- 求解 (避开 server._solve_study_by_tag, 直接实现) ----

def solve_study(study_label: str = "研究 1") -> Dict[str, Any]:
    """求解当前模型的研究。

    实现等价于 comsol_ampacity_mcp.server._solve_study_by_tag:
    用 Java study 对象的 run() 直接跑, 避免 mph.solve() 找不到中文 label 的问题。
    """
    try:
        sess = mph_backend.session
        model_name = getattr(sess, "current_model", None)
        if not model_name:
            return {"success": False, "error": "No current model"}
        m = sess.get_model(model_name)
        if m is None:
            return {"success": False, "error": "Model not found"}
        # 找第一个 study tag, 直接 run (label 是中文也能跑, 因为用 tag)
        try:
            tags = list(m.java.study().tags())
        except Exception as e:
            return {"success": False, "error": f"read study tags: {e}"}
        if not tags:
            return {"success": False, "error": "No study found in model"}
        tag = tags[0]
        m.java.study(tag).run()
        return {"success": True, "study": tag}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ---- 派生值 (max / average operator) ----
#
# mcp 的 results_create_max_operator 建的是 "空白的 coupling operator",
# 调用形式是 MaxT(some_expr), 而不是 max(T, 1) 这种内联表达式.
# 我们不用这套 API —— 直接 evaluate("max(T, 1)") 更直观,
# 而且 mph 库自带 evaluate 缓存, 重复求值很快.
#
# 这里保留接口签名, 但默认走 fallthrough (不真建, 让 caller 用原表达式).

def create_max_operator(operator_name: str = "MaxT",
                        entity_dimension: int = 3) -> Dict[str, Any]:
    """接口保留 —— 但实际不建 coupling operator, 返回 success 让 caller 走原表达式.

    如果未来你想真用 coupling operator, 把下面那行注释去掉即可.
    """
    # 真要建耦合算子, 用这种调用 (但要再调 evaluate("MaxT(some_expr)"...)):
    # try:
    #     r = results_tools.results_create_max_operator(
    #         operator_name=operator_name,
    #         entity_dimension=entity_dimension,
    #     )
    #     if r.get("success"):
    #         return {"success": True, "operator_name": operator_name}
    #     return {"success": False, "error": r.get("error", "unknown")}
    # except Exception as e:
    #     return {"success": False, "error": str(e)}
    return {"success": True, "operator_name": "", "noop": True}


def create_average_operator(operator_name: str = "AvgT",
                            entity_dimension: int = 3) -> Dict[str, Any]:
    return {"success": True, "operator_name": "", "noop": True}


# ---- 状态查询 ----

def is_available() -> bool:
    """mph 后端 (即 mph Python 包) 是否可用"""
    return mph_backend.is_available()
