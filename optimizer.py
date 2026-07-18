# -*- coding: utf-8 -*-
"""ampacity-lab: 纯数学优化算法层
=============================================

纯数学与数值计算，不包含任何 mph 或 tkinter 依赖。

提供：
  1. 温度单位转换工具（K ↔ °C）
  2. 割线法（Secant Method）寻优
  3. 二分法（Bisection）作为兜底

设计原则：
  - 纯函数式，无状态
  - 输入输出明确
  - 与具体的物理求解器（COMSOL）解耦
"""
from typing import Optional, Tuple, Callable, Dict, List
import math


# ---------------------------------------------------------------------------
# 温度单位转换
# ---------------------------------------------------------------------------

def convert_temp_value(value: float, from_unit: str, to_unit: str) -> float:
    """温度单位转换

    Args:
        value: 温度值
        from_unit: 源单位 ('K' 或 'degC')
        to_unit: 目标单位 ('K' 或 'degC')

    Returns:
        转换后的温度值
    """
    from_unit = from_unit.strip().lower()
    to_unit = to_unit.strip().lower()

    # 统一单位名称
    if from_unit in ['degc', 'c', '°c', 'celsius']:
        from_unit = 'degc'
    elif from_unit in ['k', 'kelvin']:
        from_unit = 'k'

    if to_unit in ['degc', 'c', '°c', 'celsius']:
        to_unit = 'degc'
    elif to_unit in ['k', 'kelvin']:
        to_unit = 'k'

    # 转换
    if from_unit == to_unit:
        return value

    if from_unit == 'k' and to_unit == 'degc':
        return value - 273.15
    elif from_unit == 'degc' and to_unit == 'k':
        return value + 273.15
    else:
        # 未知单位，返回原值
        return value


def read_max_temp(expression: str, unit: str = 'K') -> Tuple[Optional[float], str]:
    """从表达式结果中读取最高温度（模拟，实际使用中由引擎调用 COMSOL 求值）

    这个函数在实际使用中应该由 engine 调用 COMSOL 的求值接口。
    这里只是提供接口定义。

    Args:
        expression: 温度表达式，如 'max(T, 1)'
        unit: 返回单位

    Returns:
        (温度值, 单位)
    """
    # 这是一个占位函数，实际调用由 engine_core 通过 mph 接口完成
    return None, unit


# ---------------------------------------------------------------------------
# 割线法（Secant Method）
# ---------------------------------------------------------------------------

def secant_method(
    func: Callable[[float], float],
    target: float,
    x0: float,
    x1: float,
    tolerance: float = 0.05,
    max_iter: int = 20,
) -> Dict:
    """割线法求解 func(x) = target

    使用两个初始点 (x0, x1) 进行线性外推迭代。

    Args:
        func: 目标函数 x -> y
        target: 目标值（求解 func(x) = target）
        x0: 初始点1（电流值）
        x1: 初始点2（电流值）
        tolerance: 收敛容差（温度差）
        max_iter: 最大迭代次数

    Returns:
        dict:
            success: bool
            converged: bool
            final_x: 最终 x 值（电流）
            final_y: 最终 y 值（温度）
            iterations: 迭代次数
            history: [{x, y, error}]
            error: 错误信息
    """
    history = []

    try:
        # 计算初始两点
        y0 = func(x0)
        y1 = func(x1)

        history.append({'x': x0, 'y': y0, 'error': abs(y0 - target)})
        history.append({'x': x1, 'y': y1, 'error': abs(y1 - target)})

        # 检查初始点是否已收敛
        if abs(y1 - target) <= tolerance:
            return {
                'success': True,
                'converged': True,
                'final_x': x1,
                'final_y': y1,
                'iterations': 0,
                'history': history,
                'error': ''
            }

        if abs(y0 - target) <= tolerance:
            return {
                'success': True,
                'converged': True,
                'final_x': x0,
                'final_y': y0,
                'iterations': 0,
                'history': history,
                'error': ''
            }

        # 割线法迭代
        for i in range(max_iter):
            # 检查分母是否过小（两点温度相同）
            if abs(y1 - y0) < 1e-6:
                return {
                    'success': False,
                    'converged': False,
                    'final_x': x1,
                    'final_y': y1,
                    'iterations': i,
                    'history': history,
                    'error': f'Secant denominator too small: y1={y1}, y0={y0}'
                }

            # 割线法公式：x_new = x1 - f(x1) * (x1 - x0) / (f(x1) - f(x0))
            x_new = x1 - (y1 - target) * (x1 - x0) / (y1 - y0)

            # 边界保护：电流不能为负或过大
            if x_new < 0:
                x_new = max(0.5 * x1, 10)
            if x_new > 5000:
                x_new = min(1.5 * x1, 5000)

            # 计算新点
            y_new = func(x_new)
            error = abs(y_new - target)

            history.append({'x': x_new, 'y': y_new, 'error': error})

            # 检查收敛
            if error <= tolerance:
                return {
                    'success': True,
                    'converged': True,
                    'final_x': x_new,
                    'final_y': y_new,
                    'iterations': i + 1,
                    'history': history,
                    'error': ''
                }

            # 更新迭代点
            x0, y0 = x1, y1
            x1, y1 = x_new, y_new

        # 达到最大迭代次数
        return {
            'success': True,
            'converged': False,
            'final_x': x1,
            'final_y': y1,
            'iterations': max_iter,
            'history': history,
            'error': f'Max iterations ({max_iter}) reached, error={abs(y1 - target):.4f}'
        }

    except Exception as e:
        return {
            'success': False,
            'converged': False,
            'final_x': None,
            'final_y': None,
            'iterations': len(history),
            'history': history,
            'error': f'Secant method exception: {e}'
        }


