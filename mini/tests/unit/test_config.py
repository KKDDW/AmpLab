"""test_config.py: ConfigStore 持久化 + dot-path"""
import json
import os


class TestConfigStore:
    def test_default_load(self, tmp_config):
        # 默认值
        assert tmp_config.get("compute.target_T") == 90.0
        assert tmp_config.get("compute.method") == "linear"
        assert tmp_config.get("solver.temp_unit") == "degC"

    def test_set_and_get(self, tmp_config):
        tmp_config.set("compute.target_T", 85.0)
        assert tmp_config.get("compute.target_T") == 85.0

    def test_persistence(self, tmp_path):
        # 写一次, 再 load 一次
        from mini.utils.config import ConfigStore
        path = str(tmp_path / "cfg.json")

        c1 = ConfigStore(path=path)
        c1.set("compute.target_T", 88.5)
        c1.set("ui.last_open_dir", "C:/test")

        c2 = ConfigStore(path=path)
        assert c2.get("compute.target_T") == 88.5
        assert c2.get("ui.last_open_dir") == "C:/test"

    def test_dot_path_creates_intermediate(self, tmp_config):
        tmp_config.set("a.b.c.d", "deep")
        assert tmp_config.get("a.b.c.d") == "deep"

    def test_get_with_default(self, tmp_config):
        assert tmp_config.get("nonexistent.key", "fallback") == "fallback"

    def test_section(self, tmp_config):
        s = tmp_config.section("compute")
        assert "target_T" in s
        assert "method" in s
