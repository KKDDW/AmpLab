# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 后端子包
=============================================

提供跟 COMSOL 通信的 BackendProtocol 接口 + 真 COMSOL 实现.

只有生产用的后端:
  - BackendProtocol: 抽象接口
  - MphCompatBackend: 真 COMSOL 适配 (调 mini.mph_compat.core)

MockBackend (测试用) 不在这里, 见 mini/tests/_mocks.py
"""
from .base import BackendProtocol
from .mph_compat import MphCompatBackend

__all__ = ["BackendProtocol", "MphCompatBackend"]
