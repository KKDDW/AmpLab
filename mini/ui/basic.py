# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 基础 UI 界面
=============================================

定位: 主视图层 (Main View Layer)
职责:
  1. 负责主界面框架的渲染（顶部按钮栏 + 下方业务展示区）。
  2. 维护界面级的“状态机”，严格管控不同计算阶段下按钮的禁用/启用。
  3. 作为门面 (Facade)，将底层的日志操作转发给专用的 LogWindow 组件。

设计模式:
  - 哑组件 (Dumb Component): 自身不包含任何业务逻辑，用户的点击统统转化为回调 (Callback) 抛给上层 Dispatcher。
  - 门面模式 (Facade): 对外暴露出 `append_log` 等接口，实际上内部是转交给 `self._log_win` 去处理，外部调用方无需关心日志窗口的创建细节。

历史: 此文件原本 425 行, 拆出 LogWindow 和 UI 常量后只剩 200 行左右，实现了极佳的代码内聚。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from .log_window import LogWindow
from .themes import THEMES, apply_theme, get_theme
from ..utils.logger import get_logger, RingBufferHandler

log = get_logger(__name__)


class BasicPanel(ttk.Frame):
    """基础界面面板 (4 业务按钮 + 1 日志按钮 + 业务展示区)

    作为整个程序的 GUI 骨架，挂载于最顶层的 root 窗口上。
    """

    def __init__(
            self,
            parent: tk.Misc,
            on_add_files: Optional[Callable[[], None]] = None,
            on_inspect: Optional[Callable[[], None]] = None,
            on_calc: Optional[Callable[[], None]] = None,
            on_stop: Optional[Callable[[], None]] = None,
            ring: Optional[RingBufferHandler] = None,
    ) -> None:
        super().__init__(parent)

        # 【稳健获取根窗口】
        # 无论传入的 parent 是 Frame 还是 Tk 对象，都能精准拿到最顶级的 window 实例。
        # 这是为了确保弹出的 LogWindow 能够认祖归宗，挂载在正确的父级上。
        self.root = parent if isinstance(parent, tk.Tk) else parent.winfo_toplevel()

        # 【安全降级防御】
        # 如果调用方没有注入回调函数，就赋一个 lambda: None 空函数。
        # 这样即使用户点了按钮，也只会什么都不做，而不会抛出 TypeError 导致程序崩溃。
        self.on_add_files = on_add_files or (lambda: None)
        self.on_inspect = on_inspect or (lambda: None)
        self.on_calc = on_calc or (lambda: None)
        self.on_stop = on_stop or (lambda: None)

        # 【组件复合 (Composition)】
        # 实例化独立的日志窗口管理器。由于其内部采用了懒加载机制，
        # 此处只是创建了管理器实例，并不会真的弹出一个黑框框打扰用户。
        self._log_win = LogWindow(self.root, ring=ring)

        # 【主题状态】当前主题: normal / cute
        self._theme: str = "normal"

        # 构建 UI 控件并完成整体打包定位
        self._build_ui()
        self.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # =======================================================================
    # 动态注入机制 (Late Binding)
    # =======================================================================

    def _set_callbacks(
            self,
            on_add_files: Optional[Callable[[], None]] = None,
            on_inspect: Optional[Callable[[], None]] = None,
            on_calc: Optional[Callable[[], None]] = None,
            on_stop: Optional[Callable[[], None]] = None,
    ) -> None:
        """动态注入业务回调。

        应用场景：在复杂的程序启动流中，可能需要先画出 UI 给用户看（避免启动白屏），
        等后台沉重的 Engine 和 Dispatcher 初始化完成后，再通过这个方法把灵魂（业务逻辑）注入进按钮里。
        """
        if on_add_files is not None:
            self.on_add_files = on_add_files
            self.btn_add_files.config(command=on_add_files)
        if on_inspect is not None:
            self.on_inspect = on_inspect
            self.btn_inspect.config(command=on_inspect)
        if on_calc is not None:
            self.on_calc = on_calc
            self.btn_calc.config(command=on_calc)
        if on_stop is not None:
            self.on_stop = on_stop
            self.btn_stop.config(command=on_stop)

    # =======================================================================
    # UI 布局与渲染
    # =======================================================================

    def _build_ui(self) -> None:
        """构建主面板 (按钮栏 + 业务展示区)。"""
        # 顶部按钮工具栏 (横向排列)
        bar = ttk.Frame(self)
        bar.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))

        # 4 个核心业务操作按钮，依次向左对齐
        self.btn_add_files = ttk.Button(bar, text="添加文件", command=self.on_add_files)
        self.btn_add_files.pack(side=tk.LEFT, padx=4)

        self.btn_inspect = ttk.Button(bar, text="检测模型", command=self.on_inspect)
        self.btn_inspect.pack(side=tk.LEFT, padx=4)

        self.btn_calc = ttk.Button(bar, text="开始计算", command=self.on_calc)
        self.btn_calc.pack(side=tk.LEFT, padx=4)

        # 中断按钮，危险操作，初始状态严格禁用
        self.btn_stop = ttk.Button(bar, text="中断", command=self.on_stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=4)

        # 日志按钮，放在最右侧 (符合大多数工具栏的用户习惯)。
        # 直接绑定子组件 LogWindow 的 toggle 方法，点击时控制弹窗。
        self.btn_toggle_log = ttk.Button(
            bar, text="日志", command=self._log_win.toggle, width=8,
        )
        self.btn_toggle_log.pack(side=tk.RIGHT, padx=4)

        # 主题切换按钮 (紧贴日志按钮左侧, 用于切 normal / cute 主题)
        self.btn_toggle_theme = ttk.Button(
            bar, text=THEMES["normal"]["toggle_text"],
            command=self._toggle_theme, width=14,
        )
        self.btn_toggle_theme.pack(side=tk.RIGHT, padx=4)

        # 预留的业务展示区 (后续用于嵌入表格、图表、进度条等)
        body = ttk.Frame(self)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        ttk.Label(
            body, text="(业务展示区 — Phase 3 接入)",
            foreground="gray"
        ).pack(pady=40)

    # =======================================================================
    # 公开 API (门面模式)
    # =======================================================================

    # 这三个方法保持了原本的 API 签名不变，使得外部调用方 (Dispatcher) 完全无感。
    # 内部将实际的工作直接委托 (Delegate) 给专业的 _log_win 实例。

    def _toggle_theme(self) -> None:
        """切换 normal / cute 主题 (二次元可爱风格)"""
        self._theme = "cute" if self._theme == "normal" else "normal"
        apply_theme(self.root, self._theme)
        self._update_button_text(self._theme)
        log.debug("切换主题到 %s", self._theme)

    def _update_button_text(self, theme_name: str) -> None:
        """按主题更新 6 个按钮的文字"""
        theme = get_theme(theme_name)
        text_map = theme["button_text"]
        self.btn_add_files.config(text=text_map["add_files"])
        self.btn_inspect.config(text=text_map["inspect"])
        self.btn_calc.config(text=text_map["calc"])
        self.btn_stop.config(text=text_map["stop"])
        self.btn_toggle_log.config(text=text_map["log"])
        self.btn_toggle_theme.config(text=theme["toggle_text"])

    def append_log(self, message: str, level: str = "info") -> None:
        """追加一条日志 -> 转发给独立日志组件处理。"""
        self._log_win.append(message, level)

    def clear_log(self) -> None:
        """清空日志 -> 转发给独立日志组件处理。"""
        self._log_win.clear()

    def get_log_content(self) -> str:
        """取日志内容 -> 从独立日志组件获取。"""
        return self._log_win.get_content()

    def set_buttons_state(self, state: str) -> None:
        """全局 UI 状态机

        通过集中管理状态，杜绝类似于“在检测过程中又点击了计算”这类严重的并发冲突 Bug。
        保证用户只能按照特定的流程 (加文件 -> 检测 -> 计算) 往下走。
        """
        # "init": 刚双击启动程序，COMSOL 引擎还在后台拉起，处于离线状态。
        if state == "init":
            self.btn_add_files.config(state=tk.DISABLED)
            self.btn_inspect.config(state=tk.DISABLED)
            self.btn_calc.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.DISABLED)

        # "no_file": 引擎已连接，但用户还没告诉我们要算啥。
        elif state == "no_file":
            self.btn_add_files.config(state=tk.NORMAL)
            self.btn_inspect.config(state=tk.DISABLED)
            self.btn_calc.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.DISABLED)

        # "ready": 加载了文件，但尚未进行合规性检测。
        elif state == "ready":
            self.btn_add_files.config(state=tk.NORMAL)
            self.btn_inspect.config(state=tk.NORMAL)
            self.btn_calc.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.DISABLED)

        # "inspected": 检测全部通过，一切就绪，可以随时按下计算按钮。
        elif state == "inspected":
            self.btn_add_files.config(state=tk.NORMAL)
            self.btn_inspect.config(state=tk.NORMAL)
            self.btn_calc.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)

        # "inspecting": 正在调用 COMSOL API 解析模型，防连点，且允许随时强退。
        elif state == "inspecting":
            self.btn_add_files.config(state=tk.DISABLED)
            self.btn_inspect.config(state=tk.DISABLED)
            self.btn_calc.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)

        # "computing": 正在执行繁重的多点寻优/批量计算。
        elif state == "computing":
            self.btn_add_files.config(state=tk.DISABLED)
            self.btn_inspect.config(state=tk.DISABLED)
            self.btn_calc.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)

        else:
            log.warning("UI 收到未知状态字: %s, 按钮防卫机制未触发", state)


