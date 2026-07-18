# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 调度器 (中枢)
=============================================

依赖:
  - AppContext  (root, engine, ui, bus, config, log_dir)
  - EventBus    (事件订阅)
  - Result      (统一返回)

不直接 import engine_core / ui_basic 内部细节 —— 通过 ctx 拿。

事件订阅:
  result / engine_started / engine_stopped / file_loaded / file_inspected
    -> UI 提示 + logging

启动:
  app = AppDispatcher(ctx)
  app.start()        # 显式起, 默认会启动 COMSOL 引擎 (后台)
  ...
  app.stop()         # 显式停

加新业务按钮:
  - 在 BasicPanel 加按钮 -> 把 callback 接进 dispatcher
  - 业务逻辑用 _run_in_thread(name, fn) 工具, 统一异常 / UI 状态
"""
from __future__ import annotations

import os
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Callable, List

from .context import AppContext
from .engine.results import PointResult
from .utils.events import EventBus
from .utils.logger import Store, get_logger
from .utils.result import Result

log = get_logger(__name__)


class AppDispatcher:
    """应用调度器: 接 AppContext, 显式 start/stop"""

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.engine = ctx.engine
        self.ui = ctx.ui
        self.bus: EventBus = ctx.bus
        self.config = ctx.config
        self.root = ctx.root

        # 业务数据 (dispatcher 持有, engine 不认识)
        self.file_list: List[str] = []
        self.static_groups: List[dict] = [{"group_name": "默认组"}]
        self.sweep_params: dict = {}
        self._engine_ready: bool = False

        # 把 UI 的业务回调接进来
        self.ui._set_callbacks(
            on_add_files=self._on_add_files,
            on_inspect=self._on_inspect,
            on_calc=self._on_calc,
            on_stop=self._on_stop,
        )

        self._wire_events()
        self._load_persisted_config()

        log.info("dispatcher 就绪 (未启动引擎, 等 start)")
        # 启动时 UI 状态: 引擎没就绪, 只有"添加文件"亮
        self.root.after(0, self._refresh_ui_state)

    # ---- 生命周期 ----

    def start(self) -> None:
        """显式启动 (启动 COMSOL 引擎, 恢复 UI 状态)"""
        log.info("dispatcher.start()")
        self.ui.append_log("系统就绪 — 请添加 .mph 文件", "info")
        self.ui.append_log('提示: 默认不显示日志, 点右上"日志"按钮展开', "sys")
        self._start_engine_async()
        # 启动之后立刻报空闲 (用户没操作前就在等)
        self._log_idle("初始化")

    def stop(self) -> None:
        """显式停止 (停引擎, 关文件)"""
        log.info("dispatcher.stop()")
        try:
            res = self.engine.stop_engine()
            if not res.ok:
                log.warning("stop_engine 失败: %s", res.error)
        except Exception as e:
            log.error("stop 异常: %s", e)
        self._save_persisted_config()

    # ---- 事件订阅 ----

    def _wire_events(self) -> None:
        b = self.bus

        b.on("result", self._on_result_event)
        b.on("progress", self._on_progress_event)
        b.on("step", self._on_step_event)
        b.on("engine_started", self._on_engine_started_event)
        b.on("engine_stopped", self._on_engine_stopped_event)
        b.on("file_loaded", self._on_file_loaded_event)
        b.on("file_inspected", self._on_file_inspected_event)
        b.on("exception", self._on_exception_event)

    # ---- 事件处理 (纯函数, 易测) ----

    def _on_result_event(self, result: PointResult) -> None:
        if result.status == "success" and result.converged:
            self.ui.append_log(
                f"✓ task {result.task_id}: {result.file_name} | "
                f"{result.group_name} | I={result.final_I:.2f}A "
                f"-> T={result.final_T:.2f}°C  "
                f"({result.elapsed_sec:.1f}s)",
                "success",
            )
        elif result.status == "skipped":
            self.ui.append_log(
                f"○ task {result.task_id} skipped: {result.error}",
                "warning",
            )
        else:
            self.ui.append_log(
                f"✗ task {result.task_id} 失败: {result.error}",
                "error",
            )

    def _on_progress_event(self, current: int, total: int, elapsed: float) -> None:
        log.info("进度 %d/%d (%.0f%%)  用时 %.1fs",
                 current, total, current * 100 / max(total, 1), elapsed)

    def _on_step_event(self, task_id: int, point: dict) -> None:
        log.debug("task=%d step x=%.2f y=%.3f err=%.4f",
                  task_id, point["x"], point["y"], point["error"])

    def _on_engine_started_event(self, version, cores) -> None:
        self._engine_ready = True
        log.info("引擎启动: COMSOL %s / %s 核", version, cores)
        self.ui.append_log(f"COMSOL {version} / {cores} 核 就绪", "success")
        # 引擎就绪, 刷新 UI 状态 (init -> no_file 或 ready)
        self.root.after(0, self._refresh_ui_state)

    def _on_engine_stopped_event(self) -> None:
        self._engine_ready = False
        self.ui.append_log("COMSOL 引擎已断开", "warning")
        # 引擎挂了, 回到 init
        self.root.after(0, self._refresh_ui_state)

    def _on_file_loaded_event(self, path: str) -> None:
        log.info("模型已加载: %s", os.path.basename(path))

    def _on_file_inspected_event(self, path: str, result: dict) -> None:
        log.info("已检测: %s  (params=%d studies=%d)",
                 os.path.basename(path),
                 len(result.get("parameters", [])),
                 len(result.get("studies", [])))
        # 如果 inspector 建好了派生值, 通知 solver 切到 cached label (提速)
        cached = result.get("suggested_cached_label")
        if cached:
            self.engine._solver.use_cached_eval(cached)

    def _on_exception_event(self, name: str, error: str, traceback: str) -> None:
        self.ui.append_log(f"{name} 异常: {error}", "error")
        log.error("%s 异常: %s", name, error)

    # ---- 后台线程工具 ----

    def _run_in_thread(
        self,
        name: str,
        fn: Callable[[], Any],
        busy_state: str = "computing",  # 忙碌时的状态名 ("inspecting" / "computing" / ...)
    ) -> None:
        """统一的后台执行: 线程化 + 异常吞 + UI 按钮状态恢复 + 空闲日志

        busy_state: 线程跑起来时按钮切到的状态 (一般是 "inspecting" / "computing")
        线程结束后调 _refresh_ui_state() 自动算当前应该回到啥状态
        """
        self.root.after(0, self.ui.set_buttons_state, busy_state)
        log.info("▶ 开始执行: %s", name)

        def wrapper() -> None:
            try:
                fn()
            except Exception as e:
                log.exception("%s 异常", name)
                self.bus.emit("exception", name=name, error=str(e),
                              traceback=traceback.format_exc())
            finally:
                # 任务结束, 按当前业务状态刷新按钮
                self.root.after(0, self._refresh_ui_state)
                # 任务结束, 报空闲
                self._log_idle(name)

        threading.Thread(target=wrapper, daemon=True, name=name).start()

    def _refresh_ui_state(self) -> None:
        """根据当前业务状态算 UI 应该亮啥按钮, 然后设置

        规则:
          - 引擎没就绪: init
          - 引擎就绪 + 无文件: no_file
          - 引擎就绪 + 有文件 + 还没全检测: ready (允许再点检测)
          - 引擎就绪 + 有文件 + 全部检测完: inspected
        """
        if not self._engine_ready:
            new_state = "init"
        elif not self.file_list:
            new_state = "no_file"
        else:
            # inspector 内部 cache 里有 path, 表示"已检测过"
            cache = self.engine._inspector._cache
            all_done = all(f in cache for f in self.file_list)
            new_state = "inspected" if all_done else "ready"
        self.ui.set_buttons_state(new_state)

    def _log_idle(self, last_task: str) -> None:
        """任务结束后, 报告当前空闲状态 + 文件 / 引擎状态摘要"""
        n_files = len(self.file_list)
        n_results = len(self.engine.tasks)
        file_hint = f"{n_files} 文件" if n_files else "无文件"
        result_hint = f"{n_results} 工况" if n_results else "无结果"
        engine_hint = "已就绪" if self._engine_ready else "未就绪"
        log.info(
            "⏸ 等待用户操作 (上次任务: %s | %s | %s | 引擎 %s)",
            last_task, file_hint, result_hint, engine_hint,
        )

    # ---- UI 按钮回调 ----

    def _on_add_files(self) -> None:
        files = filedialog.askopenfilenames(
            title="选择 COMSOL 模型",
            filetypes=[("COMSOL Model", "*.mph"), ("All", "*.*")],
        )
        if not files:
            log.info("用户取消选择")
            return
        self.file_list = list(files)
        # 持久化最近目录
        if files:
            self.config.set("ui.last_open_dir", os.path.dirname(files[0]))
        log.info("添加 %d 个文件", len(self.file_list))
        for f in self.file_list:
            log.info("  - %s", os.path.basename(f))
        self.ui.append_log(f"已添加 {len(self.file_list)} 个文件", "success")
        # 文件选好了, 状态从 no_file -> ready
        self.root.after(0, self._refresh_ui_state)

    def _on_inspect(self) -> None:
        file_list = list(self.file_list)
        if not self._check_files():
            return

        def work() -> None:
            self.ui.append_log("开始检测模型...", "sys")
            for fp in file_list:
                res = self.engine.inspect_mph(fp)
                if res.ok:
                    n = len(res.data.get("parameters", []))
                    self.ui.append_log(
                        f"✓ {os.path.basename(fp)} 检测完成 ({n} 参数)",
                        "success",
                    )
                else:
                    self.ui.append_log(
                        f"✗ {os.path.basename(fp)} 失败: {res.error}",
                        "error",
                    )
            self.ui.append_log("模型检测完成", "sys")

        self._run_in_thread("inspect", work, busy_state="inspecting")

    def _on_calc(self) -> None:
        if not self._check_files():
            return
        file_list = list(self.file_list)
        static_groups = list(self.static_groups)
        sweep_params = dict(self.sweep_params)

        # 从 config 读取参数
        target_T = self.config.get("compute.target_T", 90.0)
        tolerance = self.config.get("compute.tolerance", 0.05)
        # initial_I: 优先用最近加载文件的 default_I, 没有就用 config 默认
        default_I = self.engine.default_I
        if default_I > 0:
            initial_I = default_I
        else:
            initial_I = self.config.get("compute.initial_I", 800.0)

        def work() -> None:
            self.ui.append_log("=" * 50, "sys")
            self.ui.append_log("开始批量计算", "sys")
            self.ui.append_log("=" * 50, "sys")
            res = self.engine.run_batch(
                file_list=file_list,
                static_groups=static_groups,
                sweep_params=sweep_params,
                target_T=target_T,
                tolerance=tolerance,
                initial_I=initial_I,
            )
            if res.ok:
                tasks = res.data.get("tasks", [])
                ok = sum(1 for t in tasks if t.status == "success")
                self.ui.append_log("=" * 50, "sys")
                self.ui.append_log(
                    f"批量完成: 共 {len(tasks)} 工况, "
                    f"成功 {ok}, 失败 {len(tasks) - ok}",
                    "success" if ok == len(tasks) else "warning",
                )
                self.ui.append_log("=" * 50, "sys")
            else:
                self.ui.append_log(f"批量失败: {res.error}", "error")

        self._run_in_thread("compute", work, busy_state="computing")

    def _on_stop(self) -> None:
        log.warning("用户点击中断")
        self.engine.request_stop()
        self.ui.append_log("正在停止, 当前工况完成后终止", "warning")

    # ---- 引擎启停 ----

    def _start_engine_async(self) -> None:
        self.ui.append_log("正在后台启动 COMSOL 引擎...", "sys")
        version = self.config.get("session.comsol_version", "latest")
        cores = self.config.get("session.cores", None)

        def work() -> None:
            res = self.engine.start_engine(comsol_version=version, cores=cores)
            if not res.ok:
                self.ui.append_log("COMSOL 引擎启动失败 (详见日志)", "error")

        # 引擎启动时: 切到 "init" (按钮全灰, 等 _on_engine_started_event 刷成 no_file)
        self._run_in_thread("start-engine", work, busy_state="init")

    # ---- 配置持久化 ----

    def _load_persisted_config(self) -> None:
        """从 ConfigStore 恢复 solver / 业务参数"""
        cfg = self.engine.config_snapshot()
        # 优先用持久化的, 没有就保持 solver 默认
        if "compute.target_T" in self.config.snapshot().get("compute", {}):
            self.engine.configure(
                target_study=self.config.get("solver.target_study", cfg["target_study"]),
                current_param_name=self.config.get("solver.current_param_name", cfg["current_param_name"]),
                temp_expression=self.config.get("solver.temp_expression", cfg["temp_expression"]),
                temp_unit=self.config.get("solver.temp_unit", cfg["temp_unit"]),
            )
        log.info("已从 ConfigStore 恢复参数")

    def _save_persisted_config(self) -> None:
        """退出时保存"""
        cfg = self.engine.config_snapshot()
        for k, v in cfg.items():
            self.config.set(f"solver.{k}", v)
        log.info("已保存 solver 参数到 ConfigStore")

    # ---- 业务数据 (dispatcher 持有, engine 不认识) ----
    # 注: file_list / static_groups / sweep_params 在 __init__ 里初始化

    # ---- 校验 / 清理 ----

    def _check_files(self) -> bool:
        if not self.file_list:
            messagebox.showwarning("提示", "请先添加文件")
            return False
        return True

    def cleanup(self) -> None:
        """兼容旧 API (= stop + 释放 UI 资源)"""
        self.stop()


# ---- 独立测试 ----
if __name__ == "__main__":
    from .utils.config import ConfigStore
    from .engine_core import AmpacityEngine
    from .tests._mocks import MockBackend
    from .utils.logger import init_logging
    from .ui import BasicPanel

    init_logging(log_dir="logs", level=10)
    config = ConfigStore()
    engine = AmpacityEngine(backend=MockBackend())
    bus = engine.bus

    root = tk.Tk()
    root.title("AmpLab mini - Dispatcher Test")
    root.geometry("1000x700")
    ui = BasicPanel(root, ring=Store.ring)
    ctx = AppContext(root=root, engine=engine, ui=ui, bus=bus,
                     config=config, log_dir="logs")
    app = AppDispatcher(ctx)
    app.start()
    root.protocol("WM_DELETE_WINDOW",
                  lambda: (app.cleanup(), root.destroy()))
    root.mainloop()
