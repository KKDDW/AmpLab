# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 统一日志模块
=============================================

设计要点:
  1. 单一入口 get_logger(name) —— 任何模块都从这里拿 logger
  2. 同时写两路:
     - 控制台 (StreamHandler) —— 开发时看
     - 文件 (TimedRotatingFileHandler) —— 出错时翻 log 文件
     - RingBufferHandler —— 内存里留最近 N 条, 供 UI 调出
  3. UI 不直接读 logger, 而是通过 LogStore.fetch() 拿最近日志
     (UI 关闭再打开也能看到关闭前的历史)
  4. 日志文件落在 ./logs/ampacity_YYYYMMDD.log, 自动按天切

用法:
    from mini.logger import get_logger
    log = get_logger(__name__)
    log.info("hello")
    log.error("oops", exc_info=True)
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import threading
from collections import deque
from datetime import datetime
from typing import Deque, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 日志级别颜色 (终端 ANSI; Win11 / PowerShell / VSCode / Windows Terminal 都支持)
# ---------------------------------------------------------------------------

_COLOR_MAP = {
    "DEBUG":    "\033[90m",   # 亮灰
    "INFO":     "\033[97m",   # 亮白 (高对比, 显眼)
    "WARNING":  "\033[33m",   # 黄
    "ERROR":    "\033[91m",   # 亮红
    "CRITICAL": "\033[41;97m",  # 红底白字
}
_RESET = "\033[0m"
_DIM = "\033[2m"           # 时间戳变暗, 让级别和消息更突出
_BOLD = "\033[1m"

# 字段高亮: 数字亮绿 (一眼看到数据), 状态关键词染色 (成功=亮绿, 失败/异常=亮红)
_NUMBER_COLOR = "\033[92m"  # 亮绿
_KEYWORD_OK = "\033[92m"     # 亮绿 - 成功/收敛/✓
_KEYWORD_BAD = "\033[91m"    # 亮红 - 失败/异常/✗
_KEYWORD_WARN = "\033[33m"   # 黄   - 警告/没收敛

# 数字匹配: 整数 / 小数 / 百分号
# 边界: 前面不能是字母 (避免 abc123), 后面不能是字母
# (允许 =-/ 等符号, 数字应该是 "key=value" / "key-value" 里的 value 部分)
import re as _re
_NUM_RE = _re.compile(r'(?<![a-zA-Z.])\d+(?:\.\d+)?%?(?![a-zA-Z0-9])')
# 2+ 空格分隔 (用于解析 fmt 输出)
_WS_RE = _re.compile(r'  +')

# 状态关键词 (不区分大小写)
_KEYWORDS_OK = ("成功", "✓", "收敛", "完成", "ok", "done", "success")
_KEYWORDS_BAD = ("失败", "异常", "✗", "错误", "error", "fail", "exception", "crash")
_KEYWORDS_WARN = ("警告", "warning", "没收敛", "未收敛")


class _ColorFormatter(logging.Formatter):
    """给控制台加颜色 (Windows Terminal / VSCode 终端都能识别)

    配色:
      - 时间戳:   暗灰
      - 级别:     按 _COLOR_MAP
      - 模块名:   暗灰
      - 消息:     亮白, 数字亮绿, 状态关键词按类型染色
    """

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        color = _COLOR_MAP.get(record.levelname, "")
        if not color:
            return msg

        # 解析 fmt 输出: "YYYY-MM-DD HH:MM:SS  LEVEL  module.name  message"
        # 用 2+ 空格分隔 (logging 会把字段对齐, 可能多空格)
        try:
            parts = _WS_RE.split(msg, maxsplit=3)
            if len(parts) < 4:
                # 拆不出 4 段, 走原始
                return f"{color}{msg}{_RESET}"
            timestamp, level_str, module_str, body = parts
            # 给消息里的数字 / 状态词染色
            colored_body = self._colorize_body(body)
            return (f"{_DIM}{timestamp}{_RESET}  "
                    f"{_BOLD}{color}{level_str}{_RESET}  "
                    f"{_DIM}{module_str}{_RESET}  {colored_body}")
        except Exception:
            return f"{color}{msg}{_RESET}"

    def _colorize_body(self, body: str) -> str:
        """给消息里的状态关键词染色

        不染数字, 正文不加粗 (只是普通白字). 关键词 (成功/失败/异常) 才染色.
        """
        out = body
        # 1. 成功关键词 (亮绿)
        for kw in _KEYWORDS_OK:
            if kw in out:
                out = out.replace(kw, f"{_KEYWORD_OK}{kw}{_RESET}")
        # 2. 失败关键词 (亮红)
        for kw in _KEYWORDS_BAD:
            if kw in out:
                out = out.replace(kw, f"{_KEYWORD_BAD}{kw}{_RESET}")
        # 3. 警告关键词 (黄)
        for kw in _KEYWORDS_WARN:
            if kw in out:
                out = out.replace(kw, f"{_KEYWORD_WARN}{kw}{_RESET}")
        return out


