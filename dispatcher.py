# -*- coding: utf-8 -*-
"""ampacity-lab: 调度器（连接引擎和 UI）
=============================================

AppDispatcher 作为中枢，负责：
  1. 实例化 AmpacityEngine（纯计算引擎）
  2. 实例化 BasicPanel（纯 UI 界面）
  3. 定义回调方法接收引擎的数据推送
  4. 将引擎的业务方法注入到 UI 的按钮回调中
  5. 确保线程安全（引擎回调 -> UI 更新使用 after）

设计原则:
  - 引擎和 UI 完全解耦，通过 dispatcher 桥接
  - 所有 UI 更新都通过 root.after 确保线程安全
  - 业务逻辑在 dispatcher 中编排
"""
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
from typing import List, Dict

from engine_core import AmpacityEngine, PointResult
from ui_basic import BasicPanel


class AppDispatcher:
    """应用调度器 - 连接引擎和 UI"""

    def __init__(self, root: tk.Tk):
        self.root = root

        # 数据状态
        self.file_list: List[str] = []
        self.static_groups: List[Dict] = [{"group_name": "默认组"}]
        self.sweep_params: Dict[str, List] = {}

        # 实例化引擎（注入回调函数）
        self.engine = AmpacityEngine(
            log_fn=self._handle_engine_log,
            progress_fn=self._handle_engine_progress,
            result_fn=self._handle_engine_result
        )

        # 实例化 UI（注入按钮回调）
        self.ui = BasicPanel(
            root,
            on_add_files=self._on_add_files,
            on_inspect=self._on_inspect,
            on_calc=self._on_calc,
            on_stop=self._on_stop
        )

        # 初始化日志
        self._safe_log("系统初始化完成", "sys")
        self._safe_log("请先添加 .mph 文件，然后检测模型", "info")

        # 启动 COMSOL 引擎（可选：延迟到用户点击时启动）
        self._start_engine_async()

    # ---- 引擎回调处理（接收引擎推送的数据）----

    def _handle_engine_log(self, msg: str, level: str):
        """处理引擎日志回调（线程安全）"""
        self._safe_log(msg, level)

    def _handle_engine_progress(self, current: int, total: int, elapsed: float):
        """处理引擎进度回调（线程安全）"""
        msg = f"进度: {current}/{total} ({current*100//total}%) - 已用时 {elapsed:.1f}秒"
        self._safe_log(msg, "info")

    def _handle_engine_result(self, result: PointResult):
        """处理引擎结果回调（线程安全）"""
        msg = (f"任务 {result.task_id}: {result.file_name} | {result.group_name} | "
               f"I={result.final_I:.2f}A, T={result.final_T:.2f}°C, "
               f"状态={result.status}")
        level = "success" if result.status == "success" else "warning"
        self._safe_log(msg, level)

    def _safe_log(self, msg: str, level: str):
        """线程安全的日志更新（通过 after 调度到主线程）"""
        self.root.after(0, self.ui.append_log, msg, level)

    # ---- UI 按钮回调（业务逻辑）----

    def _on_add_files(self):
        """添加文件按钮回调"""
        files = filedialog.askopenfilenames(
            title="选择 COMSOL 模型文件",
            filetypes=[("COMSOL Model", "*.mph"), ("All Files", "*.*")]
        )

        if files:
            self.file_list = list(files)
            self._safe_log(f"已添加 {len(self.file_list)} 个文件:", "success")
            for f in self.file_list:
                self._safe_log(f"  - {os.path.basename(f)}", "info")
        else:
            self._safe_log("未选择文件", "warning")

    def _on_inspect(self):
        """检测模型按钮回调"""
        if not self.file_list:
            messagebox.showwarning("警告", "请先添加文件")
            return

        self._safe_log("开始检测模型...", "sys")

        # 在后台线程中执行检测
        def _inspect_thread():
            try:
                for file_path in self.file_list:
                    result = self.engine.inspect_mph(file_path)
                    if result.get('success'):
                        self._safe_log(f"✓ {os.path.basename(file_path)} 检测完成", "success")
                        # 显示检测到的信息
                        params = result.get('parameters', [])
                        studies = result.get('studies', [])
                        self._safe_log(f"  参数数量: {len(params)}", "info")
                        self._safe_log(f"  研究数量: {len(studies)}", "info")
                    else:
                        self._safe_log(f"✗ {os.path.basename(file_path)} 检测失败: {result.get('error')}", "error")

                self._safe_log("模型检测完成", "sys")
            except Exception as e:
                self._safe_log(f"检测异常: {e}", "error")

        threading.Thread(target=_inspect_thread, daemon=True).start()

    def _on_calc(self):
        """开始计算按钮回调"""
        if not self.file_list:
            messagebox.showwarning("警告", "请先添加文件")
            return

        # 更新 UI 状态
        self.root.after(0, self.ui.set_buttons_state, True)
        self._safe_log("="*60, "sys")
        self._safe_log("开始批量计算...", "sys")
        self._safe_log("="*60, "sys")

        # 在后台线程中执行计算
        def _calc_thread():
            try:
                results = self.engine.run_batch(
                    file_list=self.file_list,
                    static_groups=self.static_groups,
                    sweep_params=self.sweep_params,
                    target_T=90.0,
                    tolerance=0.05,
                    initial_I=800.0,
                    method='secant'
                )

                self._safe_log("="*60, "sys")
                self._safe_log(f"批量计算完成! 共 {len(results)} 个工况", "success")
                success_count = sum(1 for r in results if r.status == 'success')
                self._safe_log(f"成功: {success_count}, 失败: {len(results) - success_count}", "info")
                self._safe_log("="*60, "sys")

            except Exception as e:
                self._safe_log(f"计算异常: {e}", "error")
            finally:
                # 恢复 UI 状态
                self.root.after(0, self.ui.set_buttons_state, False)

        threading.Thread(target=_calc_thread, daemon=True).start()

    def _on_stop(self):
        """中断按钮回调"""
        self._safe_log("正在请求停止...", "warning")
        self.engine.request_stop()

    # ---- 引擎管理 ----

    def _start_engine_async(self):
        """异步启动 COMSOL 引擎"""
        self._safe_log("正在后台启动 COMSOL 引擎...", "sys")

        def _start_thread():
            success = self.engine.start_engine(comsol_version='latest')
            if success:
                self._safe_log("COMSOL 引擎启动成功", "success")
            else:
                self._safe_log("COMSOL 引擎启动失败", "error")

        threading.Thread(target=_start_thread, daemon=True).start()

    def cleanup(self):
        """清理资源（程序退出时调用）"""
        try:
            self._safe_log("正在清理资源...", "sys")
            self.engine.stop_engine()
            self._safe_log("资源清理完成", "sys")
        except Exception as e:
            self._safe_log(f"清理异常: {e}", "error")


# ---- 独立测试 ----
if __name__ == '__main__':
    root = tk.Tk()
    root.title("Ampacity Dispatcher Test")
    root.geometry("900x700")

    app = AppDispatcher(root)

    # 窗口关闭时清理
    def on_closing():
        app.cleanup()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