# =======================================================================
# 本地测试模块
# =======================================================================
if __name__ == "__main__":
    from ..utils.logger import init_logging

    # 启动底层环形日志
    ring = init_logging(log_dir="logs", level=10)


    # 模拟外部 Dispatcher 的行为
    def t_add():
        log.info("用户交互: 点击 [添加文件]")


    def t_inspect():
        log.info("用户交互: 点击 [检测模型]")
        log.warning("业务模拟: 检测出模型参数设置可能存在风险")


    def t_calc():
        log.info("用户交互: 点击 [开始计算], UI 进入锁定状态...")
        panel.set_buttons_state("computing")


    def t_stop():
        log.error("用户交互: 点击 [中断], 放弃当前计算任务")
        panel.set_buttons_state("inspected")  # 恢复为计算前状态


    # 构建测试窗体
    root = tk.Tk()
    root.title("UI Basic Panel Test (mini)")
    root.geometry("900x650")

    # 实例化我们的分离式面板
    panel = BasicPanel(
        root,
        on_add_files=t_add, on_inspect=t_inspect,
        on_calc=t_calc, on_stop=t_stop,
        ring=ring,
    )

    log.info('UI 启动完成 — 日志模块已完全解耦，点右上"日志"按钮可随时唤出查看')

    # 启动 GUI 主循环
    root.mainloop()
