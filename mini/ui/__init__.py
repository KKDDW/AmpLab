# -*- coding: utf-8 -*-
"""ampacity-lab (mini): UI 组件包
=============================================

所有界面相关代码:
  - basic.py:      BasicPanel (主面板)
  - log_window.py: LogWindow (日志弹窗)
  - constants.py:  LEVEL_STYLE / LEVEL_ORDER (颜色/级别常量)
  - utils.py:      center_window (居中工具)

对外暴露:
  - BasicPanel (兼容老 from mini.ui_basic import BasicPanel)
"""
from __future__ import annotations

from .basic import BasicPanel

__all__ = ["BasicPanel"]
