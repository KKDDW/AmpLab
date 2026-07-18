# -*- coding: utf-8 -*-
"""ampacity-lab (mini): UI 公共常量
=============================================

放 UI 用的颜色 / 级别常量, 多个 UI 模块 (BasicPanel / LogWindow) 共享.
单独一个文件方便维护: 想加新颜色/新业务级别, 改这里一处即可.
"""
from __future__ import annotations

# 日志级别 -> (显示颜色, Text 控件使用的 tag 名)
LEVEL_STYLE: dict = {
    "DEBUG":    ("gray",   "debug"),
    "INFO":     ("black",  "info"),
    "WARNING":  ("orange", "warning"),
    "ERROR":    ("red",    "error"),
    "CRITICAL": ("red",    "critical"),
    "sys":      ("blue",   "sys"),       # 业务自定义: 系统级消息
    "success":  ("green",  "success"),   # 业务自定义: 成功消息
}

# 级别优先级 (数字越大越严重).
# 切到 INFO 意味着 DEBUG 不显示, 其它 (>=20) 都显示.
# 跟 Python 原生 logging 标准完全一致, 方便底层直接对接.
LEVEL_ORDER: dict = {
    "DEBUG":    10,
    "INFO":     20,
    "WARNING":  30,
    "ERROR":    40,
    "CRITICAL": 50,
    "sys":      20,    # 业务自定义, 跟 INFO 同级
    "success":  20,    # 业务自定义, 跟 INFO 同级
}

# UI 上显示的 4 个 level 按钮 (顺序就是 UI 上的从左到右)
LEVEL_BUTTONS = [
    ("DEBUG",   "DEBUG"),
    ("INFO",    "INFO"),
    ("WARNING", "WARN"),
    ("ERROR",   "ERR"),
]
