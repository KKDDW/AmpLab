"""test_optimizer.py: 验证 regula_falsi_method 寻优正确性
=============================================================

不依赖 COMSOL, 纯数学测试.
"""
import math
import pytest

from mini.optimizer import (
    DEFAULT_TOL,
    MAX_CURRENT,
    MIN_CURRENT,
    convert_temp_value,
    regula_falsi_method,
)


# ---------------------------------------------------------------------------
# 温度单位转换
# ---------------------------------------------------------------------------

class TestConvertTemp:
    def test_k_to_c(self):
        assert convert_temp_value(363.15, "K", "degC") == pytest.approx(90.0)

    def test_c_to_k(self):
        assert convert_temp_value(90.0, "degC", "K") == pytest.approx(363.15)

    def test_same_unit(self):
        assert convert_temp_value(42.0, "K", "K") == 42.0
        assert convert_temp_value(42.0, "degC", "degC") == 42.0

    def test_alias(self):
        # 别名都认
        assert convert_temp_value(363.15, "kelvin", "°C") == pytest.approx(90.0)
        assert convert_temp_value(363.15, "k", "C") == pytest.approx(90.0)

    def test_unknown_unit(self):
        # 未知单位返原值
        assert convert_temp_value(42.0, "xyz", "K") == 42.0


# ---------------------------------------------------------------------------
# regula_falsi_method
# ---------------------------------------------------------------------------

class TestRegulaFalsi:
    """用 f(I) = a*I + b 这种已知反函数的简单模型, 验收敛"""

    def test_linear_function(self):
        # T = 0.05*I + 25, 已知反函数 I = (T-25)/0.05
        # 找 T=90 -> I=1300
        f = lambda I: 0.05 * I + 25.0
        r = regula_falsi_method(
            f, target=90.0,
            x_low=500.0, x_high=2000.0,
            tolerance=0.1, max_iter=20,
        )
        assert r["success"] is True
        assert r["converged"] is True
        assert r["final_x"] == pytest.approx(1300.0, abs=0.5)
        assert r["final_y"] == pytest.approx(90.0, abs=0.1)

    def test_quadratic_function(self):
        # T = 25 + 0.05*I + 1e-5*I^2, 解析解 I ≈ 1070.71
        f = lambda I: 25.0 + 0.05 * I + 1e-5 * I * I
        r = regula_falsi_method(
            f, target=90.0,
            x_low=500.0, x_high=1500.0,
            tolerance=0.05, max_iter=20,
        )
        assert r["success"] is True
        assert r["converged"] is True
        # 解析解: I = (-0.05 + sqrt(0.0025 + 0.0026)) / 0.00002 = 1070.71
        true_I = (-0.05 + math.sqrt(0.0025 + 0.0026)) / 0.00002
        assert r["final_x"] == pytest.approx(true_I, abs=1.0)

    def test_target_outside_bracket(self):
        """target 不在 bracket 内 -> 报错"""
        f = lambda I: 0.05 * I + 25.0
        # I=500 时 T=50, I=1500 时 T=100, target=200 超出
        r = regula_falsi_method(
            f, target=200.0,
            x_low=500.0, x_high=1500.0,
            tolerance=0.1, max_iter=10,
        )
        assert r["success"] is False
        assert r["converged"] is False
        assert "outside" in r["error"].lower()

    def test_degenerate_y_diff(self):
        """f(x_low) ≈ f(x_high) -> 退化, 走中点"""
        # f 几乎不随 I 变
        f = lambda I: 50.0  # 常数
        r = regula_falsi_method(
            f, target=50.0,    # target=50 跟 f 一致, 边界立刻收敛
            x_low=500.0, x_high=1500.0,
            tolerance=0.1, max_iter=10,
        )
        # 边界收敛 (y_low 和 y_high 跟 target 差 0)
        assert r["converged"] is True

    def test_already_converged_at_boundary(self):
        """x_low 处已经收敛 -> 0 次迭代"""
        f = lambda I: 0.05 * I + 25.0
        # I=1300 时 T=90, 直接命中
        r = regula_falsi_method(
            f, target=90.0,
            x_low=1300.0, x_high=1500.0,
            tolerance=0.1, max_iter=10,
        )
        assert r["converged"] is True
        assert r["iterations"] == 0
        assert r["final_x"] == 1300.0

    def test_initial_solve_fails(self):
        """func 一开始就抛 -> 返 fail"""
        def f(I):
            raise RuntimeError("solver died")
        r = regula_falsi_method(
            f, target=90.0,
            x_low=500.0, x_high=1500.0,
            tolerance=0.1, max_iter=10,
        )
        assert r["success"] is False
        assert "initial solve failed" in r["error"]

    def test_boundary_protection(self):
        """外推到边界外 -> 自动回中点 (不崩)"""
        f = lambda I: 0.05 * I + 25.0
        # 用正常 bracket, 但 I_high 设很大, 故意让 x_new 算出 > MAX_CURRENT
        # 这时算法应该自动截断到 MAX_CURRENT (或回中点)
        r = regula_falsi_method(
            f, target=90.0,
            x_low=100.0, x_high=5000.0,
            tolerance=0.1, max_iter=20,
        )
        # 不崩, 有结果, 且在范围内
        assert r["final_x"] is not None
        assert MIN_CURRENT <= r["final_x"] <= MAX_CURRENT
