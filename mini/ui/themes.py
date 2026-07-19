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
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# 2 套主题定义
# ---------------------------------------------------------------------------

THEMES: Dict[str, Dict] = {
    "normal": {
        "name": "普通",
        "font_family": "Microsoft YaHei UI",  # 统一使用微软雅黑
        "font_size": 10,
        "bg": "#F0F0F0",             # 系统灰白
        "fg": "#000000",
        "button_bg": "#E1E1E1",
        "button_fg": "#000000",
        "accent": "#0078D4",         # Windows 蓝
        "button_style": "default",   # 默认样式
        "button_text": {
            "add_files":  "添加文件",
            "inspect":    "检测模型",
            "calc":       "开始计算",
            "stop":       "中断",
            "log":        "日志",
        },
        "toggle_text": "切换主题 →",
        "title": "Ampacity MVP (mini)",
    },
    "cute": {
        "name": "可爱",
        "font_family": "Microsoft YaHei UI",  # 统一使用微软雅黑（保证尺寸一致）
        "font_size": 10,
        "bg": "#FFF0F5",                  # Lavender Blush 薰衣草粉
        "fg": "#FF1493",                  # Deep Pink 深粉
        "button_bg": "#FFB6C1",           # Light Pink 浅粉按钮
        "button_fg": "#C71585",           # Medium Violet Red 中紫红
        "accent": "#FF69B4",              # Hot Pink 亮粉
        "button_style": "cute",           # 可爱样式（圆角）
        "button_text": {
            "add_files":  "🐱 添加文件",
            "inspect":    "🔍 检测模型",
            "calc":       "💕 开始计算",
            "stop":       "⏸  中断",
            "log":        "📜 日志",
        },
        "toggle_text": "切换主题 →",
        "title": "🌸 Ampacity (◕‿◕) 🌸",
    },
    "dark": {
        "name": "暗黑",
        "font_family": "Microsoft YaHei UI",  # 统一使用微软雅黑
        "font_size": 10,
        "bg": "#1E1E1E",                  # VS Code 暗色背景
        "fg": "#D4D4D4",                  # 浅灰文字
        "button_bg": "#2D2D30",           # 深灰按钮
        "button_fg": "#CCCCCC",           # 按钮文字
        "accent": "#007ACC",              # VS Code 蓝
        "button_style": "default",        # 默认样式
        "button_text": {
            "add_files":  "⊕  添加文件",
            "inspect":    "⚡ 检测模型",
            "calc":       "▶  开始计算",
            "stop":       "■  中断",
            "log":        "◈  日志",
        },
        "toggle_text": "切换主题 →",
        "title": "Ampacity MVP (mini) - Dark Mode",
    },
    "ocean": {
        "name": "海洋",
        "font_family": "Microsoft YaHei UI",  # 统一使用微软雅黑
        "font_size": 10,
        "bg": "#E0F7FA",                  # Cyan 50 - 更浅的青色
        "fg": "#004D40",                  # 深青绿文字
        "button_bg": "#B2EBF2",           # Cyan 200 - 青色按钮
        "button_fg": "#00695C",           # 深青绿按钮文字
        "accent": "#00ACC1",              # Cyan 600 - 青色强调
        "button_style": "default",        # 默认样式
        "button_text": {
            "add_files":  "🌊 添加文件",
            "inspect":    "🐚 检测模型",
            "calc":       "🚢 开始计算",
            "stop":       "⚓ 中断",
            "log":        "📖 日志",
        },
        "toggle_text": "切换主题 →",
        "title": "Ampacity MVP - Ocean Theme 🌊",
    },
}

# 主题切换顺序 (定义循环顺序)
THEME_ORDER = ["normal", "cute", "dark", "ocean"]


def get_theme(name: str) -> Dict:
    """取主题字典, 找不到返 normal"""
    return THEMES.get(name, THEMES["normal"])


