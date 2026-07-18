# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 程序入口
=============================================
极简入口: 初始化日志 + 构造 AppContext + 启动 dispatcher + Tk mainloop

不再 import dispatcher / engine_core / ui_basic, 只 import context + 各
工厂方法。完全可测, 写测试时:
    from mini import bootstrap
    root, ctx, app = bootstrap.create_app(log_dir="logs", use_mock=True)
"""
from __future__ import annotations

import logging
import os
import sys
import tkinter as tk

# 让 `python main.py` 也能从 mini 包外跑 (project root 在 NEW/)
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(_HERE)
if _PROJECT not in sys.path:
    sys.path.insert(0, _PROJECT)

from mini.bootstrap import create_app
from mini.logger import get_logger


def main() -> None:
    log = get_logger("main")
    log.info("AmpLab mini 启动")

    root, ctx, app = create_app(log_dir=os.path.join(_HERE, "logs"))

    app.start()

    def on_closing() -> None:
        try:
            app.stop()
        finally:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
    log.info("AmpLab mini 退出")


if __name__ == "__main__":
    main()
