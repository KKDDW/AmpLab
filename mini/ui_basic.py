# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 基础 UI 界面
=============================================

改进点:
  1. 顶部加一个"日志"按钮 —— 默认不显示日志区
  2. 点一下展开/收起日志区, 首次展开时从 ring buffer 拉历史
  3. 实时日志: dispatcher 调 append_log, 内部用 root.after 防线程问题
  4. 完全不认识 engine_core, 只通过回调通信
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Callable, List, Optional, Tuple
from datetime import datetime

from .utils.logger import get_logger, RingBufferHandler

log = get_logger(__name__)


# 日志级别 -> 颜色 / tag
_LEVEL_STYLE = {
    "DEBUG":    ("gray",    "debug"),
    "INFO":     ("black",   "info"),
    "WARNING":  ("orange",  "warning"),
    "ERROR":    ("red",     "error"),
    "CRITICAL": ("red",     "critical"),
    "sys":      ("blue",    "sys"),       # 业务自定义
    "success":  ("green",   "success"),   # 业务自定义
}

# 级别优先级 (数字越大越严重). 切到 INFO 意味着 DEBUG 不显示, 其它都显示.
# 跟 Python logging 标准一致 (DEBUG=10, INFO=20, WARNING=30, ERROR=40, CRITICAL=50)
_LEVEL_ORDER = {
    "DEBUG":    10,
    "INFO":     20,
    "WARNING":  30,
    "ERROR":    40,
    "CRITICAL": 50,
    "sys":      20,   # 业务自定义, 跟 INFO 同级
    "success":  20,   # 业务自定义, 跟 INFO 同级
}


