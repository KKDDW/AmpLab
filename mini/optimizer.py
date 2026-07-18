# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 纯数学优化算法层
=============================================

使用基于优选历史点的无约束插值法 (Secant-like Method).
不需要初始区间包裹目标值.

适用前提: 目标函数 f(x) 关于 x 严格单调.
"""
from __future__ import annotations

from typing import Callable, Dict, List

from .utils.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
MAX_CURRENT = 5000.0  # 单次求解的电流硬上限 (A)
MIN_CURRENT = 10.0  # 单次求解的电流硬下限 (A)
DEFAULT_TOL = 0.02  # 默认温度收敛容差 (°C)
DEFAULT_MAX_ITER = 20  # 默认最大迭代次数

# 防御性退化的温度差阈值 (°C)
# 当历史两点温度差 < 此值, 认为斜率几乎为 0, 强制电流偏移破除死锁
DEGENERATE_Y_DIFF = 1e-3


# ---------------------------------------------------------------------------
# 结果字典封装
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
# 优选插值法 (Trial & Secant)
# ---------------------------------------------------------------------------

def iterative_interpolation_method(
        func: Callable[[float], float],
        target: float,
        x_guess: float,  # 只需要提供一个初始试探电流
        tolerance: float = DEFAULT_TOL,
        max_iter: int = DEFAULT_MAX_ITER,
) -> Dict:
    """基于优选点的无约束插值法 (Secant-like Method)

    适用前提
    --------
    目标函数 f(x) 关于 x 严格单调 (本项目里: 温度随电流严格递增).

    逻辑
    ----
    1. 计算初始试探电流对应的温度.
    2. 根据温度偏大或偏小, 将电流调整 10% 进行第二次试探.
    3. 取历史记录中【温度误差最小】的两点进行线性插值 (割线法),
       推算新的电流.
    4. 循环直到满足容差或达到最大次数; 不收敛时返回历史最优解.

    Parameters
    ----------
    func : Callable[[float], float]
        输入电流 (A), 输出温度 (°C). 必须严格单调.
    target : float
        目标温度 (°C).
    x_guess : float
        初始试探电流 (A). 不需要预先包络 target.
    tolerance : float
        温度收敛容差 (°C). 默认 0.02.
    max_iter : int
        最大迭代次数. 默认 20.

    Returns
    -------
    dict
        success / converged / final_x / final_y / iterations / history / error
    """
    history: List[Dict] = []
    log.info("interpolation start: target=%.3f x_guess=%.2f tol=%.3f",
             target, x_guess, tolerance)

    def _safe_eval(x: float, label: str, fallback_x, fallback_y) -> Dict:
        """调 func, 失败时返 fail result. x/y 在失败时用 fallback (而不是 None)"""
        try:
            y = func(x)
        except Exception as e:
            log.error("%s 失败: %s", label, e)
            return _result(False, False, fallback_x, fallback_y,
                           len(history), history, str(e))
        return {"y": y}

    # ==========================================
    # 第 1 步: 初始试探
    # ==========================================
    x1 = max(MIN_CURRENT, min(MAX_CURRENT, x_guess))
    r = _safe_eval(x1, "第 1 次试探", 0.0, 0.0)
    if "y" not in r:
        return r
    y1 = r["y"]

    err1 = abs(y1 - target)
    history.append({"x": x1, "y": y1, "error": err1})
    log.debug("试探 1: 电流=%.2fA, 温度=%.3f°C, 误差=%.4f", x1, y1, err1)

    if err1 <= tolerance:
        return _result(True, True, x1, y1, 1, history)

    # ==========================================
    # 第 2 步: 根据结果改变 10% 再算一次
    # ==========================================
    # 当前温度低于目标 -> 增大电流 (+10%); 高于目标 -> 减小电流 (-10%)
    x2 = x1 * 1.10 if y1 < target else x1 * 0.90
    x2 = max(MIN_CURRENT, min(MAX_CURRENT, x2))

    r = _safe_eval(x2, "第 2 次试探", x1, y1)
    if "y" not in r:
        return r
    y2 = r["y"]

    err2 = abs(y2 - target)
    history.append({"x": x2, "y": y2, "error": err2})
    log.debug("试探 2 (+/-10%%): 电流=%.2fA, 温度=%.3f°C, 误差=%.4f", x2, y2, err2)

    if err2 <= tolerance:
        return _result(True, True, x2, y2, 2, history)

    # ==========================================
    # 第 3 步: 进入插值循环 (不限制 Bracket)
    # ==========================================
    for i in range(2, max_iter):
        # 核心逻辑: 对历史数据按误差从小到大排序
        # 列表前两项永远是【最靠近目标温度的两次试验】
        history_sorted = sorted(history, key=lambda item: item["error"])

        p1 = history_sorted[0]
        # 防止取到两个 x 极其相近的点导致除以 0, 找次优且 X 不同的点
        p2 = next(
            (p for p in history_sorted[1:] if abs(p["x"] - p1["x"]) > 1e-3),
            history_sorted[1],
        )

        xa, ya = p1["x"], p1["y"]
        xb, yb = p2["x"], p2["y"]

        # 线性插值 (割线法公式)
        if abs(ya - yb) < DEGENERATE_Y_DIFF:
            # 斜率几乎为 0 -> 强制电流偏移 1% 破除死锁
            x_new = xa * 1.01
            log.debug("温度变化极小, 强制偏移 1%% 探索: x=%.2f", x_new)
        else:
            x_new = xa - (ya - target) * (xb - xa) / (yb - ya)

        # 物理边界保护
        x_new = max(MIN_CURRENT, min(MAX_CURRENT, x_new))

        r = _safe_eval(x_new, f"第 {i + 1} 次插值", x_new, y1)
        if "y" not in r:
            return r
        y_new = r["y"]

        err_new = abs(y_new - target)
        history.append({"x": x_new, "y": y_new, "error": err_new})
        log.debug(
            "插值 iter %2d: 预测电流=%.2fA 温度=%.3f°C 误差=%.4f "
            "(基于最优历史: %.2fA 和 %.2fA)",
            i + 1, x_new, y_new, err_new, xa, xb,
        )

        if err_new <= tolerance:
            log.info("插值收敛: x=%.2f y=%.3f iters=%d", x_new, y_new, i + 1)
            return _result(True, True, x_new, y_new, i + 1, history)

    # ==========================================
    # 第 4 步: 达到最大迭代次数, 返回历史最优
    # ==========================================
    best_result = min(history, key=lambda item: item["error"])
    log.warning("达到最大迭代 %d, 最佳结果 err=%.4f", max_iter, best_result["error"])
    return _result(
        True, False, best_result["x"], best_result["y"], max_iter, history,
        f"max iter reached, best err={best_result['error']:.4f}",
    )
