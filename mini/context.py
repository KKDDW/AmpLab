# -*- coding: utf-8 -*-
"""ampacity-lab (mini): AppContext
=============================================

把所有跨模块的依赖打包成一个对象, 取代散落在 dispatcher 里的 self.xxx。

设计:
  - 不可变 (frozen) —— 创建后不能再改
  - dispatcher 只 import AppContext, 不直接 import engine/ui/store
  - 写测试时构造一个 AppContext(engine=MockEngine(), ui=MockUI(), ...)
  - 加新依赖 (比如 metrics collector), 加一个字段即可, 不动 dispatcher 签名

字段:
  root:        tk.Tk 根窗口
  engine:      AmpacityEngine
  ui:          BasicPanel
  bus:         EventBus (= engine.bus)
  config:      ConfigStore
  log_dir:     日志目录
"""
from __future__ import annotations

import os
import tkinter as tk
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .utils.config import ConfigStore
    from .engine_core import AmpacityEngine
    from .utils.events import EventBus
    from .ui_basic import BasicPanel


@dataclass(frozen=True)
class AppContext:
    root: "tk.Tk"
    engine: "AmpacityEngine"
    ui: "BasicPanel"
    bus: "EventBus"
    config: "ConfigStore"
    log_dir: str = "logs"

    @property
    def log(self):
        """每个模块用自己的 logger, 但 dispatcher 也能从 ctx 拿一个"""
        from .utils.logger import get_logger
        return get_logger("dispatcher")