class BasicPanel(ttk.Frame):
    """基础界面面板 (4 个业务按钮 + 1 个日志切换按钮)

    业务回调 (注入式):
        on_add_files, on_inspect, on_calc, on_stop
    日志:
        内部维护一个 ScrolledText, 默认隐藏, 点"日志"按钮才显示
        日志源是 RingBufferHandler, 启动时回放历史
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
        self.root = parent if isinstance(parent, tk.Tk) else parent.winfo_toplevel()

        self.on_add_files = on_add_files or (lambda: None)
        self.on_inspect = on_inspect or (lambda: None)
        self.on_calc = on_calc or (lambda: None)
        self.on_stop = on_stop or (lambda: None)
        self._ring = ring

        # 日志区状态
        self._log_visible = False
        self._replayed = False  # 日志区首次展开时回放一次
        # 当前显示级别 (默认 INFO, 不显示 DEBUG). 切换时重新过滤.
        self._log_level = "INFO"

        self._build_ui()
        self.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _set_callbacks(
        self,
        on_add_files: Optional[Callable[[], None]] = None,
        on_inspect: Optional[Callable[[], None]] = None,
        on_calc: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
    ) -> None:
        """(重新)设置业务回调, 同时把按钮 command 重新绑定。
        适合 dispatcher 在创建 ui 之后再注入回调的场景。"""
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

    # ---- 布局 ----

    def _build_ui(self) -> None:
        # 顶部按钮区
        bar = ttk.Frame(self)
        bar.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))

        self.btn_add_files = ttk.Button(
            bar, text="添加文件", command=self.on_add_files
        )
        self.btn_add_files.pack(side=tk.LEFT, padx=4)

        self.btn_inspect = ttk.Button(
            bar, text="检测模型", command=self.on_inspect
        )
        self.btn_inspect.pack(side=tk.LEFT, padx=4)

        self.btn_calc = ttk.Button(
            bar, text="开始计算", command=self.on_calc
        )
        self.btn_calc.pack(side=tk.LEFT, padx=4)

        self.btn_stop = ttk.Button(
            bar, text="中断", command=self.on_stop, state=tk.DISABLED
        )
        self.btn_stop.pack(side=tk.LEFT, padx=4)

        # 日志切换按钮 —— 单独贴在右侧
        self.btn_toggle_log = ttk.Button(
            bar, text="日志 ▾", command=self._toggle_log, width=8
        )
        self.btn_toggle_log.pack(side=tk.RIGHT, padx=4)

        # 日志级别过滤按钮 (DEBUG/INFO/WARN/ERR) —— 紧贴日志按钮左侧
        # 默认 INFO (DEBUG 不显示); 实时切换并重新过滤
        self._log_level_buttons = {}
        for lvl, label in [("DEBUG", "DEBUG"), ("INFO", "INFO"),
                            ("WARNING", "WARN"), ("ERROR", "ERR")]:
            btn = ttk.Button(
                bar, text=label, width=6,
                command=lambda L=lvl: self._set_log_level(L),
            )
            btn.pack(side=tk.RIGHT, padx=2)
            self._log_level_buttons[lvl] = btn
        # 初始时高亮默认级别
        self._refresh_level_buttons()

        # 业务展示区 (Phase 3 再丰富, 现在留空 frame 占位)
        body = ttk.Frame(self)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        ttk.Label(
            body, text="(业务展示区 — Phase 3 接入)",
            foreground="gray"
        ).pack(pady=40)

        # 日志容器 (默认不 pack, 即隐藏)
        self._log_container = ttk.LabelFrame(self, text="日志")
        self.log_text = scrolledtext.ScrolledText(
            self._log_container,
            wrap=tk.WORD, height=18, font=("Consolas", 9),
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 颜色 tag (按 level 统一)
        for fg, tag in _LEVEL_STYLE.values():
            self.log_text.tag_config(tag, foreground=fg)

        # 启动时不让它自己抢焦点
        self.log_text.configure(state=tk.DISABLED)

    # ---- 日志区显隐 ----

    def _toggle_log(self) -> None:
        if self._log_visible:
            self._log_container.pack_forget()
            self.btn_toggle_log.configure(text="日志 ▾")
            self._log_visible = False
        else:
            self._log_container.pack(
                side=tk.TOP, fill=tk.BOTH, expand=True, pady=(8, 0)
            )
            self.btn_toggle_log.configure(text="日志 ▴")
            self._log_visible = True
            if not self._replayed:
                self._replay_ring()
                self._replayed = True

    def _replay_ring(self) -> None:
        """首次展开时把 ring buffer 的历史塞进日志区 (按当前 level 过滤)"""
        if self._ring is None:
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
        """按当前 _log_level 过滤. 业务自定义 level (sys/success) 跟 INFO 同级."""
        threshold = _LEVEL_ORDER.get(self._log_level, 20)
        actual = _LEVEL_ORDER.get(level, 20)
        return actual >= threshold

    def _set_log_level(self, level: str) -> None:
        """切换日志显示级别. 清空当前内容, 重新从 ring buffer 过滤回放."""
        if level not in _LEVEL_ORDER:
            return
        self._log_level = level
        self._refresh_level_buttons()
        log.info("日志级别切换到 %s", level)
        # 清掉当前 ScrolledText 内容, 重新回放
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        # 强制标记未回放, 让 _toggle_log 下次展开时回放
        self._replayed = False
        if self._log_visible:
            self._replayed = True
            self._replay_ring()

    def _refresh_level_buttons(self) -> None:
        """高亮当前选中的 level 按钮 (其它按钮复位)."""
        for lvl, btn in self._log_level_buttons.items():
            if lvl == self._log_level:
                btn.state(["pressed"])
            else:
                btn.state(["!pressed"])

    def _write_line(self, ts: datetime, level: str, msg: str) -> None:
        """写一行日志到 ScrolledText (线程安全). 内部不再过滤, 调用方负责."""
        line = f"[{ts:%H:%M:%S}] {level:<7} {msg}"
        _, tag = _LEVEL_STYLE.get(level, ("black", "info"))
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ---- 公开方法 (供 dispatcher 调用) ----

    def append_log(self, message: str, level: str = "info") -> None:
        """追加一条日志 (主线程直接调; 后台线程通过 root.after 调).
        按当前 _log_level 过滤, 低于级别的直接丢弃."""
        ts = datetime.now()
        # 统一把业务 level 转 logging level 名, 找不到就用 info
        level_norm = level.upper() if level.upper() in _LEVEL_STYLE else "INFO"
        if not self._should_show(level_norm):
            return
        self.root.after(0, self._write_line, ts, level_norm, message)

    def clear_log(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def set_buttons_state(self, calculating: bool) -> None:
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
        return self.log_text.get("1.0", tk.END)


# ---- 独立测试 ----
if __name__ == "__main__":
    from .utils.logger import init_logging
    ring = init_logging(log_dir="logs", level=10)  # DEBUG, 全看

    def t_add():
        log.info("点击 添加文件")

    def t_inspect():
        log.info("点击 检测模型")
        log.warning("假装模型有 warning")

    def t_calc():
        log.info("点击 开始计算")
        panel.set_buttons_state(True)

    def t_stop():
        log.error("假装出错了")
        panel.set_buttons_state(False)

    root = tk.Tk()
    root.title("UI Basic Panel Test (mini)")
    root.geometry("900x650")
    panel = BasicPanel(
        root,
        on_add_files=t_add, on_inspect=t_inspect,
        on_calc=t_calc, on_stop=t_stop,
        ring=ring,
    )
    log.info('UI 启动完成 — 日志区默认隐藏, 点右上"日志"按钮展开')
    root.mainloop()
