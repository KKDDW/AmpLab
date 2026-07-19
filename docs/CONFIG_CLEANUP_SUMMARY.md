# 配置清理总结

## 已完成的修复

### 1. 删除多余的硬编码
✅ **settings_panel.py:90** - 删除了 `self._widgets["study_node"].set("等待检测...")`
   - 改为依赖后续的 `load_from_config()` 自动设置
   - 现在只有一个地方控制初始值：`config.py`

### 2. 统一 tolerance 默认值为 0.02
✅ **solver.py:240** - `tolerance: float = 0.05` → `0.02`
✅ **engine_core.py:197** - `tolerance: float = 0.05` → `0.02`
✅ **engine_core.py:215** - `run_batch` 的 `tolerance: float = 0.05` → `0.02`
✅ **batch.py:92** - `tolerance: float = 0.05` → `0.02`

现在所有地方都与 `config.py:35` 和 `optimizer.py:23` 保持一致。

### 3. 恢复 solver 字段的必要初始值
✅ **solver.py:94-98** - 恢复为：
   ```python
   self.target_study: str = "等待检测"
   self.current_param_name: str = "I"
   self.temp_expression: str = "max(T, 1)"
   ```
   - 这些是必要的，用于 `config_snapshot()` 的 fallback
   - 与 `config.py` 的 `DEFAULT_CONFIG` 保持一致

---

## 最终配置架构

### 唯一配置源
```python
# config.py DEFAULT_CONFIG（第32-58行）
"compute": {
    "target_T": 90.0,
    "tolerance": 0.02,
    "initial_I": 800.0,
    "method": "linear",
    "max_iter": 15,
},
"solver": {
    "target_study": "等待检测",
    "current_param_name": "I",
    "temp_expression": "max(T, 1)",
    "temp_unit": "degC",
}
```

### 配置流程
```
1. 首次启动
   config.py DEFAULT_CONFIG
        ↓
   写入 ~/.../config.json
        ↓
   dispatcher._load_persisted_config()
        ↓
   engine.configure() 设置到 solver
        ↓
   UI.load_from_config() 显示

2. 用户修改 UI
   UI 输入变化
        ↓
   config.set() 立即保存
        ↓
   config.json 更新
        ↓
   下次启动生效

3. 检测模型后
   dispatcher._on_inspect()
        ↓
   ui.update_study_nodes(["研究 1", ...])
        ↓
   自动选择第一个
        ↓
   config.set("solver.target_study", nodes[0])
        ↓
   保存到 config.json
```

### 防御性 fallback（合理且必要）
所有这些都是**必要的**，不是多余的：

1. **dispatcher.py** - `config.get(key, fallback)`
   - 防止 config 文件损坏或缺失字段

2. **settings_panel.py** - `config.get(key, fallback)`
   - 防止 config 读取失败

3. **solver.py** - 字段初始值
   - 用于 `engine.config_snapshot()` 的 fallback
   - 当 `dispatcher._load_persisted_config()` 中 config 没有值时使用

4. **函数签名默认值** - 所有函数参数
   - Python 语法要求
   - 最后一道防线

---

## 配置值对照表

| 配置项 | config.py | solver.py | 函数签名 | UI fallback | 状态 |
|--------|-----------|-----------|----------|-------------|------|
| target_study | "等待检测" | "等待检测" | - | "等待检测" | ✅ 统一 |
| target_T | 90.0 | - | 90.0 | 90.0 | ✅ 统一 |
| tolerance | 0.02 | - | 0.02 | 0.02 | ✅ 已修复 |
| initial_I | 800.0 | - | - | 800.0 | ✅ 统一 |
| max_iter | 15 | - | 15 | - | ✅ 统一 |
| current_param_name | "I" | "I" | - | - | ✅ 统一 |
| temp_expression | "max(T, 1)" | "max(T, 1)" | - | - | ✅ 统一 |
| temp_unit | "degC" | "degC" | - | - | ✅ 统一 |

---

## 特殊说明

### I_guess vs initial_I
- **I_guess**: `compute_ampacity()` 函数参数，默认 1000.0（算法内部用）
- **initial_I**: config 中的用户配置，默认 800.0（UI 显示，传给 batch）
- **关系**: dispatcher 读取 config 的 `initial_I`，传给 batch，batch 再传给 solver 的 `I_guess`
- **结论**: 两者用途不同但会关联，不是重复配置

### "等待检测" vs "等待检测..."
- **配置层**: `"等待检测"` (无点) - 存储在 config.json
- **UI 层**: `"等待检测..."` (3个点) - 显示给用户看
- **转换逻辑**: 
  ```python
  val = config.get("solver.target_study", "等待检测")  # 读配置
  if val == "等待检测":  # 判断是否默认值
      ui.set("等待检测...")  # 显示时加3个点
  ```
- **结论**: 这是合理的显示层映射，不是不一致

---

## 修改文件清单

1. ✅ `mini/ui/settings_panel.py` - 删除第90行硬编码
2. ✅ `mini/engine/solver.py` - 修复 tolerance 为 0.02，恢复字段初始值
3. ✅ `mini/engine_core.py` - 修复两处 tolerance 为 0.02
4. ✅ `mini/engine/batch.py` - 修复 tolerance 为 0.02
5. ✅ 创建文档 `CONFIG_FLOW_ANALYSIS.md` 和 `CONFIG_CLEANUP_SUMMARY.md`

---

## 验证清单

启动程序后检查：
- [ ] UI 研究节点显示 "等待检测..."
- [ ] UI 目标温度显示 90.0
- [ ] UI 容差显示 0.02
- [ ] UI 初始探测显示 800.0
- [ ] 修改任一参数 → 关闭重启 → 值被保留
- [ ] 删除 config.json → 重启 → 恢复默认值
- [ ] 检测模型后 → 研究节点自动更新
