# -*- coding: utf-8 -*-
"""ampacity-lab (mini): ConfigStore
=============================================

JSON 持久化的用户配置 (目标温度 / 寻优方法 / 文件路径记忆 / UI 状态等)。

设计:
  - 用 dot-path 取值, 例: store.get("compute.target_T", default=90.0)
  - set 时立即落盘 (debounce 留给调用方)
  - 文件不存在 -> 用 defaults
  - 写盘失败 -> 不抛, 只记 log, 内存里还能用

典型用法:
    store = ConfigStore()
    target = store.get("compute.target_T", 90.0)
    store.set("compute.target_T", 85.0)
    store.set("ui.last_dir", "C:/foo")
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Optional

from .logger import get_logger

log = get_logger(__name__)


# 默认配置 (第一次启动时落地到文件)
DEFAULT_CONFIG: dict = {
    "compute": {
        "target_T": 90.0,
        "tolerance": 0.05,
        "initial_I": 800.0,
        "method": "linear",     # 唯一支持: linear (regula falsi / 两点插值)
        "max_iter": 15,
    },
    "session": {
        "comsol_version": "latest",
        "cores": None,           # None = auto
    },
    "ui": {
        "last_open_dir": "",     # 上次打开的目录
        "geometry": "1000x700",
    },
    "log": {
        "level": "INFO",
        "buffer_capacity": 2000,
    },
    "solver": {
        "target_study": "研究 1",
        "current_param_name": "I",
        "temp_expression": "max(T, 1)",
        "temp_unit": "degC",     # target_T 是 °C, 让 COMSOL 直接返回 °C
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """把 override 合并进 base, 嵌套 dict 递归"""
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class ConfigStore:
    """JSON 配置存储"""

    def __init__(self, path: Optional[str] = None) -> None:
        if path is None:
            home = os.path.expanduser("~")
            path = os.path.join(home, ".ampacity_lab", "config.json")
        self._path = path
        self._lock = threading.Lock()
        self._data: dict = self._load()
        log.info("ConfigStore: %s (%d 顶层键)", self._path, len(self._data))

    # ---- 加载 / 保存 ----

    def _load(self) -> dict:
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                merged = _deep_merge(DEFAULT_CONFIG, raw)
                log.info("已加载配置: %s", self._path)
                return merged
        except Exception as e:
            log.warning("配置加载失败 (%s), 用默认值", e)
        # 首次启动, 落一份默认
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
            log.info("已写入默认配置: %s", self._path)
        except Exception as e:
            log.warning("默认配置写盘失败: %s", e)
        return json.loads(json.dumps(DEFAULT_CONFIG))  # 深拷贝

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning("配置写盘失败: %s", e)

    # ---- dot-path 读写 ----

    def get(self, key: str, default: Any = None) -> Any:
        """dot-path 取值, 例: get("compute.target_T", 90.0)"""
        with self._lock:
            cur: Any = self._data
            for part in key.split("."):
                if not isinstance(cur, dict) or part not in cur:
                    return default
                cur = cur[part]
            return cur

    def set(self, key: str, value: Any, *, persist: bool = True) -> None:
        """dot-path 赋值, 自动建中间层 dict; persist=False 只改内存"""
        with self._lock:
            parts = key.split(".")
            cur = self._data
            for part in parts[:-1]:
                if part not in cur or not isinstance(cur[part], dict):
                    cur[part] = {}
                cur = cur[part]
            cur[parts[-1]] = value
        if persist:
            self._save()

    def section(self, name: str) -> dict:
        """取整个 section (浅拷贝, 改它不会影响 store)"""
        with self._lock:
            return dict(self._data.get(name, {}))

    def reload(self) -> None:
        with self._lock:
            self._data = self._load()

    def snapshot(self) -> dict:
        """整体浅拷贝 (调试用)"""
        with self._lock:
            return dict(self._data)
