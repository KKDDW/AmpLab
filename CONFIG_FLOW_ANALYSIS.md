# 配置流完整分析

## 问题：太多地方有相同的配置默认值

### 当前状态（有问题）

| 位置 | 值 | 作用 | 是否必要 |
|------|-----|------|---------|
| `config.py:53` | `"等待检测"` | 配置文件默认值 | ✅ **唯一真实源** |
| `solver.py:94` | `"等待检测"` | Solver 初始值 | ✅ 必要（用于 config_snapshot fallback） |
| `settings_panel.py:38` | `["等待检测..."]` | UI 下拉框选项 | ✅ 必要（UI 显示） |
| `settings_panel.py:90` | `.set("等待检测...")` | UI 初始显示 | ❌ **冗余**，应从 config 读取 |
| `settings_panel.py:143` | `fallback "等待检测"` | config.get fallback | ✅ 必要（防御性） |
| `settings_panel.py:144` | `!= "等待检测"` | 判断逻辑 | ✅ 必要 |
| `settings_panel.py:152` | `.set("等待检测...")` | else 分支 | ✅ 必要 |
| `settings_panel.py:234` | `.set("等待检测...")` | 清空时恢复 | ✅ 必要 |

### 核心问题

**UI 初始化时硬编码了值（第90行）**：
```python
self._widgets["study_node"].set("等待检测...")  # ❌ 不应该硬编码
```

应该改为从 config 读取，这样修改 config.py 就能生效。

---

## 配置值不一致问题

### 1. "等待检测" vs "等待检测..."

- **配置层** (`config.py`, `solver.py`): `"等待检测"` (无点)
- **UI 层** (`settings_panel.py`): `"等待检测..."` (3个点)

**原因**：UI 显示更友好，需要视觉提示。

**问题**：第 143-144 行的判断逻辑不匹配：
```python
val = self.config.get("solver.target_study", "等待检测")  # 返回 "等待检测"
if val and val != "等待检测":  # 判断是否等于 "等待检测"
    ...
else:
    self._widgets["study_node"].set("等待检测...")  # 设置 "等待检测..."
```

**这个逻辑是对的**！因为：
- 配置中存储 `"等待检测"`（无点）
- UI 显示 `"等待检测..."`（有点）
- 两者需要映射转换

---

## 修复方案

### 修复1：删除 settings_panel.py:90 的硬编码

UI 初始化时不要硬编码，应该在后面调用 `load_from_config()` 时设置。

### 修复2：统一配置优先级

```
优先级（从高到低）：
1. config.json 用户配置文件
2. config.py DEFAULT_CONFIG
3. solver.py 初始值（作为 config_snapshot 的 fallback）
4. 函数签名默认值（最后防线）
```

### 修复3：创建配置常量

在 `utils/config.py` 中定义：
```python
# UI 显示映射
CONFIG_TO_UI_MAPPING = {
    "solver.target_study": {
        "等待检测": "等待检测...",  # 配置值 -> UI 显示值
    }
}
```

---

## 实际显示流程

### 启动时

```
1. settings_panel.__init__()
   - 第90行: 硬编码设置 "等待检测..." ❌ 应删除

2. settings_panel.__init__() 最后
   - 第71行: self.load_from_config()
   
3. load_from_config()
   - 第143行: val = config.get("solver.target_study", "等待检测")
   - 第144行: if val != "等待检测": ... else: set("等待检测...")
   
结果：UI 显示 "等待检测..." ✅
```

### 检测后更新

```
1. dispatcher._on_inspect() 完成
   
2. ui.update_study_nodes(["研究 1", "研究 2"])

3. settings_panel.update_study_nodes()
   - 第238行: _widgets["study_node"]["values"] = nodes
   - 第241行: _widgets["study_node"].set(nodes[0])
   - 第245行: config.set("solver.target_study", nodes[0])
   
结果：UI 显示 "研究 1"，配置中保存 "研究 1" ✅
```

---

## 其他配置项检查

### target_T (目标温度)

| 位置 | 值 | 必要性 |
|------|-----|--------|
| `config.py:34` | 90.0 | ✅ 唯一源 |
| `dispatcher.py:311` | fallback 90.0 | ✅ 防御 |
| `engine_core.py:195` | 函数签名 90.0 | ✅ 防御 |
| `solver.py:238` | 函数签名 90.0 | ✅ 防御 |
| `settings_panel.py:155` | fallback 90.0 | ✅ 防御 |

✅ **所有值一致，无问题**

### tolerance (容差)

| 位置 | 值 | 必要性 |
|------|-----|--------|
| `config.py:35` | 0.02 | ✅ 唯一源 |
| `optimizer.py:23` | 0.02 | ✅ 算法常量 |
| `engine_core.py:197` | 0.02 | ✅ 已修复 |
| `solver.py:240` | 0.02 | ✅ 已修复 |
| `settings_panel.py:160` | fallback 0.02 | ✅ 防御 |

✅ **已修复，所有值一致**

### initial_I (初始电流)

| 位置 | 值 | 必要性 |
|------|-----|--------|
| `config.py:36` | 800.0 | ✅ 唯一源 |
| `dispatcher.py:318` | fallback 800.0 | ✅ 防御 |
| `settings_panel.py:165` | fallback 800.0 | ✅ 防御 |

✅ **所有值一致，无问题**

### current_param_name (电流参数名)

| 位置 | 值 | 必要性 |
|------|-----|--------|
| `config.py:54` | "I" | ✅ 唯一源 |
| `solver.py:96` | "I" | ✅ 必要（config_snapshot fallback） |

✅ **所有值一致，无问题**

### temp_expression (温度表达式)

| 位置 | 值 | 必要性 |
|------|-----|--------|
| `config.py:55` | "max(T, 1)" | ✅ 唯一源 |
| `solver.py:98` | "max(T, 1)" | ✅ 必要（config_snapshot fallback） |

✅ **所有值一致，无问题**

---

## 总结

### 需要修复的问题

1. ❌ **settings_panel.py:90** - 删除硬编码的初始值
   - 理由：应该通过 `load_from_config()` 设置，而不是硬编码

### 已经正确的设计

1. ✅ **config.py** - 唯一配置源
2. ✅ **solver.py** - 必要的初始值（用于 config_snapshot fallback）
3. ✅ **防御性 fallback** - 所有 `config.get(key, fallback)` 都是必要的
4. ✅ **函数签名默认值** - 最后一道防线
5. ✅ **所有数值已统一** - tolerance 已从 0.05 改为 0.02

### 配置优先级（正确的）

```
用户修改 UI → config.set() → 立即保存到 config.json
                 ↓
重启程序 → ConfigStore 加载 config.json
                 ↓
       dispatcher._load_persisted_config()
                 ↓
       engine.configure(从 config 读取)
                 ↓
       设置到 solver 字段
                 ↓
       UI 从 config 加载显示
```
