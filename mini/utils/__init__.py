"""ampacity-lab (mini): 通用工具子包
=============================================

可复用进其他项目的基础组件. 跟 ampacity 业务无关.

- result       统一返回类型 (Result / make_ok / make_fail)
- concurrency  非阻塞并发门 (ConcurrencyGate, 支持重入)
- config       JSON 配置持久化 (ConfigStore, dot-path 访问)
- events       简单事件总线 (EventBus, 线程安全)
- inspection   多份数据求交集 (MultiInspection / SectionInfo, 注册制)
- logger       统一日志 (get_logger / LogStore / RingBufferHandler)
"""
from .result import Result
from .concurrency import ConcurrencyGate
from .config import ConfigStore
from .events import EventBus
from .inspection import MultiInspection, SectionInfo
from .logger import (
    get_logger,
    init_logging,
    Store,
    RingBufferHandler,
)

__all__ = [
    "Result",
    "ConcurrencyGate",
    "ConfigStore",
    "EventBus",
    "MultiInspection",
    "SectionInfo",
    "get_logger",
    "init_logging",
    "Store",
    "RingBufferHandler",
]
