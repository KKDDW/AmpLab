# -*- coding: utf-8 -*-
"""ampacity-lab (mini): AmpacityEngine (门面)
=============================================

只做组合, 不做具体业务。所有真实逻辑都在 engine/ 子包、backends/、optimizer/ 里。

设计原则:
  - 所有方法返回 Result (不再是 bool / dict / 抛异常的混搭)
  - 不暴露任何下划线属性 (无 _lock / _solver 等泄漏)
  - 配置 / 状态修改走 configure(**kw), 不暴露单独 setter
  - 锁通过 busy 属性 + try_acquire/release 公开方法暴露

外部接口 (向后兼容 + 升级):
  - start_engine(comsol_version, cores) -> Result
  - stop_engine()                        -> Result
  - load_mph(path)                       -> Result
  - inspect_mph(path=None)               -> Result
  - compute_ampacity(target_T, I_guess, ..., solver=None) -> Result
  - run_batch(file_list, ...)            -> Result[List[PointResult]]
  - request_stop()
  - busy                                 -> bool

新接口:
  - configure(target_study, current_param_name, temp_expression, temp_unit)
  - config_snapshot() / config_restore(**kw)  留给将来接 ConfigStore
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .backends import BackendProtocol, MphCompatBackend, MockBackend
from .utils.concurrency import ConcurrencyGate
from .engine import (
    AmpacitySolver,
    BatchRunner,
    ModelInspector,
    ModelLoader,
    PointResult,
    SessionManager,
)
from .utils.events import EventBus
from .utils.logger import get_logger
from .optimizer import MAX_CURRENT, MIN_CURRENT
from .utils.result import Result

log = get_logger(__name__)


class AmpacityEngine:
    """门面: 把 5 个小 class 串成用户感知的引擎"""

    def __init__(self, backend: Optional[BackendProtocol] = None) -> None:
        self._backend: BackendProtocol = backend or MphCompatBackend()
        self.bus: EventBus = EventBus()
        self._gate = ConcurrencyGate()

        self._session = SessionManager(self._backend, self.bus)
        self._loader = ModelLoader(self._backend, self.bus)
        self._inspector = ModelInspector(
            self._backend, self.bus, self._loader, self._gate
        )
        self._solver = AmpacitySolver(self._backend, self.bus)
        self._batch = BatchRunner(
            self._backend, self.bus, self._loader, self._solver, self._gate
        )

        log.info("AmpacityEngine 就绪 (backend=%s)",
                 type(self._backend).__name__)

    # ---- 公开: 并发状态 ----

    @property
    def busy(self) -> bool:
        """是否有重操作 (batch / inspect) 在跑"""
        return self._gate.busy

    def try_acquire(self) -> bool:
        """抢门; 给需要互斥的外部代码用"""
        return self._gate.try_acquire()

    def release(self) -> None:
        self._gate.release()

    # ---- 公开: 只读快照 (旧代码可能用到) ----

    @property
    def current_file(self) -> str:
        return self._loader.current_file

    @property
    def default_I(self) -> float:
        return self._loader.default_I

    @property
    def detected_studies(self) -> List[Dict[str, str]]:
        return self._inspector.detected_studies

    @property
    def detected_parameters(self) -> List[Dict[str, Any]]:
        return self._inspector.detected_parameters

    @property
    def detected_evaluations(self) -> List[Dict[str, str]]:
        return self._inspector.detected_evaluations

    @property
    def inspection(self) -> Dict[str, Any]:
        return self._inspector.inspection

    @property
    def tasks(self) -> List[PointResult]:
        return self._batch.tasks

    @property
    def is_running(self) -> bool:
        return self._batch.is_running

    @property
    def backend(self) -> BackendProtocol:
        return self._backend

    # ---- 公开: 配置 (solver 参数集中配置) ----

    def configure(
        self,
        target_study: Optional[str] = None,
        current_param_name: Optional[str] = None,
        temp_expression: Optional[str] = None,
        temp_unit: Optional[str] = None,
    ) -> Result:
        """集中设置 solver 全部参数; 不传的保持原值"""
        if target_study is not None:
            self._solver.target_study = target_study
        if current_param_name is not None:
            self._solver.current_param_name = current_param_name
        if temp_expression is not None:
            self._solver.temp_expression = temp_expression
        if temp_unit is not None:
            self._solver.temp_unit = temp_unit
        return Result.make_ok(
            target_study=self._solver.target_study,
            current_param_name=self._solver.current_param_name,
            temp_expression=self._solver.temp_expression,
            temp_unit=self._solver.temp_unit,
        )

    def config_snapshot(self) -> Dict[str, Any]:
        """取当前 solver 全部参数 (用于持久化到 ConfigStore)"""
        return {
            "target_study": self._solver.target_study,
            "current_param_name": self._solver.current_param_name,
            "temp_expression": self._solver.temp_expression,
            "temp_unit": self._solver.temp_unit,
        }

    # ---- 公开: 业务方法 (全部返 Result) ----

    def start_engine(self, comsol_version: str = "latest",
                     cores: Optional[int] = None) -> Result:
        ok = self._session.start(version=comsol_version, cores=cores)
        if not ok:
            return Result.make_fail("engine start failed", version=comsol_version)
        info = self._session.info
        return Result.make_ok(**info)

    def stop_engine(self) -> Result:
        self._loader.unload()
        self._session.stop()
        return Result.make_ok(stopped=True)

    def load_mph(self, file_path: str) -> Result:
        if not self._loader.load(file_path):
            return Result.make_fail(f"load failed: {file_path}")
        return Result.make_ok(
            path=file_path,
            default_I=self._loader.default_I,
        )

    def inspect_mph(self, file_path: Optional[str] = None) -> Result:
        if file_path is None:
            file_path = self._loader.current_file
        if not file_path:
            return Result.make_fail("no file specified")
        # Inspector 内部已经走 gate, 不用这里再抢
        data = self._inspector.inspect(file_path)
        return Result.from_dict(data)

    def inspect_many(self, file_paths: List[str]) -> "MultiInspection":
        """多文件检测, 一次性返回 MultiInspection (新 API)"""
        return self._inspector.inspect_many(file_paths)

    def compute_ampacity(
        self,
        target_T: float = 90.0,
        I_guess: float = 1000.0,
        tolerance: float = 0.05,
        max_iter: int = 15,
        task_id: int = 0,
        solver=None,
    ) -> Result:
        data = self._solver.compute_ampacity(
            target_T=target_T, I_guess=I_guess,
            tolerance=tolerance, max_iter=max_iter,
            task_id=task_id, solver=solver,
        )
        return Result.from_dict(data)

    def run_batch(
        self,
        file_list: List[str],
        static_groups: Optional[List[Dict]] = None,
        sweep_params: Optional[Dict[str, List]] = None,
        target_T: float = 90.0,
        tolerance: float = 0.05,
        initial_I: float = 800.0,
        method: str = "secant",
    ) -> Result:
        try:
            tasks = self._batch.run(
                file_list=file_list,
                static_groups=static_groups,
                sweep_params=sweep_params,
                target_T=target_T,
                tolerance=tolerance,
                initial_I=initial_I,
                method=method,
            )
        except Exception as e:
            log.exception("run_batch 异常")
            return Result.make_fail(f"run_batch exception: {e}")
        return Result.make_ok(tasks=tasks, count=len(tasks))

    def request_stop(self) -> None:
        self._batch.request_stop()


# ---- 工厂 ----

def make_mock_engine() -> AmpacityEngine:
    """快速构造 Mock 后端的引擎 (开发/单测)"""
    return AmpacityEngine(backend=MockBackend())
