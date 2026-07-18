"""test_result.py: Result 数据类 + 工厂方法 + 互转"""
import pytest

from mini.utils.result import Result


class TestResult:
    def test_make_ok(self):
        r = Result.make_ok(value=42, name="x")
        assert r.ok is True
        assert r.success is True
        assert r.data == {"value": 42, "name": "x"}
        assert r.error == ""
        # bool
        assert bool(r) is True
        # 单个 value 时, .value 拿第一个; 多个时返整个 dict
        r_single = Result.make_ok(only=99)
        assert r_single.value == 99

    def test_make_fail(self):
        r = Result.make_fail("oops", code=-1)
        assert r.ok is False
        assert r.error == "oops"
        assert r.data == {"code": -1}
        assert bool(r) is False

    def test_frozen(self):
        r = Result.make_ok(x=1)
        with pytest.raises(Exception):  # FrozenInstanceError
            r.success = False

    def test_from_dict(self):
        # 兼容 comsol_ampacity_mcp 风格
        d = {"success": True, "value": 90.0, "temperature": "K"}
        r = Result.from_dict(d)
        assert r.ok
        # data 里 success / error 之外的全部保留
        assert r.data == {"value": 90.0, "temperature": "K"}

    def test_from_dict_fail(self):
        d = {"success": False, "error": "boom"}
        r = Result.from_dict(d)
        assert not r.ok
        assert r.error == "boom"

    def test_from_dict_garbage(self):
        r = Result.from_dict("not a dict")
        assert not r.ok

    def test_to_dict_roundtrip(self):
        r = Result.make_ok(a=1, b=2)
        d = r.to_dict()
        assert d == {"success": True, "a": 1, "b": 2}
        r2 = Result.from_dict(d)
        assert r2.ok
        assert r2.data == {"a": 1, "b": 2}
