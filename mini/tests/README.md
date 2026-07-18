# mini/tests/

ampacity-lab mini 项目的测试目录。

## 结构

```
tests/
├── __init__.py
├── conftest.py              # 共享 fixtures (mock_engine, mph_files, tmp_config)
├── README.md
├── unit/                    # 单元测试, 不依赖 COMSOL, 跑得快 (< 5秒)
│   ├── test_optimizer.py    # regula_falsi 算法正确性
│   ├── test_result.py       # Result 数据类
│   ├── test_concurrency.py  # ConcurrencyGate 互斥 + 重入
│   ├── test_config.py       # ConfigStore 持久化
│   ├── test_mph_compat_core.py  # mcp 函数接口形状
│   └── test_inspector.py    # mph_backend 真实 dict 格式适配
├── e2e/                     # 端到端, 真 COMSOL, 跑得慢 (每文件 ~30秒)
│   └── test_real_comsol.py  # 4 个真实 .mph 文件跑通
└── fixtures/                # 测试用小文件 (暂空, 未来可放 sample.mph)
```

## 跑法

```bash
# 1) 装 pytest
pip install pytest

# 2) 跑所有单元测试 (快, 不需要 COMSOL)
pytest mini/tests/unit -v

# 3) 跑 e2e (需要真 COMSOL + .mph 文件)
pytest mini/tests/e2e -v -s

# 4) 跑全部
pytest mini/tests -v
```

## Fixtures (conftest.py)

| name | 说明 | scope |
|---|---|---|
| `mock_engine` | 离线 AmpacityEngine, 用 MockBackend | function |
| `event_bus` | 干净的事件总线 | function |
| `tmp_log_dir` | 临时日志目录 | function |
| `tmp_config` | 临时 ConfigStore | function |
| `mph_files` | 真实 .mph 文件列表 (找不到自动 skip) | session |

## 加新测试

1. **单元测试** → `mini/tests/unit/test_xxx.py`，文件名 `test_` 开头，pytest 自动收集
2. **e2e 测试** → `mini/tests/e2e/test_xxx.py`
3. **fixture** → `mini/tests/conftest.py` 或 `mini/tests/unit/conftest.py`

## pytest.ini (可选)

加到 `pyproject.toml` 或项目根 `pytest.ini`:

```ini
[pytest]
testpaths = mini/tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```
