# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 纯数学优化算法层
=============================================

只保留 linear (regula falsi / 两点插值法).
其他算法 (secant / bisection / hybrid) 全部移除.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from .utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

MAX_CURRENT = 5000.0   # 单次求解的电流硬上限 (A)
MIN_CURRENT = 10.0     # 单次求解的电流硬下限 (A)
DEFAULT_TOL = 0.05     # 默认温度收敛容差 (°C)
DEFAULT_MAX_ITER = 20  # 默认最大迭代次数


# ---------------------------------------------------------------------------
# 温度单位转换 (保留以备后用)
# ---------------------------------------------------------------------------

def convert_temp_value(value: float, from_unit: str, to_unit: str) -> float:
    """温度单位转换: K ↔ °C

    接受多种别名 (K, k, Kelvin / degC, °C, c, celsius)
    """
    f = from_unit.strip().lower()
    t = to_unit.strip().lower()

    if f in ("degc", "c", "°c", "celsius"):
        f = "degc"
    elif f in ("k", "kelvin"):
        f = "k"

    if t in ("degc", "c", "°c", "celsius"):
        t = "degc"
    elif t in ("k", "kelvin"):
        t = "k"

    if f == t:
        return value
    if f == "k" and t == "degc":
        return value - 273.15
    if f == "degc" and t == "k":
        return value + 273.15
    log.warning("未知温度单位 %s → %s, 原值返回", from_unit, to_unit)
    return value


# ---------------------------------------------------------------------------
# 结果字典
# ---------------------------------------------------------------------------

def _result(success: bool, converged: bool, x, y, iters: int,
            history: List[Dict], error: str = "") -> Dict:
    return {
        "success": success,
        "converged": converged,
        "final_x": x,
        "final_y": y,
        "iterations": iters,
        "history": history,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Regula Falsi (试位法 / 线性插值法)
# ---------------------------------------------------------------------------
#
# 思路: 已知两个点 (x_low, f(x_low)) 和 (x_high, f(x_high)), 用线性插值
# 算 y=target 处的 x. 然后保留使 func-target 异号的那一端.
#
# 跟 secant 的区别: 保留有效 bracket, 不跑出区间
# 跟 bisection 的区别: 不取中点, 用斜率外推 (更快)
#
# 退化处理: |y_high - y_low| < 1e-6 时自动用中点, 不会崩

def regula_falsi_method(
    func: Callable[[float], float],
    target: float,
    x_low: float,
    x_high: float,
    tolerance: float = DEFAULT_TOL,
    max_iter: int = DEFAULT_MAX_ITER,
) -> Dict:
    """线性插值法 / Regula Falsi

    要求 target 在 [func(x_low), func(x_high)] 区间内.
    """
    history: List[Dict] = []
    log.info("regula_falsi start: target=%.3f bracket=[%.2f, %.2f] tol=%.3f",
             target, x_low, x_high, tolerance)

    try:
        y_low = func(x_low)
        y_high = func(x_high)
    except Exception as e:
        log.error("regula_falsi 初始求解失败: %s", e)
        return _result(False, False, None, None, 0, history,
                       f"initial solve failed: {e}")

    history.append({"x": x_low, "y": y_low, "error": abs(y_low - target)})
    history.append({"x": x_high, "y": y_high, "error": abs(y_high - target)})

    # 边界已收敛
    if abs(y_low - target) <= tolerance:
        return _result(True, True, x_low, y_low, 0, history)
    if abs(y_high - target) <= tolerance:
        return _result(True, True, x_high, y_high, 0, history)

    # 检查 target 是否在 bracket 内
    y_min, y_max = min(y_low, y_high), max(y_low, y_high)
    if not (y_min <= target <= y_max):
        log.error("target %.2f 不在 [%.2f, %.2f] 区间 (caller 需要先扩 bracket)",
                  target, y_min, y_max)
        return _result(False, False, None, None, 0, history,
                       f"target {target} outside [{y_min:.2f}, {y_max:.2f}]; "
                       f"widen bracket or auto-expand before calling")

    for i in range(max_iter):
        # 退化: 两点温度几乎一样, 走中点
        if abs(y_high - y_low) < 1e-6:
            x_new = (x_low + x_high) / 2.0
            log.debug("regula_falsi 退化, 走中点: %.2f", x_new)
        else:
            # 线性插值: 在 y=target 高度上的 x
            x_new = x_low - (y_low - target) * (x_high - x_low) / (y_high - y_low)
            # 边界保护
            if x_new < MIN_CURRENT:
                x_new = max(MIN_CURRENT, (x_low + x_high) / 2.0)
            elif x_new > MAX_CURRENT:
                x_new = min(MAX_CURRENT, (x_low + x_high) / 2.0)

        try:
            y_new = func(x_new)
        except Exception as e:
            log.error("regula_falsi 第 %d 次求解失败: %s", i + 1, e)
            return _result(False, False, x_new, None, i, history, str(e))

        err = abs(y_new - target)
        history.append({"x": x_new, "y": y_new, "error": err})
        log.debug("regula_falsi iter %2d: x=%.2f y=%.3f err=%.4f",
                  i + 1, x_new, y_new, err)

        if err <= tolerance:
            log.info("regula_falsi 收敛: x=%.2f y=%.3f iters=%d",
                     x_new, y_new, i + 1)
            return _result(True, True, x_new, y_new, i + 1, history)

        # 保留异号端
        if (y_new - target) * (y_low - target) < 0:
            x_high, y_high = x_new, y_new
        else:
            x_low, y_low = x_new, y_new

    x_final = (x_low + x_high) / 2.0
    try:
        y_final = func(x_final)
    except Exception as e:
        log.error("regula_falsi 最终求解失败: %s", e)
        return _result(False, False, x_final, None, max_iter, history, str(e))

    log.warning("regula_falsi 达到最大迭代 %d, err=%.4f",
                max_iter, abs(y_final - target))
    return _result(True, False, x_final, y_final, max_iter, history,
                   f"max iter reached, err={abs(y_final - target):.4f}")
