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
  - 测试:   create_app(use_mock=True) 拿到全 Mock 的 app

加新功能 (例如全局快捷键) 在这里加, 不动 main.py。
"""
from __future__ import annotations

import os
import tkinter as tk
from typing import Optional, Tuple

from .backends import BackendProtocol, MphCompatBackend, MockBackend
from .utils.config import ConfigStore
from .context import AppContext
from .dispatcher import AppDispatcher
from .engine_core import AmpacityEngine
from .utils.logger import Store, init_logging
from .ui_basic import BasicPanel


def create_app(
    log_dir: str = "logs",
    use_mock: bool = False,
    backend: Optional[BackendProtocol] = None,
    geometry: str = "1000x700",
    title: str = "Ampacity MVP (mini)",
) -> Tuple[tk.Tk, AppContext, AppDispatcher]:
    """构造一个完整的 mini app。返回 (root, ctx, dispatcher)。"""

    # 1. 日志 (ring handler 一并就绪)
    init_logging(log_dir=log_dir, level=20, buffer_capacity=2000)

    # 2. Tk root
    root = tk.Tk()
    root.title(title)
    root.geometry(geometry)

    # 3. 后端 / 引擎
    if backend is None:
        backend = MockBackend() if use_mock else MphCompatBackend()
    engine = AmpacityEngine(backend=backend)

    # 4. UI (接 ring handler 以便首次展开回放)
    ui = BasicPanel(root, ring=Store.ring)

    # 5. ConfigStore (用户配置持久化)
    config = ConfigStore()

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