# ---------------------------------------------------------------------------
# RingBufferHandler —— 内存里存最近 N 条
# ---------------------------------------------------------------------------

class RingBufferHandler(logging.Handler):
    """线程安全的环形缓冲, 最多保留 N 条日志。

    配合 LogStore 一起用: UI 调用 LogStore.fetch() 拿到最近 N 条
    格式化好的字符串列表, 然后一次性塞进 ScrolledText。
    """

    def __init__(self, capacity: int = 2000) -> None:
        super().__init__()
        self._buf: Deque[Tuple[datetime, str, str]] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # 只存纯消息 (record.getMessage()), 不带日期/级别
            # UI 回放时用自己的格式渲染, 避免重复
            msg = record.getMessage()
            ts = datetime.fromtimestamp(record.created)
            with self._lock:
                self._buf.append((ts, record.levelname, msg))
        except Exception:
            # 日志处理器自己挂了就别再抛了, 否则整个程序都炸
            self.handleError(record)

    def snapshot(self) -> List[Tuple[datetime, str, str]]:
        """返回当前缓冲区的浅拷贝 (线程安全)"""
        with self._lock:
            return list(self._buf)


# ---------------------------------------------------------------------------
# LogStore —— 全局唯一, 持有 RingBufferHandler
# ---------------------------------------------------------------------------

class _LogStore:
    """日志存储单例。

    之所以用单例 + 显式 init(), 是因为:
      - 测试 / 独立运行时不需要文件 handler (init() 不调就不写)
      - 但 RingBuffer 永远在, 任何场景 UI 都能拿
    """

    _instance: Optional["_LogStore"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "_LogStore":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def init(
        self,
        log_dir: str = "logs",
        level: int = logging.DEBUG,
        buffer_capacity: int = 2000,
    ) -> RingBufferHandler:
        """初始化全局日志系统。重复调用安全, 返回 ring handler 供 UI 用。"""
        if self._initialized:
            return self._ring  # type: ignore[attr-defined]

        # 1. 根 logger —— 设为 DEBUG 让所有级别的 record 都能下到 handler
        # 真正的"用户想要的 level"由 console handler 控制 (下面 line 158)
        # ring + file handler 永远全留 (UI / 日志文件可看全量)
        root = logging.getLogger("ampacity")
        root.setLevel(logging.DEBUG)
        root.propagate = False  # 别再往 root logger 冒泡

        # 格式: "YYYY-MM-DD HH:MM:SS  LEVEL  module.name  message"
        # 用 2+ 空格分隔, _ColorFormatter 解析
        fmt = "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"   # 带日期, 到秒 (不要毫秒, 易读)
        formatter = logging.Formatter(fmt, datefmt=datefmt)

        # 2. 控制台 —— 硬编码 INFO+ (不显示 DEBUG, 不管 init_logging 传啥)
        # 调试细节靠 UI 弹窗切到 DEBUG 看
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(_ColorFormatter(fmt, datefmt=datefmt))
        root.addHandler(console)

        # 3. 文件 (按天切, 保留 14 天)
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(
            log_dir, f"ampacity_{datetime.now():%Y%m%d}.log"
        )
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=14,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # 文件比控制台详细
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

        # 4. Ring buffer (UI 用)
        self._ring = RingBufferHandler(capacity=buffer_capacity)
        self._ring.setLevel(logging.DEBUG)  # 缓冲区全留, UI 自己过滤
        self._ring.setFormatter(formatter)
        root.addHandler(self._ring)

        self._initialized = True
        root.info("=" * 60)
        root.info("AmpLab mini 启动  pid=%d  cwd=%s",
                  os.getpid(), os.getcwd())
        root.info("=" * 60)
        return self._ring

    @property
    def ring(self) -> RingBufferHandler:
        if not self._initialized:
            raise RuntimeError(
                "LogStore 未初始化, 请先调用 LogStore.init()"
            )
        return self._ring  # type: ignore[attr-defined]


# 模块级单例入口
Store = _LogStore()


def init_logging(
    log_dir: str = "logs",
    level: int = logging.DEBUG,
    buffer_capacity: int = 2000,
) -> RingBufferHandler:
    """便捷入口: 初始化日志系统, 返回 ring handler 供 UI 订阅。"""
    return Store.init(log_dir=log_dir, level=level, buffer_capacity=buffer_capacity)


def get_logger(name: str) -> logging.Logger:
    """任何模块: log = get_logger(__name__)"""
    # 所有 logger 挂在 'ampacity' 根下, 统一管理
    if not name.startswith("ampacity"):
        name = f"ampacity.{name}"
    return logging.getLogger(name)
