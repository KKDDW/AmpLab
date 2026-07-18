"""test_optimizer.py: 验证 iterative_interpolation_method 寻优正确性
====================================================================

不依赖 COMSOL, 纯数学测试.
"""
import math
import pytest

from mini.optimizer import (
    DEFAULT_TOL,
    MAX_CURRENT,
    MIN_CURRENT,
    iterative_interpolation_method,
)


# ---------------------------------------------------------------------------
# iterative_interpolation_method
# ---------------------------------------------------------------------------

class TestIterativeInterpolation:
    """用 f(I) = a*I + b 这种已知反函数的简单模型, 验收敛"""

    def test_linear_function(self):
        # T = 0.05*I + 25, 已知反函数 I = (T-25)/0.05
        # 找 T=90 -> I=1300
        f = lambda I: 0.05 * I + 25.0
        r = iterative_interpolation_method(
            f, target=90.0,
            x_guess=500.0,
            tolerance=0.1, max_iter=20,
        )
        assert r["success"] is True
        assert r["converged"] is True
        assert r["final_x"] == pytest.approx(1300.0, abs=0.5)
        assert r["final_y"] == pytest.approx(90.0, abs=0.1)

    def test_quadratic_function(self):
        # T = 25 + 0.05*I + 1e-5*I^2, 解析解 I ≈ 1070.71
        f = lambda I: 25.0 + 0.05 * I + 1e-5 * I * I
        r = iterative_interpolation_method(
            f, target=90.0,
            x_guess=500.0,
            tolerance=0.05, max_iter=20,
        )
        assert r["success"] is True
        assert r["converged"] is True
        # 解析解: I = (-0.05 + sqrt(0.0025 + 0.0026)) / 0.00002 = 1070.71
        true_I = (-0.05 + math.sqrt(0.0025 + 0.0026)) / 0.00002
        assert r["final_x"] == pytest.approx(true_I, abs=1.0)

    def test_already_converged_at_guess(self):
        """x_guess 处已经命中 target -> 1 次迭代 (只算 1 次)"""
        f = lambda I: 0.05 * I + 25.0
        # I=1300 时 T=90, 第一次试探直接命中
        r = iterative_interpolation_method(
            f, target=90.0,
            x_guess=1300.0,
            tolerance=0.1, max_iter=10,
        )
        assert r["converged"] is True
        assert r["iterations"] == 1
        assert r["final_x"] == pytest.approx(1300.0, abs=0.1)

    def test_initial_solve_fails(self):
        """func 一开始就抛 -> 返 fail, x/y 不是 None (有 fallback)"""
        def f(I):
            raise RuntimeError("solver died")
        r = iterative_interpolation_method(
            f, target=90.0,
            x_guess=500.0,
            tolerance=0.1, max_iter=10,
        )
        assert r["success"] is False
        assert r["final_x"] is not None  # fallback, 不是 None
        assert r["final_y"] is not None
        assert "solver died" in r["error"]

    def test_boundary_protection_guess_above_max(self):
        """x_guess 超过 MAX_CURRENT -> 自动 clamp 到边界"""
        f = lambda I: 0.05 * I + 25.0
        # guess 设 9999, 应该被 clamp 到 MAX_CURRENT
        r = iterative_interpolation_method(
            f, target=90.0,
            x_guess=9999.0,
            tolerance=0.1, max_iter=20,
        )
        # 不崩, 收敛到正确解
        assert r["final_x"] is not None
        assert MIN_CURRENT <= r["final_x"] <= MAX_CURRENT
        assert r["final_y"] == pytest.approx(90.0, abs=0.2)

    def test_boundary_protection_guess_below_min(self):
        """x_guess 低于 MIN_CURRENT -> 自动 clamp"""
        f = lambda I: 0.05 * I + 25.0
        r = iterative_interpolation_method(
            f, target=90.0,
            x_guess=1.0,
            tolerance=0.1, max_iter=20,
        )
        assert r["final_x"] is not None
        assert MIN_CURRENT <= r["final_x"] <= MAX_CURRENT

    def test_max_iter_returns_best(self):
        """max_iter 不够 -> success=True, converged=False, 返历史最优"""
        # 用 max_iter=1, 只够算第 1 步初始试探, 必不收敛
        f = lambda I: 0.05 * I + 25.0
        r = iterative_interpolation_method(
            f, target=90.0,
            x_guess=500.0,
            tolerance=0.01, max_iter=1,
        )
        assert r["success"] is True
        assert r["converged"] is False
        # 没收敛, 但至少有个 best result
        assert r["final_x"] is not None
        assert "max iter" in r["error"].lower()

    def test_history_populated(self):
        """每次计算都进 history"""
        f = lambda I: 0.05 * I + 25.0
        r = iterative_interpolation_method(
            f, target=90.0,
            x_guess=500.0,
            tolerance=0.1, max_iter=10,
        )
        # history 至少 2 个点 (初始 + ±10% 第 2 试探)
        assert len(r["history"]) >= 2
        for h in r["history"]:
            assert "x" in h and "y" in h and "error" in h
