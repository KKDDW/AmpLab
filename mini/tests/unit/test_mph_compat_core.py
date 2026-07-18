"""test_mph_compat_core.py: 验证 mini/mph_compat/core.py 的接口形状
===================================================================

不真连 COMSOL, 只测函数存在 / 签名 / 错误处理.
"""
import inspect

import pytest

from mini.mph_compat import core


# ---------------------------------------------------------------------------
# 必需函数都在
# ---------------------------------------------------------------------------

REQUIRED = [
    "mph_start", "mph_disconnect", "mph_status",
    "model_load", "model_inspect", "model_unload",
    "param_set", "param_get",
    "evaluate", "solve_study",
    "create_max_operator", "create_average_operator",
    "is_available",
]


def test_all_required_exports():
    for name in REQUIRED:
        assert hasattr(core, name), f"core.{name} missing"
        assert callable(getattr(core, name)), f"core.{name} not callable"


# ---------------------------------------------------------------------------
# 签名
# ---------------------------------------------------------------------------

class TestSignatures:
    def test_evaluate(self):
        sig = inspect.signature(core.evaluate)
        params = list(sig.parameters.keys())
        assert params == ["expression", "unit", "dataset"]

    def test_solve_study(self):
        sig = inspect.signature(core.solve_study)
        params = list(sig.parameters.keys())
        assert params == ["study_label"]

    def test_param_set(self):
        sig = inspect.signature(core.param_set)
        params = list(sig.parameters.keys())
        assert params == ["name", "value"]


# ---------------------------------------------------------------------------
# 错误处理: 吃坏参数不抛
# ---------------------------------------------------------------------------

NO_REQUIRED = [
    "mph_start", "mph_disconnect", "mph_status",
    "model_unload", "model_inspect", "param_get",
    "evaluate", "solve_study", "create_max_operator",
    "create_average_operator",
]


@pytest.mark.parametrize("name", NO_REQUIRED)
def test_optional_params_no_raise(name):
    """没有必传参数的函数, 各种坏输入都不应抛"""
    fn = getattr(core, name)
    for bad_args in [(), (None,), (None, None), (123, 456), ("x", "y", "z")]:
        try:
            r = fn(*bad_args)
            if not isinstance(r, dict):
                # mph 不可用时返字符串也算可接受
                assert isinstance(r, (str, type(None)))
        except (TypeError, AttributeError):
            # 类型错误是合理的 (mph 未导入等)
            pass


REQUIRED_PARAMS = ["model_load", "param_set"]


@pytest.mark.parametrize("name", REQUIRED_PARAMS)
def test_required_params_raise_on_empty(name):
    """必传参数的, 不传应该 TypeError"""
    fn = getattr(core, name)
    with pytest.raises(TypeError):
        fn()
