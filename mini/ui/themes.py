# -*- coding: utf-8 -*-
"""ampacity-lab (mini): UI 主题系统
=============================================

定义 2 套主题: normal (默认) / cute (二次元可爱).

字段:
  - font_family:  字体名 (系统没装时 fallback 默认)
  - font_size:    字号
  - bg:           主背景色
  - fg:           主前景色 (文字)
  - button_bg:    按钮背景
  - button_fg:    按钮文字
  - accent:       强调色 (强调按钮 / 状态)
  - button_text:  4 个业务按钮的文字 (含 emoji)
  - toggle_text:  "切换主题" 按钮的文字
  - title:        主窗口标题

用法:
  from mini.ui.themes import THEMES, apply_theme
  apply_theme(root, "cute")  # 应用主题到 root + 所有子 widget
"""
from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk
from typing import Dict


# ---------------------------------------------------------------------------
# 2 套主题定义
# ---------------------------------------------------------------------------

THEMES: Dict[str, Dict] = {
    "normal": {
        "name": "普通",
        "font_family": "Segoe UI",   # Windows 默认; 没有就 fallback
        "font_size": 10,
        "bg": "#F0F0F0",             # 系统灰白
        "fg": "#000000",
        "button_bg": "#E1E1E1",
        "button_fg": "#000000",
        "accent": "#0078D4",         # Windows 蓝
        "button_text": {
            "add_files":  "添加文件",
            "inspect":    "检测模型",
            "calc":       "开始计算",
            "stop":       "中断",
            "log":        "日志",
        },
        "toggle_text": "🎀 可爱模式",
        "title": "Ampacity MVP (mini)",
    },
    "cute": {
        "name": "可爱",
        "font_family": "Comic Sans MS",   # 手写体, Windows 自带
        "font_size": 11,
        "bg": "#FFE4E1",                  # Misty Rose 浅粉
        "fg": "#FF1493",                  # Deep Pink 深粉
        "button_bg": "#FFB6C1",           # Light Pink 浅粉按钮
        "button_fg": "#C71585",           # Medium Violet Red 中紫红
        "accent": "#FF69B4",              # Hot Pink 亮粉
        "button_text": {
            "add_files":  "📁 选模型 🐱",
            "inspect":    "🔍 看看模型",
            "calc":       "💕 开始算",
            "stop":       "⏸ 暂停",
            "log":        "📜 日志",
        },
        "toggle_text": "💼 普通模式",
        "title": "🌸 Ampacity (◕‿◕) 🌸",
    },
}


def get_theme(name: str) -> Dict:
    """取主题字典, 找不到返 normal"""
    return THEMES.get(name, THEMES["normal"])


# ---------------------------------------------------------------------------
# 应用主题
# ---------------------------------------------------------------------------

def apply_theme(root: tk.Tk, theme_name: str) -> None:
    """把主题应用到 root + 所有 ttk widget.

    内部遍历所有 widget, 重设 bg / fg / font.
    业务按钮文字需要在 BasicPanel 里单独更新 (知道每个按钮的引用).
    """
    theme = get_theme(theme_name)

    # 1. 主窗口 title
    root.title(theme["title"])

    # 2. 字体 + 主背景
    font = (theme["font_family"], theme["font_size"])
    try:
        root.configure(bg=theme["bg"])
    except tk.TclError:
        pass  # 某些 platform 不支持

    # 3. ttk 样式
    style = ttk.Style(root)
    try:
        style.theme_use("clam")  # 用 clam 主题, 跨平台一致 + 支持颜色覆盖
    except tk.TclError:
        pass
    style.configure(".",
                    background=theme["bg"],
                    foreground=theme["fg"],
                    fieldbackground=theme["button_bg"],
                    font=font)
    style.configure("TButton",
                    background=theme["button_bg"],
                    foreground=theme["button_fg"],
                    font=font,
                    padding=(8, 4))
    style.map("TButton",
              background=[("active", theme["accent"]), ("pressed", theme["accent"])],
              foreground=[("active", "#FFFFFF")])
    style.configure("TFrame", background=theme["bg"])
    style.configure("TLabel", background=theme["bg"], foreground=theme["fg"], font=font)
    style.configure("TLabelframe", background=theme["bg"], foreground=theme["fg"], font=font)
    style.configure("TLabelframe.Label", background=theme["bg"], foreground=theme["fg"], font=font)
