# -*- coding: utf-8 -*-
"""ampacity-lab (mini): AmpacitySolver
=============================================

定位
----
业务逻辑与算法的桥梁层.

核心职责
--------
给定 (目标温度 target_T, 初始估算电流 I_guess), 找出最优电流 I,
使得在 COMSOL 模型上 evaluate 出的最高温度最接近 target_T.

不做的事
--------
- 不做 UI 渲染 (UI 在 ui_basic.py)
- 不做 COMSOL 通信 (backend 在 backends/)
- 不做寻优算法实现 (算法在 optimizer.py)

加速策略
--------
如果 inspector 已经建好了派生值 (cached_label, 比如 "max_T_cached"),
solver 会优先 evaluate 这个 label 而不是原表达式 "max(T, 1)",
速度能快 5-10x (避免每次重算 max).

调用链
------
UI 按钮 → dispatcher → AmpacitySolver.compute_ampacity()
                              ↓
                       optimizer.iterative_interpolation_method()
                              ↓
                       solve_func (内联闭包)
                              ↓
                       self.solve_at_I()  →  backend  →  COMSOL
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from ..backends.base import BackendProtocol
from ..optimizer import iterative_interpolation_method
from ..utils.events import EventBus
from ..utils.logger import get_logger
from .results import PointResult

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# 类型别名
# ---------------------------------------------------------------------------

# 一个 I -> T 的纯函数签名, 允许注入
# 默认: I -> 后端仿真 -> 温度; 也可注入代理模型 / 缓存
SolveFunc = Callable[[float], float]

# 容错: 单次寻优里允许 backend 连续失败的次数上限
# 超过则视为 backend 真正坏掉, 立刻终止寻优
MAX_CONSECUTIVE_FAILURES = 3


# ---------------------------------------------------------------------------
# 主类
# ---------------------------------------------------------------------------

class AmpacitySolver:
    """载流量单点寻优器 (Single-Point Ampacity Optimizer)

    一次寻优 = 找一对 (I, T) 使 T ≈ target_T

    典型用法
    --------
    >>> solver = AmpacitySolver(backend, bus)
    >>> result = solver.compute_ampacity(target_T=90.0, I_guess=1000.0)
    >>> if result["converged"]:
    ...     print(f"载流量 = {result['final_I']:.1f} A")
    """

    def __init__(self, backend: BackendProtocol, bus: EventBus) -> None:
        """初始化求解器

        Parameters
        ----------
        backend : BackendProtocol
            COMSOL 后端实现 (mp.client / mph / mock), 必须实现
            param_set / solve_study / evaluate 三个方法.
        bus : EventBus
            全局事件总线, 用于把寻优进度推给 UI / 日志 / 控制台.
        """
        self._backend = backend
        self._bus = bus

        # 寻优配置 (初始值, 由外部 engine.configure() 设置)
        self.target_study: str = "等待检测"
        self.current_param_name: str = "I"
        self.temp_expression: str = "max(T, 1)"

        # 强制统一温度单位为摄氏度 (°C), 不管 COMSOL 返啥
        self.temp_unit: str = "degC"
        # None = 走原表达式; 非 None = 走 inspector 建好的 cached 派生值
        self.cached_eval_label: Optional[str] = None

    # -----------------------------------------------------------------------
    # 配置接口
    # -----------------------------------------------------------------------

    def use_cached_eval(self, label: Optional[str]) -> None:
        """切换 solver 用 cached 派生值 (通常由 inspector 调用)

        Parameters
        ----------
        label : str or None
            派生值的 label (例如 "max_T_cached").
            传 None 表示退回用原表达式.
        """
        self.cached_eval_label = label
        if label:
            log.info("solver 切换到 cached 派生值: %s", label)

    def _eval_expression(self) -> str:
        """本次 evaluate 要用的表达式

        优先用 cached label (快), 没有用原表达式 (慢但通用).
        改这个不动, 因为 _eval_expression() 是给 evaluate 内部用的.
        """
        if self.cached_eval_label:
            return self.cached_eval_label
        return self.temp_expression

    # -----------------------------------------------------------------------
    # 单步求解
    # -----------------------------------------------------------------------

    def solve_at_I(self, I: float) -> Optional[float]:
        """单次仿真: 设 I -> 求解 -> evaluate -> 取温度标量

        这是优化器每次迭代都会调的"原子操作".
        COMSOL 调用全在这里, 跟寻优算法无关.

        Parameters
        ----------
        I : float
            要试的电流值 (A).

        Returns
        -------
        float or None
            成功: 该电流对应的最高温度 (°C).
            失败: None (日志会写原因, 不抛异常).
        """
        try:
            # 1. 把 I 设到 COMSOL 参数
            r_set = self._backend.param_set(self.current_param_name, str(I))
            if not r_set.get("success"):
                log.warning("param_set 失败: %s", r_set.get("error"))
                return None

            # 2. 触发 COMSOL 求解 (可能慢, 阻塞)
            sol = self._backend.solve_study(self.target_study)
            if not sol.get("success"):
                log.warning("solve 失败 I=%.2f: %s", I, sol.get("error"))
                return None

            # 3. evaluate 派生温度
            ev = self._backend.evaluate(self._eval_expression(), unit=self.temp_unit)
            if not ev.get("success"):
                log.warning("evaluate 失败 I=%.2f: %s", I, ev.get("error"))
                return None

            # 4. 把 evaluate 的结果 (可能 list / ndarray / float) 收成标量
            return self._coerce_temperature(ev.get("value"))
        except Exception as e:
            log.error("solve_at_I 异常 I=%.2f: %s", I, e)
            return None

    @staticmethod
    def _coerce_temperature(value) -> Optional[float]:
        """把 evaluate 的返值收成标量最高温度 (°C)

        COMSOL evaluate 返值类型飘忽, 这一层专门做类型适配.

        兼容
        ----
        - float / int             → 直接用
        - numpy ndarray           → .tolist() 再展平
        - list / tuple (嵌套)     → 递归展平, 取 max
        - 其它                    → 返 None

        Returns
        -------
        float or None
            标量温度; 无法解析时返 None (调用方按"失败"处理).
        """
        if value is None:
            return None

        # numpy 数组先转 list, 后面统一走展平逻辑
        if hasattr(value, "tolist"):
            try:
                value = value.tolist()
            except Exception:
                # 转换失败就当 float 强转, 实在不行返 None
                pass

        # list / tuple: 嵌套结构, 递归展平后取 max
        if isinstance(value, (list, tuple)):
            if not value:
                return None
            flat: list = []

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

        # 单值: 强转 float
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    # -----------------------------------------------------------------------
    # 主入口
    # -----------------------------------------------------------------------

    def compute_ampacity(
            self,
            target_T: float = 90.0,
            I_guess: float = 1000.0,
            tolerance: float = 0.02,
            max_iter: int = 15,
            task_id: int = 0,
            solver: Optional[SolveFunc] = None,
    ) -> Dict[str, Any]:
        """单点寻优 (使用优选插值法 iterative_interpolation_method)

        只需输入目标温度 target_T 和初始估算电流 I_guess.
        不需要预先提供包裹区间 (I_low / I_high), 算法自己会扩展.

        Parameters
        ----------
        target_T : float
            目标温度 (°C), 默认 90.
        I_guess : float
            初始试探电流 (A), 默认 1000. 这是算法的"起点",
            不要求它真的接近最优解, 算法会自己收敛.
        tolerance : float
            温度收敛容差 (°C). |T - target_T| <= tolerance 时认为收敛.
            默认 0.02.
        max_iter : int
            最大迭代次数 (指插值循环轮数, 不计前 2 次试探).
            默认 15.
        task_id : int
            任务 ID, 用于多任务并发时区分日志 / 事件.
        solver : callable, optional
            I -> T 的函数. 默认用 self.solve_at_I (真 COMSOL).
            也可注入代理模型 / 缓存用于测试 / 调试.

        Returns
        -------
        dict
            {
              "success":     bool,   # 寻优过程是否正常完成 (无异常)
              "converged":   bool,   # 是否在容差内收敛
              "final_I":     float,  # 最终电流 (A), 失败时为 None
              "final_T":     float,  # 最终温度 (°C), 失败时为 None
              "iterations":  int,    # 插值循环轮数 (不含前 2 次试探)
              "solve_count": int,    # 实际调用 backend 的总次数 = len(history)
              "history":     list,   # [{x, y, error}, ...] 每个元素是一次试探
              "error":       str,    # 错误信息; 成功时为空字符串
            }

            history 元素字段:
              - x: float  试探的电流 (A)
              - y: float  对应温度 (°C)
              - error: float  |y - target_T|, 算法按这个排最优历史点
        """
        if solver is None:
            solver = self.solve_at_I  # type: ignore[assignment]

        log.info("寻优 task=%d: 目标温度=%.2f°C  初始猜测电流=%.1fA",
                 task_id, target_T, I_guess)

        # 容错计数器: 连续失败 N 次就停 (避免 COMSOL 真坏了还硬算)
        consecutive_failures = 0

        def solve_func(I: float) -> float:
            """给 optimizer 用的单步函数: I -> T

            失败时根据容错策略决定: 偶尔失败 → 抛 (让 optimizer fallback);
            连续失败 → 抛 (optimizer 兜底) 但日志重点提示.
            """
            nonlocal consecutive_failures
            t = solver(I)
            if t is None:
                consecutive_failures += 1
                log.warning("task=%d 仿真失败 %d/%d 次 (I=%.2fA)",
                            task_id, consecutive_failures, MAX_CONSECUTIVE_FAILURES, I)
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    raise RuntimeError(
                        f"连续 {MAX_CONSECUTIVE_FAILURES} 次仿真失败, task={task_id} 终止"
                    )
                # 单次失败抛出去, 让 optimizer 用 fallback 当前 x 继续
                raise RuntimeError(f"仿真求解失败 I={I}A")
            # 成功, 重置失败计数
            consecutive_failures = 0
            log.debug("task=%d 仿真步进: 电流=%.2fA -> 温度=%.3f°C", task_id, I, t)

            # 通知前端/控制台当前进度点 (UI 可以画点)
            self._bus.emit("step", task_id=task_id,
                           point={"x": I, "y": t, "error": abs(t - target_T)})
            return t

        t0 = time.time()
        try:
            # 调用寻优算法 (传入 solve_func 作为 f(I) = T)
            res = iterative_interpolation_method(
                func=solve_func,
                target=target_T,
                x_guess=I_guess,
                tolerance=tolerance,
                max_iter=max_iter,
            )
        except Exception as e:
            log.error("寻优异常 task=%d: %s", task_id, e)
            return {
                "success": False, "converged": False,
                "final_I": None, "final_T": None,
                "iterations": 0, "solve_count": 0,
                "history": [], "error": str(e),
            }

        # 整理输出 dict: 把 optimizer 内部字段名映射到 solver 对外约定
        # (optimizer 用 final_x / final_y, solver 用 final_I / final_T, 语义更清楚)
        out = {
            "success": res["success"],
            "converged": res["converged"],
            "final_I": res["final_x"],
            "final_T": res["final_y"],
            # iterations: optimizer 的"插值循环轮数", 不算第 1 / 2 次试探
            "iterations": res["iterations"],
            # solve_count: 实际调用 backend 的总次数, 含前 2 次试探
            # (一般 solve_count = iterations + 2, 但有失败/早停时不等)
            "solve_count": len(res["history"]),
            "history": res["history"],
            "error": res["error"],
        }

        # 结果汇总日志
        log.info(
            "task=%d 寻优结束: 最终电流=%s A, 最终温度=%s °C, 迭代次数=%d, 仿真次数=%d, 收敛=%s (耗时: %.2fs)",
            task_id,
            f"{out['final_I']:.2f}" if out['final_I'] is not None else "?",
            f"{out['final_T']:.3f}" if out['final_T'] is not None else "?",
            out["iterations"], out["solve_count"], out["converged"],
            time.time() - t0,
        )

        return out
