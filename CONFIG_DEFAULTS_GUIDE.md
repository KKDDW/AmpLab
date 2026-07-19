# 默认参数配置说明

## 唯一需要修改的文件

**文件**：`mini/utils/config.py`

**位置**：`DEFAULT_CONFIG` 字典（第 32-58 行）

---

## 为什么只需要改这一个地方？

### 其他地方的作用

1. **UI 层**（`ui/settings_panel.py`）
   ```python
   val = self.config.get("compute.target_T", 90.0)
   #                                        ^^^^
   #                                        这只是 fallback 值
   #                                        如果 config 有值就用 config 的
   ```
   **作用**：防御性编程，万一 config 读取失败也有默认值

2. **Dispatcher 层**（`dispatcher.py`）
   ```python
   target_T = self.config.get("compute.target_T", 90.0)
   ```
   **作用**：同上，读取 config 时的 fallback

3. **Engine 层**（`engine_core.py`, `batch.py` 等）
   ```python
   def compute_ampacity(target_T: float = 90.0, ...):
   ```
   **作用**：函数签名的默认参数，实际会被 config 覆盖

### 数据流

```
修改 config.py 的 DEFAULT_CONFIG
         ↓
ConfigStore 初始化时加载
         ↓
UI 从 config.get() 读取
         ↓
用户修改 UI → config.set() 保存
         ↓
下次启动从 ~/.ampacity_lab/config.json 读取
```

---

## 修改示例

### 当前默认值
```python
DEFAULT_CONFIG: dict = {
    "compute": {
        "target_T": 90.0,      # 目标温度
        "tolerance": 0.02,     # 容差
        "initial_I": 800.0,    # 初始探测电流
    },
}
```

### 修改为新值
```python
DEFAULT_CONFIG: dict = {
    "compute": {
        "target_T": 85.0,      # 改为 85°C
        "tolerance": 0.05,     # 改为 0.05°C
        "initial_I": 1000.0,   # 改为 1000A
    },
}
```

---

## 完整的配置项说明

### compute 计算参数
| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `target_T` | 90.0 | 目标温度 (°C) |
| `tolerance` | 0.02 | 收敛容差 (°C) |
| `initial_I` | 800.0 | 初始探测电流 (A) |
| `method` | "linear" | 收敛方法（固定） |
| `max_iter` | 15 | 最大迭代次数 |

### session 会话参数
| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `comsol_version` | "latest" | COMSOL 版本 |
| `cores` | None | CPU 核心数（None=自动） |

### ui 界面参数
| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `last_open_dir` | "" | 上次打开目录 |
| `geometry` | "1000x700" | 窗口大小 |

### log 日志参数
| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `level` | "INFO" | 日志级别 |
| `buffer_capacity` | 2000 | 环形缓冲容量 |

### solver 求解器参数
| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `target_study` | "等待检测" | 目标研究节点 |
| `current_param_name` | "I" | 电流参数名 |
| `temp_expression` | "max(T, 1)" | 温度表达式 |
| `temp_unit` | "degC" | 温度单位 |

---

## 配置文件位置

### 用户配置文件
**位置**：`~/.ampacity_lab/config.json`  
**Windows**：`C:\Users\用户名\.ampacity_lab\config.json`

### 首次启动
- 如果文件不存在 → 使用 `DEFAULT_CONFIG` 创建
- 之后每次修改都会保存到这个文件

### 清空配置
删除 `~/.ampacity_lab/config.json` → 重启程序 → 恢复默认值

---

## 常见问题

### Q: 我改了 config.py，为什么没生效？
**A**: 用户已有的 `~/.ampacity_lab/config.json` 会覆盖默认值。  
**解决**: 删除用户配置文件，或者手动编辑它。

### Q: UI 上改的值会保存吗？
**A**: 会！UI 修改后立即调用 `config.set()` 保存到用户配置文件。

### Q: 为什么代码里还有其他默认值？
**A**: 那些是防御性的 fallback，实际运行时会优先使用 config 的值。

### Q: 如何强制所有用户使用新默认值？
**A**: 
1. 修改 `config.py` 的 `DEFAULT_CONFIG`
2. 让用户删除 `~/.ampacity_lab/config.json`
3. 或者在代码中强制覆盖

---

## 总结

**只需要修改一个文件**：`mini/utils/config.py`

修改 `DEFAULT_CONFIG` 字典，改完后：
- 新用户：自动使用新默认值
- 老用户：需要删除配置文件或手动更新