# ---------------------------------------------------------------------------
# 二分法（Bisection）
# ---------------------------------------------------------------------------

def bisection_method(
    func: Callable[[float], float],
    target: float,
    x_low: float,
    x_high: float,
    tolerance: float = 0.05,
    max_iter: int = 30,
) -> Dict:
    """二分法求解 func(x) = target

    要求 func 单调，且 target 在 [func(x_low), func(x_high)] 区间内。

    Args:
        func: 目标函数 x -> y
        target: 目标值
        x_low: 下界（电流）
        x_high: 上界（电流）
        tolerance: 收敛容差（温度差）
        max_iter: 最大迭代次数

    Returns:
        dict: 同 secant_method
    """
    history = []

    try:
        # 计算边界点
        y_low = func(x_low)
        y_high = func(x_high)

        history.append({'x': x_low, 'y': y_low, 'error': abs(y_low - target)})
        history.append({'x': x_high, 'y': y_high, 'error': abs(y_high - target)})

        # 检查 target 是否在区间内
        y_min, y_max = min(y_low, y_high), max(y_low, y_high)
        if not (y_min <= target <= y_max):
            return {
                'success': False,
                'converged': False,
                'final_x': None,
                'final_y': None,
                'iterations': 0,
                'history': history,
                'error': f'Target {target} outside bracket [{y_min:.2f}, {y_max:.2f}]'
            }

        # 检查边界是否已收敛
        if abs(y_low - target) <= tolerance:
            return {
                'success': True,
                'converged': True,
                'final_x': x_low,
                'final_y': y_low,
                'iterations': 0,
                'history': history,
                'error': ''
            }

        if abs(y_high - target) <= tolerance:
            return {
                'success': True,
                'converged': True,
                'final_x': x_high,
                'final_y': y_high,
                'iterations': 0,
                'history': history,
                'error': ''
            }

        # 二分法迭代
        for i in range(max_iter):
            # 中点
            x_mid = (x_low + x_high) / 2.0
            y_mid = func(x_mid)
            error = abs(y_mid - target)

            history.append({'x': x_mid, 'y': y_mid, 'error': error})

            # 检查收敛
            if error <= tolerance:
                return {
                    'success': True,
                    'converged': True,
                    'final_x': x_mid,
                    'final_y': y_mid,
                    'iterations': i + 1,
                    'history': history,
                    'error': ''
                }

            # 缩小区间
            if (y_mid < target and y_high > y_low) or (y_mid > target and y_high < y_low):
                # target 在 [mid, high] 区间
                x_low, y_low = x_mid, y_mid
            else:
                # target 在 [low, mid] 区间
                x_high, y_high = x_mid, y_mid

        # 达到最大迭代次数
        x_final = (x_low + x_high) / 2.0
        y_final = func(x_final)

        return {
            'success': True,
            'converged': False,
            'final_x': x_final,
            'final_y': y_final,
            'iterations': max_iter,
            'history': history,
            'error': f'Max iterations ({max_iter}) reached, error={abs(y_final - target):.4f}'
        }

    except Exception as e:
        return {
            'success': False,
            'converged': False,
            'final_x': None,
            'final_y': None,
            'iterations': len(history),
            'history': history,
            'error': f'Bisection method exception: {e}'
        }


# ---------------------------------------------------------------------------
# 混合策略（Secant + Bisection Fallback）
# ---------------------------------------------------------------------------

def hybrid_optimize(
    func: Callable[[float], float],
    target: float,
    x0: float,
    x1: float,
    tolerance: float = 0.05,
    max_iter_secant: int = 15,
    max_iter_bisect: int = 20,
) -> Dict:
    """混合优化策略：先尝试割线法，失败则回退到二分法

    Args:
        func: 目标函数
        target: 目标值
        x0, x1: 初始两点
        tolerance: 收敛容差
        max_iter_secant: 割线法最大迭代次数
        max_iter_bisect: 二分法最大迭代次数

    Returns:
        dict: 优化结果
    """
    # 先尝试割线法
    result = secant_method(func, target, x0, x1, tolerance, max_iter_secant)

    if result['converged']:
        result['method'] = 'secant'
        return result

    # 割线法未收敛，回退到二分法
    x_low, x_high = min(x0, x1), max(x0, x1)

    # 扩展区间以确保包含目标
    try:
        y_low = func(x_low)
        y_high = func(x_high)

        # 如果目标不在区间内，尝试扩展
        if target < min(y_low, y_high):
            x_low = max(10, x_low * 0.5)
        elif target > max(y_low, y_high):
            x_high = min(5000, x_high * 1.5)

    except Exception:
        pass

    bisect_result = bisection_method(func, target, x_low, x_high, tolerance, max_iter_bisect)
    bisect_result['method'] = 'bisection (fallback)'
    bisect_result['secant_failed'] = True

    # 合并历史记录
    bisect_result['history'] = result['history'] + bisect_result['history']

    return bisect_result
