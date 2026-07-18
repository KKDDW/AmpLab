# -*- coding: utf-8 -*-
"""ampacity-lab (mini): UI 工具函数
=============================================

放 UI 相关的通用工具, 不依赖具体某个 UI 组件 (BasicPanel / LogWindow 等都可调).

当前:
  - center_window(root, width, height): 把 Tk 窗口居中到屏幕, 一次设大小+位置
"""
from __future__ import annotations

import tkinter as tk


def center_window(root: tk.Tk, width: int, height: int) -> None:
    """把 root 居中到当前屏幕, 一次设大小+位置 (不会闪烁).

    跟 `root.geometry("WxH+x+y")` 等价, 但自动算中心坐标.
    Tkinter 不会自动居中, 手动算屏幕坐标.
    """
    root.update_idletasks()  # 强制 Tk 算好屏幕尺寸
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - width) // 2
    y = (sh - height) // 2
    root.geometry(f"{width}x{height}+{x}+{y}")

