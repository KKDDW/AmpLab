# -*- coding: utf-8 -*-
"""ampacity-lab (mini): BatchRunner
=============================================

只管: 嵌套循环 file -> group -> combo, 调用 solver, 收集 PointResult
不启停引擎, 不检测模型, 不寻优算法。

并发: 跟 Inspector 共享一个 ConcurrencyGate (inspect 跟 batch 互斥)。
通过外部注入 gate, 本类不创建 (解耦)。
"""
from __future__ import annotations

import os
import threading
import time
from itertools import product
from typing import Any, Dict, List, Optional

from ..backends.base import BackendProtocol
from ..utils.concurrency import ConcurrencyGate
from ..utils.events import EventBus
from ..utils.logger import get_logger
from ..optimizer import MAX_CURRENT, MIN_CURRENT
from .loader import ModelLoader
from .results import PointResult
from .solver import AmpacitySolver

log = get_logger(__name__)


class BatchRunner:
    """批量运行: file x group x combo -> PointResult[]"""

    def __init__(self, backend: BackendProtocol, bus: EventBus,
                 loader: ModelLoader, solver: AmpacitySolver,
                 gate: ConcurrencyGate) -> None:
        self._backend = backend
        self._bus = bus
        self._loader = loader
        self._solver = solver
        self._gate = gate   # 跟 Inspector 共享, 互斥

        self.tasks: List[PointResult] = []
        self.is_running: bool = False
        self.should_stop: bool = False

    # ---- 公开的并发接口 ----

    @property
    def busy(self) -> bool:
        return self._gate.busy

    def try_acquire(self) -> bool:
        """抢门; 用于 Inspector 等其他想互斥 batch 的场景"""
        return self._gate.try_acquire()

    def release(self) -> None:
        self._gate.release()

    def request_stop(self) -> None:
        self.should_stop = True
        log.warning("收到停止指令, 当前工况完成后终止")

    # ---- 主入口 ----

    def run(
        self,
        file_list: List[str],
        static_groups: Optional[List[Dict]] = None,
        sweep_params: Optional[Dict[str, List]] = None,
        target_T: float = 90.0,
        tolerance: float = 0.05,
        initial_I: float = 800.0,
        method: str = "secant",
    ) -> List[PointResult]:
        if not self._gate.try_acquire():
            log.warning("batch 已在运行, 拒绝本次")
            return []
        try:
            return self._run_impl(
                file_list, static_groups, sweep_params,
                target_T, tolerance, initial_I, method
            )
        finally:
            self._gate.release()

    # ---- 实现 ----

    def _run_impl(
        self,
        file_list: List[str],
        static_groups: Optional[List[Dict]],
        sweep_params: Optional[Dict[str, List]],
        target_T: float,
        tolerance: float,
        initial_I: float,
        method: str,
    ) -> List[PointResult]:
        static_groups = static_groups or [{"group_name": "默认"}]
        sweep_params = sweep_params or {}
        param_names = list(sweep_params.keys())
        # 没传 sweep_params 时, 1 个 "无参数" combo
        if not sweep_params:
            param_values = []   # product(*[]) -> 1 个空 tuple
            combos = 1
        else:
            param_values = list(sweep_params.values())
            combos = 1
            for lst in param_values:
                combos *= len(lst)
        total = len(file_list) * len(static_groups) * combos

        self.tasks = []
        self.is_running = True
        self.should_stop = False
        completed = 0
        t0 = time.time()
        log.info("批量开始: %d 文件 x %d 组 x %d combo = %d 工况",
                 len(file_list), len(static_groups), combos, total)

        try:
            for file_path in file_list:
                if self.should_stop:
                    break
                base = os.path.basename(file_path).replace(".mph", "")

                if not self._loader.load(file_path):
                    self._skip_remaining(static_groups, param_names, param_values,
                                         base, completed, total, t0)
                    completed += len(static_groups) * combos
                    self._bus.emit("progress", current=completed, total=total,
                                   elapsed=time.time() - t0)
                    continue

                for g in static_groups:
                    if self.should_stop:
                        break
                    gname = g.get("group_name", "默认")
                    for k, v in g.items():
                        if k == "group_name":
                            continue
                        self._backend.param_set(k, str(v))

                    last_I = initial_I
                    for combo in product(*param_values):
                        if self.should_stop:
                            break
                        completed += 1
                        env = dict(zip(param_names, combo)) if param_names else {}
                        for k, v in env.items():
                            self._backend.param_set(k, str(v))

                        t_point = time.time()
                        res = self._solver.compute_ampacity(
                            target_T=target_T,
                            I_guess=last_I,
                            tolerance=tolerance,
                            max_iter=15,
                            task_id=completed,
                        )
                        elapsed = time.time() - t_point

                        pr = PointResult(
                            task_id=completed, file_name=base,
                            group_name=gname, env_params=env,
                            final_I=res.get("final_I"),
                            final_T=res.get("final_T"),
                            converged=res.get("converged", False),
                            iterations=res.get("iterations", 0),
                            solve_count=res.get("solve_count", 0),
                            history=res.get("history", []),
                            error=res.get("error", ""),
                            elapsed_sec=elapsed,
                            status="success" if res.get("success") else "failed",
                        )
                        self.tasks.append(pr)
                        self._bus.emit("result", result=pr)
                        if pr.converged and pr.final_I:
                            last_I = pr.final_I
                        self._bus.emit("progress", current=completed, total=total,
                                       elapsed=time.time() - t0)
        finally:
            self.is_running = False
            log.info("批量结束: 完成 %d/%d, 用时 %.1fs",
                     completed, total, time.time() - t0)

        return self.tasks

    def _skip_remaining(self, static_groups, param_names, param_values,
                        base, completed, total, t0):
        for g in static_groups:
            for combo in product(*param_values):
                completed += 1
                env = dict(zip(param_names, combo)) if param_names else {}
                pr = PointResult(
                    task_id=completed, file_name=base,
                    group_name=g.get("group_name", "默认"),
                    env_params=env, status="skipped",
                    error="load failed", elapsed_sec=0.0)
                self.tasks.append(pr)
                self._bus.emit("result", result=pr)
