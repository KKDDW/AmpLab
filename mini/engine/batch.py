# -*- coding: utf-8 -*-
"""ampacity-lab (mini): BatchRunner
=============================================

定位: 批量计算任务调度器 (Task Orchestrator)。
职责: 负责展开多维嵌套循环 (文件 -> 静态分组 -> 扫描参数组合)，驱动求解器计算，收集结果。
特性:
  1. 不直接控制底层物理引擎的启停（交由 Backend 管理）。
  2. 采用共享并发锁 (ConcurrencyGate)，与环境检查 (Inspector) 等操作严格互斥，防止 COMSOL 进程崩溃。
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
    """批量运行控制类

    计算矩阵：文件列表 (Files) × 静态参数组 (Groups) × 扫描参数组合 (Combos)
    最终产出：一维的 PointResult 对象列表，供 UI 表格或 Excel 导出使用。
    """

    def __init__(self, backend: BackendProtocol, bus: EventBus,
                 loader: ModelLoader, solver: AmpacitySolver,
                 gate: ConcurrencyGate) -> None:
        self._backend = backend  # 物理引擎底层接口
        self._bus = bus  # 事件总线 (向前端 UI 实时推数据和进度)
        self._loader = loader  # 模型加载器
        self._solver = solver  # 核心的单点寻优器 (之前修改过的那套插值算法)

        # 依赖注入的并发门控。
        # 为什么注入？因为这个 gate 需要和系统里其他的模块（比如 Inspector）是同一个实例，
        # 保证同一时间只能有一个模块在占用 COMSOL 计算。
        self._gate = gate

        # 状态维护
        self.tasks: List[PointResult] = []
        self.is_running: bool = False
        self.should_stop: bool = False  # 中断标志位

    # =======================================================================
    # 公开的并发/控制接口
    # =======================================================================

    @property
    def busy(self) -> bool:
        """反映当前 COMSOL 引擎是否被占用"""
        return self._gate.busy

    def try_acquire(self) -> bool:
        """抢占门控锁。由内部或外部调用以保证互斥。"""
        return self._gate.try_acquire()

    def release(self) -> None:
        """释放门控锁。"""
        self._gate.release()

    def request_stop(self) -> None:
        """
        优雅停止机制 (Graceful Shutdown)
        置起标志位后，当前正在计算的工况会继续跑完（不强杀进程防损坏），
        但在进入下一个循环前会检测并退出。
        """
        self.should_stop = True
        log.warning("收到停止指令, 当前工况完成后终止")

    # =======================================================================
    # 主入口
    # =======================================================================

    def run(
            self,
            file_list: List[str],
            static_groups: Optional[List[Dict]] = None,
            sweep_params: Optional[Dict[str, List]] = None,
            target_T: float = 90.0,
            tolerance: float = 0.05,
            initial_I: float = 800.0,
    ) -> List[PointResult]:
        """批量运行的安全包装层，负责加锁与解锁"""

        # 获取执行权，拿不到说明别人（如 Inspector）正在用 COMSOL
        if not self._gate.try_acquire():
            log.warning("batch 已在运行, 拒绝本次")
            return []

        try:
            # 拿到锁后，执行真正的业务逻辑
            return self._run_impl(
                file_list, static_groups, sweep_params,
                target_T, tolerance, initial_I,
            )
        finally:
            # 无论成功、失败还是抛异常，务必释放锁
            self._gate.release()

    # =======================================================================
    # 核心实现层
    # =======================================================================

    def _run_impl(
            self,
            file_list: List[str],
            static_groups: Optional[List[Dict]],
            sweep_params: Optional[Dict[str, List]],
            target_T: float,
            tolerance: float,
            initial_I: float,
    ) -> List[PointResult]:

        # 1. --- 数据预处理与笛卡尔积计算 ---
        static_groups = static_groups or [{"group_name": "默认"}]
        sweep_params = sweep_params or {}
        param_names = list(sweep_params.keys())

        # 如果没有扫描参数，就当做只有 1 个空组合
        if not sweep_params:
            param_values = []
            combos = 1
        else:
            param_values = list(sweep_params.values())
            combos = 1
            for lst in param_values:
                combos *= len(lst)

        # 计算总工况数：文件数 × 分组数 × 参数组合数
        total = len(file_list) * len(static_groups) * combos

        # 2. --- 状态初始化 ---
        self.tasks = []
        self.is_running = True
        self.should_stop = False
        completed = 0
        t0 = time.time()

        log.info("批量开始: %d 文件 x %d 组 x %d combo = %d 工况",
                 len(file_list), len(static_groups), combos, total)

        # 3. --- 开始三层嵌套大循环 ---
        try:
            # 第一层：遍历文件
            for file_path in file_list:
                if self.should_stop:
                    break

                base = os.path.basename(file_path).replace(".mph", "")

                # 尝试加载模型，如果失败（比如文件损坏）
                if not self._loader.load(file_path):
                    # 把这个文件对应的所有底层工况强行塞成失败结果
                    # 这样进度条才能正确走到 100%，且用户能在结果表看到是哪个文件挂了
                    self._skip_remaining(static_groups, param_names, param_values,
                                         base, completed, total, t0)
                    completed += len(static_groups) * combos
                    self._bus.emit("progress", current=completed, total=total,
                                   elapsed=time.time() - t0)
                    continue

                # 第二层：遍历静态参数组 (例如：组A代表敷设深度1米，组B代表深度2米)
                for g in static_groups:
                    if self.should_stop:
                        break

                    gname = g.get("group_name", "默认")

                    # 批量注入静态参数到 COMSOL
                    for k, v in g.items():
                        if k == "group_name":
                            continue
                        self._backend.param_set(k, str(v))

                    # 【核心性能优化：热启动机制 (Warm Start)】
                    # 当扫描环境温度 (如 20度, 25度, 30度) 时，对应的最佳电流是相近的。
                    # 将上一个工况算出的解作为下一个工况的 `initial_I`，
                    # 能让插值算法的收敛速度呈指数级提升 (通常只需 1-2 次迭代即可收敛)。
                    last_I = initial_I

                    # 第三层：遍历扫描参数的笛卡尔积组合 (使用 itertools.product)
                    # 例如 param_values 为 [[20,30], [1.5, 2.0]]
                    # combo 每次会弹出一个组合 (20, 1.5)
                    for combo in product(*param_values):
                        if self.should_stop:
                            break

                        completed += 1

                        # 把参数名和弹出的组合值打包成字典 (e.g. {"T_amb": 20, "H_wind": 1.5})
                        env = dict(zip(param_names, combo)) if param_names else {}

                        # 注入这组动态参数
                        for k, v in env.items():
                            self._backend.param_set(k, str(v))

                        t_point = time.time()

                        # 核心呼叫：触发单点寻优器
                        # 这里传入 last_I 作为初始猜测，彻底移除了原本的 I_low / I_high 逻辑
                        res = self._solver.compute_ampacity(
                            target_T=target_T,
                            I_guess=last_I,
                            tolerance=tolerance,
                            max_iter=15,
                            task_id=completed,
                        )
                        elapsed = time.time() - t_point

                        # 打包单次工况的执行结果
                        pr = PointResult(
                            task_id=completed,
                            file_name=base,
                            group_name=gname,
                            env_params=env,
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

                        # 每算完一个点，立即广播给 UI 前端追加到数据表格中
                        self._bus.emit("result", result=pr)

                        # 【更新热启动电流】：如果收敛且算出了值，把值赋给 last_I
                        if pr.converged and pr.final_I:
                            last_I = pr.final_I

                        # 广播总进度更新进度条
                        self._bus.emit("progress", current=completed, total=total,
                                       elapsed=time.time() - t0)
        finally:
            self.is_running = False
            log.info("批量结束: 完成 %d/%d, 用时 %.1fs",
                     completed, total, time.time() - t0)

        return self.tasks

    def _skip_remaining(self, static_groups, param_names, param_values,
                        base, completed, total, t0):
        """异常补偿器：当某个模型文件损坏无法加载时，将其名下分配的所有工况填充为 failed。
        确保任务总数对齐，防止 UI 进度条卡死或漏算。
        """
        for g in static_groups:
            for combo in product(*param_values):
                completed += 1
                env = dict(zip(param_names, combo)) if param_names else {}
                pr = PointResult(
                    task_id=completed,
                    file_name=base,
                    group_name=g.get("group_name", "默认"),
                    env_params=env,
                    status="skipped",
                    error="load failed",
                    elapsed_sec=0.0
                )
                self.tasks.append(pr)
                self._bus.emit("result", result=pr)
