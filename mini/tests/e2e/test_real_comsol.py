"""test_real_comsol.py: 真 COMSOL 端到端测试
================================================

跳过条件:
  - 没找到 .mph 文件
  - mph 库不可用

跑法:
  pytest mini/tests/e2e/test_real_comsol.py -v

或显式指定文件:
  pytest mini/tests/e2e/test_real_comsol.py::test_one_file -v \\
    --mph "D:\\F\\...\\顶管2回_app.mph"
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# 共享 helper
# ---------------------------------------------------------------------------

def _run_one(engine, mph_path, target_T=90.0, tolerance=0.5, max_iter=15):
    """跑单个文件, 返结果摘要"""
    print(f"\n  >> {mph_path.name}")

    # load
    t0 = time.time()
    r = engine.load_mph(str(mph_path))
    assert r.ok, f"load_mph failed: {r.error}"
    t_load = time.time() - t0
    default_I = r.data.get("default_I", 0)
    print(f"     load:    {t_load:.1f}s  default_I={default_I}A")

    # inspect
    t0 = time.time()
    r = engine.inspect_mph(str(mph_path))
    assert r.ok, f"inspect_mph failed: {r.error}"
    t_inspect = time.time() - t0
    n_p = len(r.data.get("parameters", []))
    print(f"     inspect: {t_inspect:.1f}s  params={n_p}")

    # 用 default_I 做 bracket
    I_low = max(50, default_I - 200)
    I_high = min(5000, default_I + 200)

    # solve
    t0 = time.time()
    r = engine.compute_ampacity(
        target_T=target_T, I_low=I_low, I_high=I_high,
        tolerance=tolerance, max_iter=max_iter, method="linear",
    )
    assert r.ok, f"compute failed: {r.error}"
    t_solve = time.time() - t0

    I_final = r.data.get("final_I")
    T_final = r.data.get("final_T")
    converged = r.data.get("converged")
    iters = r.data.get("iterations")
    err = abs(T_final - target_T) if T_final else 999
    print(f"     solve:   {t_solve:.1f}s  I={I_final:.2f}A T={T_final:.2f}°C "
          f"err={err:.3f} iters={iters} converged={converged}")

    # 断言
    assert I_final is not None
    assert 10 < I_final < 5000, f"I_final 超出合理范围: {I_final}"
    assert err < tolerance * 2, f"温度误差过大: err={err:.3f}, tol*2={tolerance*2}"

    return {
        "I": I_final, "T": T_final, "err": err,
        "iters": iters, "converged": converged,
        "load_s": t_load, "inspect_s": t_inspect, "solve_s": t_solve,
    }


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------

def test_all_files(mph_files):
    """跑所有找到的 .mph 文件"""
    if not mph_files:
        pytest.skip("没找到 .mph 测试文件, 跳过 e2e")
        return
    print(f"\n找到 {len(mph_files)} 个测试文件: "
          f"{[f.name for f in mph_files]}")

    from mini.engine_core import AmpacityEngine
    eng = AmpacityEngine()
    if not eng._backend.available:
        pytest.skip("mph 库不可用, 跳过 e2e")
        return

    t0 = time.time()
    r = eng.start_engine(comsol_version="latest")
    if not r.ok:
        pytest.skip(f"COMSOL 启动失败: {r.error}")
        return
    print(f"\n  start: {time.time() - t0:.1f}s  COMSOL "
          f"{r.data.get('version')} / {r.data.get('cores')} 核")

    try:
        for f in mph_files:
            r = _run_one(eng, f)
            assert r["converged"], f"{f.name} 未收敛"
    finally:
        eng.stop_engine()


@pytest.mark.parametrize("filename", [
    "顶管2回_app.mph",
    "定向钻2回_app.mph",
])
def test_specific_file(filename, mph_files):
    """指定文件单独跑 (参数化)"""
    target = next((f for f in mph_files if f.name == filename), None)
    if target is None:
        pytest.skip(f"文件 {filename} 不存在")
        return

    from mini.engine_core import AmpacityEngine
    eng = AmpacityEngine()
    if not eng._backend.available:
        pytest.skip("mph 库不可用")
        return

    r = eng.start_engine(comsol_version="latest")
    if not r.ok:
        pytest.skip(f"启动失败: {r.error}")
        return

    try:
        result = _run_one(eng, target)
        assert result["converged"]
    finally:
        eng.stop_engine()