def get_next_theme(current_theme: str) -> str:
    """获取下一个主题名称 (循环切换)

    Parameters
    ----------
    current_theme : str
        当前主题名称

    Returns
    -------
    str
        下一个主题名称

    Examples
    --------
    >>> get_next_theme("normal")
    "cute"
    >>> get_next_theme("ocean")
    "normal"  # 循环回第一个
    """
    try:
        idx = THEME_ORDER.index(current_theme)
        next_idx = (idx + 1) % len(THEME_ORDER)
        return THEME_ORDER[next_idx]
    except ValueError:
        # 如果当前主题不在列表中，返回第一个
        return THEME_ORDER[0]


# ---------------------------------------------------------------------------
# 应用主题
# ---------------------------------------------------------------------------

# 全局样式引擎单例 (避免每次 apply_theme 都重新创建)
_style_engine: Optional[ttk.Style] = None
_style_initialized: bool = False


def _init_style_engine(root: tk.Tk) -> ttk.Style:
    """初始化样式引擎 (只在程序启动时调用一次)"""
    global _style_engine, _style_initialized
    if _style_engine is None or not _style_initialized:
        _style_engine = ttk.Style(root)
        try:
            _style_engine.theme_use("clam")  # 用 clam 主题, 跨平台一致 + 支持颜色覆盖
        except tk.TclError:
            pass
        _style_initialized = True
    return _style_engine


def apply_theme(root: tk.Tk, theme_name: str) -> None:
    """把主题应用到 root + 所有 ttk widget.

    优化点:
      - 样式引擎只初始化一次 (首次调用时), 后续只更新配置参数
      - 减少重复的 theme_use("clam") 调用, 提升切换性能
      - 使用固定 padding 确保按钮视觉大小一致
      - 支持不同的按钮风格 (default / cute)
      - 业务按钮文字需要在 BasicPanel 里单独更新 (知道每个按钮的引用)
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

    # 3. ttk 样式 (获取单例引擎, 只更新配置)
    style = _init_style_engine(root)
    style.configure(".",
                    background=theme["bg"],
                    foreground=theme["fg"],
                    fieldbackground=theme["button_bg"],
                    font=font)

    # 4. 按钮样式：根据主题选择不同风格
    button_style = theme.get("button_style", "default")

    if button_style == "cute":
        # 可爱风格：圆角、较大 padding、渐变效果
        style.configure("TButton",
                        background=theme["button_bg"],
                        foreground=theme["button_fg"],
                        font=font,
                        borderwidth=2,
                        relief="raised",
                        padding=(12, 8))  # 更大的内边距
        style.map("TButton",
                  background=[
                      ("disabled", "#E0E0E0"),
                      ("active", theme["accent"]),
                      ("pressed", "#FF1493")  # 可爱风格：按下时更鲜艳
                  ],
                  foreground=[
                      ("disabled", "#AAAAAA"),
                      ("active", "#FFFFFF"),
                      ("pressed", "#FFFFFF")
                  ],
                  relief=[
                      ("pressed", "sunken"),
                      ("active", "raised")
                  ])
    else:
        # 默认风格：简洁扁平
        style.configure("TButton",
                        background=theme["button_bg"],
                        foreground=theme["button_fg"],
                        font=font,
                        borderwidth=1,
                        padding=(10, 6))
        style.map("TButton",
                  background=[
                      ("disabled", "#CCCCCC"),
                      ("active", theme["accent"]),
                      ("pressed", theme["accent"])
                  ],
                  foreground=[
                      ("disabled", "#999999"),
                      ("active", "#FFFFFF")
                  ])

    # 5. 其他组件样式
    style.configure("TFrame", background=theme["bg"])
    style.configure("TLabel", background=theme["bg"], foreground=theme["fg"], font=font)
    style.configure("TLabelframe", background=theme["bg"], foreground=theme["fg"], font=font)
    style.configure("TLabelframe.Label", background=theme["bg"], foreground=theme["fg"], font=font)
