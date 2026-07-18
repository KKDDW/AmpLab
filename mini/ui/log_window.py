# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 日志弹窗
=============================================

独立的日志弹窗组件, 由 BasicPanel 调用 .toggle() 显示/隐藏,
.append() / .set_level() / .clear() 等公开 API 跟外部交互.

跟 BasicPanel 的关系 (A1 拆法):
  - LogWindow 不知道 BasicPanel 存在
  - BasicPanel 持有 self._log_window: Optional[LogWindow] 字段
  - BasicPanel 把外部 append_log 等调用转发给 LogWindow
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime
from typing import Optional

from .constants import LEVEL_STYLE, LEVEL_ORDER, LEVEL_BUTTONS
from ..utils.logger import get_logger, RingBufferHandler

log = get_logger(__name__)


class LogWindow:
    """日志弹窗 (Toplevel)

    公开方法:
      - toggle(): 切显示/隐藏
      - append(message, level): 追加一条 (主线程调用, 内部用 root.after)
      - set_level(level): 切过滤级别
      - clear(): 清空当前显示
      - get_content() -> str: 取当前显示的文本
    """

    # 弹窗默认尺寸 (像素). 想改大小, 改这一处.
    WIN_W = 1000
    WIN_H = 500

    def __init__(self, root: tk.Tk, ring: Optional[RingBufferHandler] = None) -> None:
        """
        Parameters
        ----------
        root : tk.Tk
            主窗口 (用于 after 调度和 Toplevel 父级)
        ring : RingBufferHandler, optional
            日志环形缓冲. 弹窗第一次打开时回放历史.
        """
        self._root = root
        self._ring = ring
        self._win: Optional[tk.Toplevel] = None  # 弹窗实例
        self._replayed = False  # 是否已经回放过历史
        self._log_level = "DEBUG"  # 默认全显示

        # 弹窗内的 widget 引用 (弹窗创建后才有效)
        self.log_text: Optional[scrolledtext.ScrolledText] = None
        self._log_level_buttons: dict = {}  # level -> Button

    # =======================================================================
    # 公开 API
    # =======================================================================

    def toggle(self) -> None:
        """切显示/隐藏. 已开 -> 关; 未开 -> 开."""
        if self._win is not None and self._win.winfo_exists():
            self._win.destroy()
            self._win = None
        else:
            self._open()

    def append(self, message: str, level: str = "info") -> None:
        """追加一条日志 (外部调用, 可在子线程).

        低于当前过滤级别: 丢弃.
        弹窗没开: 丢弃 (下次开窗会从 ring 回放).
        """
        ts = datetime.now()
        level_norm = level.upper() if level.upper() in LEVEL_STYLE else "INFO"
        if not self._should_show(level_norm):
            return
        if not (self._win is not None and self._win.winfo_exists()):
            return
        # 必须投递到主线程 (Tkinter 安全要求)
        self._root.after(0, self._write_line, ts, level_norm, message)

    def set_level(self, level: str) -> None:
        """切过滤级别. 清空 + 重放."""
        if level not in LEVEL_ORDER:
            return
        self._log_level = level
        log.debug("日志级别切换到 %s", level)
        self._refresh_level_buttons()

        if self.log_text is None:
            return

        # 清空当前内容
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

        # 重置回放标志, 立即重放
        self._replayed = False
        if self._win is not None and self._win.winfo_exists():
            self._replayed = True
            self._replay_ring()

    def clear(self) -> None:
        """清空当前显示 (不重放)."""
        if self.log_text is None:
            return
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def get_content(self) -> str:
        """取当前显示的全文 (给外部存/导出用)."""
        if self.log_text is None:
            return ""
        return self.log_text.get("1.0", tk.END)

    # =======================================================================
    # 内部: 弹窗创建
    # =======================================================================

    def _open(self) -> None:
        win = tk.Toplevel(self._root)
        win.title("AmpLab 日志")
        # 弹窗出现在主窗口正中间 (不是屏幕, 因为主窗口可能不在屏幕正中间)
        # 一次设大小+位置, 不闪烁
        self._root.update_idletasks()
        rx = self._root.winfo_rootx()
        ry = self._root.winfo_rooty()
        rw = self._root.winfo_width()
        rh = self._root.winfo_height()
        x = rx + (rw - self.WIN_W) // 2
        y = ry + (rh - self.WIN_H) // 2
        win.geometry(f"{self.WIN_W}x{self.WIN_H}+{x}+{y}")

        # 1. 顶部控制栏
        top = ttk.Frame(win)
        top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(8, 4))
        ttk.Label(top, text="级别:").pack(side=tk.LEFT, padx=(0, 8))

        self._log_level_buttons = {}
        for lvl, label in LEVEL_BUTTONS:
            btn = ttk.Button(
                top, text=label, width=6,
                command=lambda L=lvl: self.set_level(L),
            )
            btn.pack(side=tk.LEFT, padx=2)
            self._log_level_buttons[lvl] = btn

        ttk.Button(top, text="清空", width=6, command=self.clear).pack(side=tk.RIGHT, padx=2)
        ttk.Button(top, text="关闭", width=6, command=win.destroy).pack(side=tk.RIGHT, padx=2)

        # 2. 核心文本区
        self.log_text = scrolledtext.ScrolledText(
            win, wrap=tk.WORD, font=("Consolas", 9),
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # 颜色 tag
        for fg, tag in LEVEL_STYLE.values():
            self.log_text.tag_config(tag, foreground=fg)
        self.log_text.configure(state=tk.DISABLED)

        # 3. 初始: 高亮默认 level + 回放历史
        self._refresh_level_buttons()
        if not self._replayed:
            self._replay_ring()
            self._replayed = True

        self._win = win

    def _replay_ring(self) -> None:
        """从 ring buffer 灌历史日志 (按当前 level 过滤)."""
        if self._ring is None or self.log_text is None:
            return
        snap = self._ring.snapshot()
        shown = 0
        for ts, level, msg in snap:
            if self._should_show(level):
                self._write_line(ts, level, msg)
                shown += 1
        if shown:
            self._write_line(
                datetime.now(), "info",
                f"—— 以上 {shown}/{len(snap)} 条为过滤后历史 (level={self._log_level}) ——"
            )

    def _should_show(self, level: str) -> bool:
        """level >= _log_level 阈值才显示."""
        threshold = LEVEL_ORDER.get(self._log_level, 20)
        actual = LEVEL_ORDER.get(level, 20)
        return actual >= threshold

    def _refresh_level_buttons(self) -> None:
        """高亮当前 level 按钮 (其它弹起)."""
        for lvl, btn in self._log_level_buttons.items():
            if lvl == self._log_level:
                btn.state(["pressed"])
            else:
                btn.state(["!pressed"])

    def _write_line(self, ts: datetime, level: str, msg: str) -> None:
        """底层: 写一行到 ScrolledText (必须在主线程)."""
        if self.log_text is None:
            return
        line = f"[{ts:%Y-%m-%d %H:%M:%S}]  {level:<8}  {msg}"
        _, tag = LEVEL_STYLE.get(level, ("black", "info"))
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)
