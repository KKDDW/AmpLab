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
from typing import Callable, Optional, Any, List

from .log_window import LogWindow
from .file_list_panel import FileListPanel
from .settings_panel import SettingsPanel
from .result_table_panel import ResultTablePanel
from .themes import THEMES, apply_theme, get_theme
from .constants import (
    BUTTON_WIDTH_STANDARD, BUTTON_WIDTH_NARROW, BUTTON_WIDTH_WIDE,
    BUTTON_PADDING_X
)
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
            config: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)

        # 【稳健获取根窗口】
        # 无论传入的 parent 是 Frame 还是 Tk 对象，都能精准拿到最顶级的 window 实例。
        self.root = parent if isinstance(parent, tk.Tk) else parent.winfo_toplevel()

        # 【配置管理器】
        self.config = config

        # 【安全降级防御】
        self.on_add_files = on_add_files or (lambda: None)
        self.on_inspect = on_inspect or (lambda: None)
        self.on_calc = on_calc or (lambda: None)
        self.on_stop = on_stop or (lambda: None)

        # 【清空文件列表回调】（后续由 dispatcher 注入）
        self._on_clear_files: Optional[Callable[[], None]] = None


        # 【组件复合 (Composition)】
        self._log_win = LogWindow(self.root, ring=ring)

        # 帮助窗口引用（保证只有一个）
        self._help_window: Optional[tk.Toplevel] = None


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

        # 4 个核心业务操作按钮
        self.btn_add_files = ttk.Button(
            bar, text="添加文件", command=self.on_add_files,
            width=BUTTON_WIDTH_STANDARD
        )
        self.btn_add_files.pack(side=tk.LEFT, padx=BUTTON_PADDING_X)

        self.btn_inspect = ttk.Button(
            bar, text="检测模型", command=self.on_inspect,
            width=BUTTON_WIDTH_STANDARD
        )
        self.btn_inspect.pack(side=tk.LEFT, padx=BUTTON_PADDING_X)

        self.btn_calc = ttk.Button(
            bar, text="开始计算", command=self.on_calc,
            width=BUTTON_WIDTH_STANDARD
        )
        self.btn_calc.pack(side=tk.LEFT, padx=BUTTON_PADDING_X)

        # 中断按钮
        self.btn_stop = ttk.Button(
            bar, text="中断", command=self.on_stop,
            width=BUTTON_WIDTH_STANDARD, state=tk.DISABLED
        )
        self.btn_stop.pack(side=tk.LEFT, padx=BUTTON_PADDING_X)

        # 状态标签
        self.lbl_status = ttk.Label(
            bar, text="状态: 空闲中",
            font=("", 10, "bold"),
            foreground="gray"
        )
        self.lbl_status.pack(side=tk.LEFT, padx=(20, BUTTON_PADDING_X))

        # 日志按钮
        self.btn_toggle_log = ttk.Button(
            bar, text="日志", command=self._log_win.toggle,
            width=BUTTON_WIDTH_NARROW
        )
        self.btn_toggle_log.pack(side=tk.RIGHT, padx=BUTTON_PADDING_X)

        # 帮助按钮
        self.btn_help = ttk.Button(
            bar, text="帮助", command=self._show_help,
            width=BUTTON_WIDTH_NARROW
        )
        self.btn_help.pack(side=tk.RIGHT, padx=BUTTON_PADDING_X)

        # 主题切换按钮
        self.btn_toggle_theme = ttk.Button(
            bar, text=THEMES["normal"]["toggle_text"],
            command=self._toggle_theme, width=BUTTON_WIDTH_WIDE
        )
        self.btn_toggle_theme.pack(side=tk.RIGHT, padx=BUTTON_PADDING_X)

        # 主体业务展示区 (上下分: 上半 左文件+设置 / 右扫描; 下半 结果)
        body = ttk.Frame(self)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # === 上半 (左: 文件+设置; 右: 扫描) ===
        top_section = ttk.Frame(body)
        top_section.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 4))
        top_section.grid_columnconfigure(0, weight=1)  # 左
        top_section.grid_columnconfigure(1, weight=1)  # 右
        top_section.grid_rowconfigure(0, weight=1)

        # 左侧 (文件列表 + 设置)
        top_left = ttk.Frame(top_section)
        top_left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        self.file_list_panel = FileListPanel(
            top_left,
            on_add_files=self.on_add_files,
            on_clear_files=lambda: self._on_clear_files() if self._on_clear_files else None
        )
        self.file_list_panel.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.settings_panel = SettingsPanel(
            top_left,
            config=self.config,
            on_change=lambda k, v: None
        )
        self.settings_panel.pack(fill=tk.X, expand=False)

        # 右侧 (参数组扫描 + 独立参数扫描 - 都在 SettingsPanel 末尾)
        # 用一个空 frame 占位让 SettingsPanel 在右侧撑开
        top_right = ttk.Frame(top_section)
        top_right.grid(row=0, column=1, sticky="nsew")
        # 实际 scan 块已经在 SettingsPanel 末尾, 这里留个空 frame
        ttk.Label(top_right, text="(参数扫描区见左侧设置面板底部)",
                  foreground="gray").pack(pady=20)

        # === 下半 (结果表格) ===
        bottom_section = ttk.Frame(body)
        bottom_section.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.result_table_panel = ResultTablePanel(bottom_section)
        self.result_table_panel.pack(fill=tk.BOTH, expand=True)

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

    def _show_help(self) -> None:
        """显示帮助窗口（单例模式 + 居中显示）"""
        if self._help_window is not None and self._help_window.winfo_exists():
            self._help_window.lift()
            self._help_window.focus_force()
            return

        self._help_window = tk.Toplevel(self.root)
        self._help_window.title("帮助文档")
        self._help_window.geometry("700x600")
        self._help_window.resizable(True, True)

        help_text = """
AmpLab mini - 电缆载流能力计算工具
===========================================

【核心功能】

1. 添加文件
   • 点击"添加文件"按钮，选择一个或多个 .mph 模型文件
   • 文件列表显示在左侧，支持多选、右键删除、Delete 键删除
   • 点击"清空列表"可一键移除所有文件

2. 检测模型
   • 添加文件后，点击"检测模型"按钮
   • 系统会自动解析模型中的参数、研究节点等信息
   • 检测完成后，研究节点下拉框会自动更新为实际节点名称

3. 开始计算
   • 检测完成后，"开始计算"按钮变为可用状态
   • 可在"基础设置"中调整计算参数
   • 点击"开始计算"后，状态标签显示"计算中"
   • 计算结果实时显示在右侧结果表格中

4. 中断
   • 在检测或计算过程中，可点击"中断"按钮停止任务

5. 日志
   • 点击"日志"按钮可展开/收起日志窗口

6. 帮助
   • 点击"帮助"按钮即可查看本文档

7. 主题切换
   • 点击"切换主题"按钮可在正常模式和可爱模式之间切换

【状态说明】

• 空闲中 (灰色)：等待用户操作
• 启动中 (蓝色)：COMSOL 引擎正在启动
• 检测中 (蓝色)：正在检测模型结构
• 计算中 (橙色)：正在执行载流能力计算

【操作流程】

1. 启动程序 → 等待引擎就绪
2. 点击"添加文件" → 选择 .mph 文件
3. 点击"检测模型" → 等待检测完成
4. 调整"基础设置"中的参数（可选）
5. 点击"开始计算" → 查看结果
        """

        text_frame = ttk.Frame(self._help_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_widget = tk.Text(text_frame, wrap=tk.WORD, font=("", 10), padx=10, pady=10)
        scrollbar = ttk.Scrollbar(text_frame, command=text_widget.yview)
        text_widget.config(yscrollcommand=scrollbar.set)

        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget.insert("1.0", help_text)
        text_widget.config(state=tk.DISABLED)

        btn_close = ttk.Button(self._help_window, text="关闭", command=self._help_window.destroy)
        btn_close.pack(side=tk.BOTTOM, pady=10)

        self._help_window.update_idletasks()
        window_width = self._help_window.winfo_width()
        window_height = self._help_window.winfo_height()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self._help_window.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self._help_window.protocol("WM_DELETE_WINDOW", self._help_window.destroy)

    def update_study_nodes(self, nodes: List) -> None:
        """更新研究节点选项（供 dispatcher 调用）"""
        self.settings_panel.update_study_nodes(nodes)

    def refresh_file_list(self, file_list: List[str]) -> None:
        """刷新文件列表（供 dispatcher 调用）"""
        self.file_list_panel.refresh(file_list)

    def append_result(self, result: dict) -> None:
        """添加计算结果（供 dispatcher 调用）"""
        self.result_table_panel.append_result(result)

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
