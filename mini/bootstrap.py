# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 引导程序
=============================================

集中所有"构造完整应用"的步骤:
  - 初始化日志
  - 创建 Tk root
  - 构造 engine (可指定后端)
  - 构造 UI
  - 构造 ConfigStore
  - 打包成 AppContext
  - 构造 AppDispatcher

调用方:
  - main.py: create_app(...) 然后 start()
  - 测试: 直接构造引擎/UI, 不走 create_app (MockBackend 在 tests/_mocks.py)

加新功能 (例如全局快捷键) 在这里加, 不动 main.py。
"""
from __future__ import annotations

import os
import tkinter as tk
from typing import Optional, Tuple

from .backends import BackendProtocol, MphCompatBackend
from .utils.config import ConfigStore
from .context import AppContext
from .dispatcher import AppDispatcher
from .engine_core import AmpacityEngine
from .utils.logger import Store, init_logging
from .ui import BasicPanel
from .ui.utils import center_window


def create_app(
    log_dir: str = "logs",
    backend: Optional[BackendProtocol] = None,
    geometry: str = "1000x700",
    title: str = "Ampacity MVP (mini)",
) -> Tuple[tk.Tk, AppContext, AppDispatcher]:
    """构造一个完整的 mini app。返回 (root, ctx, dispatcher)。

    backend 不传 -> 默认 MphCompatBackend (真 COMSOL).
    测试想用 mock, 自己去 tests/_mocks.py 拿, 不走 create_app.
    """

    # 1. 日志 (ring handler 一并就绪)
    init_logging(log_dir=log_dir, level=10, buffer_capacity=2000)

    # 2. Tk root (一次设大小+位置, 不闪烁)
    # 解析 geometry "WxH" 拿到宽高
    wh = geometry.lower().split("x", 1)
    w, h = int(wh[0]), int(wh[1])
    root = tk.Tk()
    center_window(root, w, h)  # 居中到屏幕 (一次设)
    root.title(title)

    # 3. 后端 / 引擎
    if backend is None:
        backend = MphCompatBackend()
    engine = AmpacityEngine(backend=backend)

    # 4. ConfigStore (用户配置持久化) - 必须在 UI 之前创建
    config = ConfigStore()

    # 5. UI (接 ring handler 以便首次展开回放)
    ui = BasicPanel(root, ring=Store.ring, config=config)

    # 6. AppContext (打包所有依赖)
    ctx = AppContext(
        root=root,
        engine=engine,
        ui=ui,
        bus=engine.bus,
        config=config,
        log_dir=log_dir,
    )

    # 7. Dispatcher (只接 ctx, 不直接 import 任何其他东西)
    app = AppDispatcher(ctx)

    return root, ctx, app
