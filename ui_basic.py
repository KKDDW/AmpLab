# -*- coding: utf-8 -*-
"""ampacity-lab: 基础 UI 界面（纯净版 - 不认识引擎）
=============================================

最基础的 UI 展示层，只负责界面元素的创建和布局。
不允许 import engine_core，所有业务逻辑通过外部传入的回调函数处理。

设计原则:
  1. 只创建 UI 元素，不包含任何业务逻辑
  2. 通过构造函数接收外部回调函数
  3. 按钮点击直接调用传入的回调函数
  4. 提供公开方法供外部更新 UI 状态
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Callable, Optional


class BasicPanel(ttk.Frame):
    """基础界面面板

    构造参数:
        parent: 父窗口
        on_add_files: 添加文件回调 () -> None
        on_inspect: 检测模型回调 () -> None
        on_calc: 开始计算回调 () -> None
        on_stop: 中断计算回调 () -> None
    """

    def __init__(
        self,
        parent,
        on_add_files: Optional[Callable[[], None]] = None,
        on_inspect: Optional[Callable[[], None]] = None,
        on_calc: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent)

        # 保存回调函数
        self.on_add_files = on_add_files or (lambda: None)
        self.on_inspect = on_inspect or (lambda: None)
        self.on_calc = on_calc or (lambda: None)
        self.on_stop = on_stop or (lambda: None)

        # 构建界面
        self._build_ui()

        # 布局到父窗口
        self.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _build_ui(self):
        """构建 UI 元素"""
        # 顶部按钮区
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        # 4 个按钮
        self.btn_add_files = ttk.Button(
            btn_frame,
            text="添加文件",
            command=self.on_add_files
        )
        self.btn_add_files.pack(side=tk.LEFT, padx=5)

        self.btn_inspect = ttk.Button(
            btn_frame,
            text="检测模型",
            command=self.on_inspect
        )
        self.btn_inspect.pack(side=tk.LEFT, padx=5)

        self.btn_calc = ttk.Button(
            btn_frame,
            text="开始计算",
            command=self.on_calc
        )
        self.btn_calc.pack(side=tk.LEFT, padx=5)

        self.btn_stop = ttk.Button(
            btn_frame,
            text="中断",
            command=self.on_stop,
            state=tk.DISABLED
        )
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        # 日志区域
        log_frame = ttk.LabelFrame(self, text="日志")
        log_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            height=20,
            font=("Consolas", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 配置日志颜色标签
        self.log_text.tag_config('info', foreground='black')
        self.log_text.tag_config('success', foreground='green')
        self.log_text.tag_config('warning', foreground='orange')
        self.log_text.tag_config('error', foreground='red')
        self.log_text.tag_config('sys', foreground='blue')

    # ---- 公开方法：供外部调用来更新 UI ----

    def append_log(self, message: str, level: str = 'info'):
        """追加日志

        Args:
            message: 日志内容
            level: 日志级别 (info/success/warning/error/sys)
        """
        self.log_text.insert(tk.END, message + '\n', level)
        self.log_text.see(tk.END)

    def clear_log(self):
        """清空日志"""
        self.log_text.delete('1.0', tk.END)

    def set_buttons_state(self, calculating: bool):
        """设置按钮状态

        Args:
            calculating: True=正在计算（禁用其他按钮，启用中断按钮）
        """
        if calculating:
            self.btn_add_files.config(state=tk.DISABLED)
            self.btn_inspect.config(state=tk.DISABLED)
            self.btn_calc.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
        else:
            self.btn_add_files.config(state=tk.NORMAL)
            self.btn_inspect.config(state=tk.NORMAL)
            self.btn_calc.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)

    def get_log_content(self) -> str:
        """获取日志内容"""
        return self.log_text.get('1.0', tk.END)


# ---- 独立测试 ----
if __name__ == '__main__':
    def test_add():
        panel.append_log("点击了添加文件", "info")

    def test_inspect():
        panel.append_log("点击了检测模型", "success")

    def test_calc():
        panel.append_log("点击了开始计算", "warning")
        panel.set_buttons_state(calculating=True)

    def test_stop():
        panel.append_log("点击了中断", "error")
        panel.set_buttons_state(calculating=False)

    root = tk.Tk()
    root.title("UI Basic Panel Test")
    root.geometry("800x600")

    panel = BasicPanel(
        root,
        on_add_files=test_add,
        on_inspect=test_inspect,
        on_calc=test_calc,
        on_stop=test_stop
    )

    panel.append_log("UI 面板初始化完成", "sys")
    panel.append_log("这是一条普通日志", "info")
    panel.append_log("这是一条成功日志", "success")
    panel.append_log("这是一条警告日志", "warning")
    panel.append_log("这是一条错误日志", "error")

    root.mainloop()
