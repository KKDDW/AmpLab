"""test_inspector.py: 验证 inspector 适配 mph_backend 真实返回格式
====================================================================

mph_backend.model_inspect 真实返回:
  parameters: dict  {name: value}      <- key 是 name
  studies:    list[str]                 <- 元素是 tag
  datasets:   list[str]                 <- evaluations 字段实际叫 datasets

这些用 fake 数据验证 _adapt 能正确处理.
"""
import pytest

from mini.engine.inspector import ModelInspector
from mini.utils.events import EventBus
from mini.utils.concurrency import ConcurrencyGate
from mini.backends import MockBackend


class FakeLoader:
    current_file = "fake.mph"

    def load(self, p):
        return True


# mph 真实格式: parameters 是 dict
FAKE_INSPECT_DICT = {
    "success": True,
    "model": {
        "name": "demo",
        "file": "fake.mph",
        "comsol_version": "6.4",
        "parameters": {"I": 807.5, "T_amb": 25.0, "sigma": 5.7e7},
        "studies": ["std1", "std2"],
        "datasets": ["dset1", "dset2"],
        "materials": ["Copper", "XLPE"],
        "physics": ["Heat"],
    },
}


def _make_inspector():
    return ModelInspector(
        backend=MockBackend(),
        bus=EventBus(),
        loader=FakeLoader(),
        gate=ConcurrencyGate(),
    )


class TestAdaptDictFormat:
    def test_parameters_dict_to_list(self):
        ins = _make_inspector()
        adapted = ins._adapt(FAKE_INSPECT_DICT)
        assert adapted["success"] is True
        assert len(adapted["parameters"]) == 3
        names = {p["name"] for p in adapted["parameters"]}
        assert names == {"I", "T_amb", "sigma"}
        # I 的 value 是 807.5
        i_param = next(p for p in adapted["parameters"] if p["name"] == "I")
        assert i_param["value"] == 807.5

    def test_studies_list_to_dicts(self):
        ins = _make_inspector()
        adapted = ins._adapt(FAKE_INSPECT_DICT)
        assert len(adapted["studies"]) == 2
        assert adapted["studies"][0] == {"name": "std1", "tag": "std1"}

    def test_datasets_become_evaluations(self):
        ins = _make_inspector()
        adapted = ins._adapt(FAKE_INSPECT_DICT)
        # mph 没 evaluations 字段, 用 datasets 顶
        assert len(adapted["evaluations"]) == 2
        assert adapted["evaluations"][0]["name"] == "dset1"

    def test_materials_kept(self):
        ins = _make_inspector()
        adapted = ins._adapt(FAKE_INSPECT_DICT)
        assert adapted["materials"] == ["Copper", "XLPE"]
        assert adapted["physics"] == ["Heat"]

    def test_suggested_current_param(self):
        ins = _make_inspector()
        adapted = ins._adapt(FAKE_INSPECT_DICT)
        # 有 I -> 建议 I
        assert adapted["suggested_current_param"] == "I"

    def test_suggested_no_I(self):
        ins = _make_inspector()
        d = {**FAKE_INSPECT_DICT,
             "model": {**FAKE_INSPECT_DICT["model"],
                       "parameters": {"T_amb": 25, "V": 220}}}
        adapted = ins._adapt(d)
        # 没有 I, 字母序第一个
        assert adapted["suggested_current_param"] in ("T_amb", "V")


class TestAdaptListFormat:
    """兼容旧格式: parameters 是 list[dict]"""

    def test_list_of_dicts(self):
        ins = _make_inspector()
        old_format = {
            "success": True,
            "model": {
                "parameters": [
                    {"name": "I", "value": 800, "description": "current"},
                    {"name": "T_amb", "value": 25, "description": ""},
                ],
                "studies": [{"name": "研究1", "tag": "std1"}],
            },
        }
        adapted = ins._adapt(old_format)
        assert len(adapted["parameters"]) == 2
        i_param = next(p for p in adapted["parameters"] if p["name"] == "I")
        assert i_param["value"] == 800
        assert adapted["studies"][0]["name"] == "研究1"
