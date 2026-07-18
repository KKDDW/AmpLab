# -*- coding: utf-8 -*-
"""ampacity-lab (mini): AmpacitySolver
=============================================

只管: 给定 (I_low, I_high, target_T) -> 找最优 I
内部用 optimizer (secant / bisection / hybrid) + 真实 solve_func (I -> T)

求解函数 solve_func 是注入式: 默认从 backend 算, 也可传入 (代理模型 / 缓存)

提速: 如果 inspector 已经建好了派生值 (cached_label), solver 会优先 evaluate
这个 label 而不是原表达式, 速度能快 5-10x。
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from ..backends.base import BackendProtocol
from ..utils.events import EventBus
from ..utils.logger import get_logger
from ..optimizer import (
    iterative_interpolation_method,
    MAX_CURRENT,
    MIN_CURRENT,
)
from .results import PointResult

log = get_logger(__name__)


# 一个 I -> T 的纯函数签名, 允许注入
SolveFunc = Callable[[float], float]


class AmpacitySolver:
    """单点寻优"""

    def __init__(self, backend: BackendProtocol, bus: EventBus) -> None:
        self._backend = backend
        self._bus = bus
        # 寻优配置
        self.target_study: str = "研究 1"
        self.current_param_name: str = "I"
        self.temp_expression: str = "max(T, 1)"
        # target_T 单位固定为 °C; temp_unit 同步为 degC 让 COMSOL 直接返回 °C
        # (避免我们自己做 K↔°C 转换, 也避免 target 和 result 单位不一致)
        self.temp_unit: str = "degC"
        # cached 派生值 label, inspector 设进来
        self.cached_eval_label: Optional[str] = None

    def use_cached_eval(self, label: Optional[str]) -> None:
        """solver 改用 cached 派生值 (inspector 调用)"""
        self.cached_eval_label = label
        if label:
            log.info("solver 切换到 cached 派生值: %s", label)

    def _eval_expression(self) -> str:
        """优先用 cached label, 没有用原表达式"""
        if self.cached_eval_label:
            return self.cached_eval_label
        return self.temp_expression

    def solve_at_I(self, I: float) -> Optional[float]:
        """一次求解: 设 I -> solve -> evaluate, 失败返回 None"""
        try:
            r_set = self._backend.param_set(self.current_param_name, str(I))
            if not r_set.get("success"):
                log.warning("param_set 失败: %s", r_set.get("error"))
                return None
            sol = self._backend.solve_study(self.target_study)
            if not sol.get("success"):
                log.warning("solve 失败 I=%.2f: %s", I, sol.get("error"))
                return None
            ev = self._backend.evaluate(self._eval_expression(), unit=self.temp_unit)
            if not ev.get("success"):
                log.warning("evaluate 失败 I=%.2f: %s", I, ev.get("error"))
                return None
            return self._coerce_temperature(ev.get("value"))
        except Exception as e:
            log.error("solve_at_I 异常 I=%.2f: %s", I, e)
            return None

    @staticmethod
    def _coerce_temperature(value) -> Optional[float]:
        """把 evaluate 的结果收成标量温度。

        COMSOL 行为:
          - 点表达式 (e.g. T_at_point)  -> 标量 float
          - 体表达式 (e.g. max(T, 1))   -> list / ndarray (所有节点的值)
        max(T, 1) 语义本身就要全场 max, 所以 list/array 时取 max
        """
        if value is None:
            return None
        # numpy 数组
        if hasattr(value, "tolist"):
            try:
                value = value.tolist()
            except Exception:
                pass
        # list / tuple
        if isinstance(value, (list, tuple)):
            if not value:
                return None
            flat = []
            def _flatten(x):
                if isinstance(x, (list, tuple)):
                    for it in x:
                        _flatten(it)
                else:
                    flat.append(x)
            _flatten(value)
            nums = [x for x in flat if isinstance(x, (int, float))]
            if not nums:
                return None
            return float(max(nums))
        # 标量
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _auto_expand_bracket(
        self,
        target_T: float,
        I_low: float,
        I_high: float,
        max_expand: int = 5,
    ) -> Tuple[float, float]:
        """自动扩 bracket: 目标温度不在 [f(I_low), f(I_high)] 区间时,
        向外延伸 (低温方向往小, 高温方向往大), 最多 max_expand 次.

        寻优前调用, 保证 regula_falsi 拿到的 bracket 一定包住 target.
        """
        for attempt in range(max_expand):
            try:
                y_low = self.solve_at_I(I_low)
                y_high = self.solve_at_I(I_high)
            except Exception as e:
                log.warning("auto_expand 求解失败: %s", e)
                return I_low, I_high
            if y_low is None or y_high is None:
                log.warning("auto_expand 求解返 None, 停止扩展")
                return I_low, I_high

            y_min, y_max = min(y_low, y_high), max(y_low, y_high)
            if y_min <= target_T <= y_max:
                log.info("auto_expand: bracket 包住 target (attempt=%d)", attempt)
                return I_low, I_high

            # target 超出高温端, 向上扩
            if target_T > y_max:
                I_high = min(MAX_CURRENT, I_high * 1.5)
                log.info("auto_expand: target>bracket, 上扩 I_high -> %.1f", I_high)
            # target 低于低温端, 向下扩
            elif target_T < y_min:
                I_low = max(MIN_CURRENT, I_low * 0.5)
                log.info("auto_expand: target<bracket, 下扩 I_low -> %.1f", I_low)

        log.warning("auto_expand: %d 次仍未包住 target, 强行开算", max_expand)
        return I_low, I_high

    def compute_ampacity(
        self,
        target_T: float = 90.0,
        I_low: float = 500.0,
        I_high: float = 1500.0,
        tolerance: float = 0.05,
        max_iter: int = 15,
        method: str = "linear",   # 唯一支持: linear (regula falsi / 两点插值)
        task_id: int = 0,
        solver: Optional[SolveFunc] = None,
    ) -> Dict[str, Any]:
        """单点寻优。

        solver: 可选外部注入的 I->T 函数 (e.g. 代理模型 / 缓存),
                不传则用 self.solve_at_I
        """
        if solver is None:
            solver = self.solve_at_I  # type: ignore[assignment]

        log.info("寻优 task=%d: T=%.2f°C  method=%s  bracket=[%.1f, %.1f]",
                 task_id, target_T, method, I_low, I_high)

        # 自动扩 bracket: 目标温度不在 [f(I_low), f(I_high)] 区间时
        # 向外延伸, 最多 5 次 (避免无限循环)
        I_low, I_high = self._auto_expand_bracket(
            target_T, I_low, I_high, max_expand=5
        )

        def solve_func(I: float) -> float:
            t = solver(I)
            if t is None:
                raise RuntimeError(f"solve failed at I={I}A")
            log.debug("task=%d step: I=%.2f -> T=%.3f", task_id, I, t)
            self._bus.emit("step", task_id=task_id,
                           point={"x": I, "y": t, "error": abs(t - target_T)})
            return t

        t0 = time.time()
        try:
            # 只支持 linear (regula falsi / 试位法 / 线性插值法)
            if method not in ("linear", "regula_falsi", "falsi"):
                log.warning("method=%r 不支持, 强制用 linear", method)
            # 新算法只要一个初始试探电流, 取 bracket 中点
            x_guess = (I_low + I_high) / 2.0
            res = iterative_interpolation_method(
                solve_func, target_T, x_guess,
                tolerance, max_iter,
            )
        except Exception as e:
            log.error("寻优异常 task=%d: %s", task_id, e)
            return {
                "success": False, "converged": False,
                "final_I": None, "final_T": None,
                "iterations": 0, "solve_count": 0,
                "history": [], "error": str(e),
            }

        out = {
            "success": res["success"],
            "converged": res["converged"],
            "final_I": res["final_x"],
            "final_T": res["final_y"],
            "iterations": res["iterations"],
            "solve_count": len(res["history"]),
            "history": res["history"],
            "error": res["error"],
        }
        log.info("task=%d 完成: I=%s T=%s iters=%d converged=%s (%.2fs)",
                 task_id,
                 f"{out['final_I']:.2f}" if out['final_I'] is not None else "?",
                 f"{out['final_T']:.3f}" if out['final_T'] is not None else "?",
                 out["iterations"], out["converged"],
                 time.time() - t0)
        return out
