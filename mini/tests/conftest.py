"""pytest fixtures shared by all tests
=============================================

放到 mini/tests/conftest.py, pytest 会自动加载.

可用 fixture:
    mock_engine    -> 离线 AmpacityEngine (MockBackend, 0.1s 启动)
    mph_files      -> 真实 .mph 文件路径列表 (test_only)
    tmp_log_dir    -> 临时日志目录
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import List

import pytest

# 让 mini.* 可 import (mini 已经是包, tests 在 mini 内部, 直接 import 即可)
from mini.utils import logger as L
from mini.engine_core import make_mock_engine
from mini.utils import ConfigStore, EventBus


# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _init_logging():
    """每个测试都确保 logging 已初始化, log 文件扔临时目录 (不污染)"""
    tmp = tempfile.mkdtemp(prefix="amp_test_")
    L.init_logging(log_dir=tmp, level=10, buffer_capacity=200)
    yield
    # 测试结束不删 tmp (留作 debug), 走 OS 自动清


@pytest.fixture
def tmp_log_dir(tmp_path) -> Path:
    """给单个测试用的临时日志目录"""
    d = tmp_path / "logs"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# 引擎 / mock
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_engine():
    """离线 AmpacityEngine, 用 MockBackend, 跑得快"""
    eng = make_mock_engine()
    eng.start_engine()
    yield eng
    eng.stop_engine()


@pytest.fixture
def event_bus() -> EventBus:
    """干净的事件总线"""
    return EventBus()


# ---------------------------------------------------------------------------
# 真实 .mph 文件 (e2e tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def mph_files() -> List[Path]:
    """项目里的真实测试 .mph 文件

    跳过的条件:
      - 文件夹不存在
      - 没有 .mph 文件
    跳过的测试用 pytest.skip() 处理
    """
    candidates = [
        r"D:\F\Pycharm\Python_Projects\ampacity_lab\AmpLab_2\Model",
        r"D:\F\Pycharm\Python_Projects\ampacity_lab\AmpLab_1\Model",
    ]
    files: List[Path] = []
    for c in candidates:
        d = Path(c)
        if d.exists():
            files.extend(sorted(d.glob("*.mph")))
    # 去重 (AmpLab_1/2 同名, 优先 AmpLab_2)
    seen = set()
    unique = []
    for f in files:
        if f.name not in seen:
            seen.add(f.name)
            unique.append(f)
    return unique


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config(tmp_path) -> ConfigStore:
    """临时配置文件, 测试结束自动删"""
    cfg_path = tmp_path / "config.json"
    return ConfigStore(path=str(cfg_path))
