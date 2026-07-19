# Ampacity Lab UI 实现计划

## 目标
将当前的简单 UI 升级为功能完整的参数化计算界面（参考目标截图）

---

## 阶段 1：UI 框架搭建（优先级：⭐⭐⭐⭐⭐）

### 1.1 左侧面板 - 模型文件列表区
**文件**：`ui/file_list_panel.py`（新建）

**组件**：
- `ttk.Treeview`：显示已添加的 .mph 文件
- 2 个按钮：`添加文件` / `清空列表`

**功能**：
- 显示文件名、路径
- 支持多选删除
- 双击打开文件详情

**后端接口**：
```python
self.file_list: List[str]  # dispatcher 已有
```

---

### 1.2 左侧面板 - 基础设置区
**文件**：`ui/settings_panel.py`（新建）

**组件**：
| 标签 | 控件 | 配置 key |
|------|------|----------|
| 研究节点 | `ttk.Combobox` | `compute.study_node` |
| 收敛变量 | `ttk.Combobox` | `compute.converge_var` |
| 目标温度 (°C) | `ttk.Entry` | `compute.target_T` |
| 容差 (°C) | `ttk.Entry` | `compute.tolerance` |
| 初始探测 (A) | `ttk.Entry` | `compute.initial_I` |
| 保存策略 | `ttk.Combobox` | `compute.save_strategy` |
| 收敛方法 | `ttk.Combobox` | `compute.convergence_method` |
| COMSOL 版本 | `ttk.Combobox` | `engine.comsol_version` |
| 派生值 | `ttk.Entry` | `compute.derived_expr` |

**功能**：
- 双向绑定 config
- 输入验证（数值范围）
- 工具提示 (Tooltip)

**后端接口**：
```python
self.config.get(key, default)
self.config.set(key, value)
```

---

### 1.3 左侧面板 - 参数组包扫描
**文件**：`ui/param_table_panel.py`（新建）

**组件**：
- `ttk.Treeview`：可编辑表格
- 工具栏按钮：`+ 行` / `- 行` / `+ 列` / `- 列` / `📋 置顶`
- Checkbox：启用/禁用扫描

**功能**：
- 动态增删行列
- 单元格编辑
- 列名自定义
- 数据验证

**数据结构**：
```python
{
    "columns": ["r3", "r2", "r1", "r8", "R", "d"],
    "rows": [
        {"name": "型号1_88mm", "r3": 71.2, "r2": 52.1, ...},
        {"name": "型号2_100%", "r3": 75.4, "r2": 54.5, ...},
    ]
}
```

**后端接口**：
```python
self.static_groups: List[dict]  # dispatcher 已有
```

---

### 1.4 左侧面板 - 独立参数扫描
**文件**：`ui/sweep_panel.py`（新建）

**组件**：
- `ttk.Checkbutton`：启用扫描
- `tk.Text`：多行输入区
- 工具栏：`+ 行` / `- 行`
- 提示文本：`一行一变量: 变量名 = 数值1, 数值2, 数值3`

**示例**：
```
xiayi = 0, 5000
k = 1.2, 1.0, 0.8
```

**后端接口**：
```python
self.sweep_params: dict  # dispatcher 已有
```

---

### 1.5 右侧面板 - 计算结果表格
**文件**：`ui/result_table_panel.py`（新建）

**组件**：
- `ttk.Treeview`：结果展示
- 列：`# | 模型 | 参数组 | env | I (A) | T (°C) | 迭代 | 耗时(s) | 状态`

**功能**：
- 实时更新结果
- 颜色标记状态：
  - 成功：绿色
  - 失败：红色
  - 跳过：黄色
- 右键菜单：导出选中 / 删除 / 查看详情

**后端接口**：
```python
self.engine.tasks: List[PointResult]  # 已有
# 通过事件总线实时更新
self.bus.on("result", callback)
```

---

### 1.6 底部按钮栏优化
**文件**：`ui/basic.py`（修改）

**新增按钮**：
- `导出 CSV`
- `导出当前配置`
- `打开 Web UI`

**状态机扩展**：
```python
# 新增状态
"has_results": 有结果时启用导出按钮
```

---

## 阶段 2：数据绑定与逻辑（优先级：⭐⭐⭐⭐）

### 2.1 配置双向绑定
**文件**：`ui/widgets/bound_entry.py`（新建）

**实现**：
```python
class BoundEntry(ttk.Entry):
    """绑定到 config 的输入框"""
    def __init__(self, parent, config, key, dtype=str, **kw):
        self.config = config
        self.key = key
        self.dtype = dtype
        # 初始加载
        self.set_value(config.get(key))
        # 失焦时保存
        self.bind("<FocusOut>", self._on_save)
```

---

### 2.2 表格数据同步
**实现**：
```python
class ParamTablePanel:
    def sync_to_dispatcher(self):
        """UI → dispatcher"""
        rows = self._extract_table_data()
        self.dispatcher.static_groups = rows

    def sync_from_dispatcher(self):
        """dispatcher → UI"""
        self._populate_table(self.dispatcher.static_groups)
```

---

### 2.3 结果实时更新
**实现**：
```python
# dispatcher 事件绑定
self.bus.on("result", self._on_result_event)

def _on_result_event(self, result: PointResult):
    # 在主线程更新 UI
    self.root.after(0, self.ui.result_table.append_result, result)
```

---

## 阶段 3：交互功能（优先级：⭐⭐⭐）

### 3.1 表格编辑器
**功能**：
- 双击单元格编辑
- Tab 键切换单元格
- Enter 确认 / Esc 取消
- 复制粘贴支持

**参考实现**：
```python
def _on_double_click(self, event):
    item = self.tree.identify_row(event.y)
    col = self.tree.identify_column(event.x)
    self._show_cell_editor(item, col)
```

---

### 3.2 数据验证
**实现**：
```python
VALIDATORS = {
    "float": lambda x: float(x) if x else None,
    "int": lambda x: int(x) if x else None,
    "positive_float": lambda x: float(x) > 0,
}

def validate_input(value, dtype):
    try:
        return VALIDATORS[dtype](value)
    except:
        messagebox.showerror("输入错误", f"无效的 {dtype} 值")
        return None
```

---

### 3.3 导出功能
**文件**：`utils/export.py`（新建）

**功能**：
```python
def export_results_to_csv(results: List[PointResult], path: str):
    """导出结果到 CSV"""
    pass

def export_config_to_json(config: dict, path: str):
    """导出当前配置"""
    pass
```

---

## 阶段 4：细节优化（优先级：⭐⭐）

### 4.1 进度条
**组件**：`ttk.Progressbar`

**位置**：底部状态栏

**更新**：
```python
self.bus.on("progress", lambda c, t, _: self.ui.update_progress(c, t))
```

---

### 4.2 快捷键
**实现**：
```python
root.bind("<Control-o>", self._on_add_files)
root.bind("<F5>", self._on_calc)
root.bind("<Escape>", self._on_stop)
```

---

### 4.3 主题适配
**表格颜色**：
```python
# themes.py
THEMES["cute"]["table_colors"] = {
    "success": "#C8E6C9",  # 浅绿
    "error": "#FFCDD2",    # 浅红
    "skipped": "#FFF9C4",  # 浅黄
}
```

---

## 📅 时间估算

| 阶段 | 预计时间 | 关键产出 |
|------|---------|---------|
| 阶段 1 | 3 天 | UI 框架搭建完成，能看到布局 |
| 阶段 2 | 2 天 | 数据流通，能运行计算 |
| 阶段 3 | 3 天 | 交互完善，用户能操作 |
| 阶段 4 | 1 天 | 细节优化，体验提升 |
| **总计** | **9 天** | 完整可用的 MVP |

---

## 🚀 立即开始：第一步

**建议从最简单的开始**：

1. **创建文件列表面板**（1-2 小时）
   - 最简单的 Treeview
   - 复用现有的 `_on_add_files` 逻辑
   - 立即看到效果，建立信心

2. **把面板嵌入 basic.py**（30 分钟）
   - 替换占位的 "业务展示区"
   - 验证布局

3. **测试数据绑定**（30 分钟）
   - 添加文件 → 列表显示
   - 清空列表 → dispatcher 同步

**第一步代码框架**：
```python
# ui/file_list_panel.py
class FileListPanel(ttk.Frame):
    def __init__(self, parent, dispatcher):
        super().__init__(parent)
        self.dispatcher = dispatcher
        self._build_ui()

    def _build_ui(self):
        # 顶部工具栏
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, pady=4)

        ttk.Button(toolbar, text="添加文件", 
                   command=self.dispatcher._on_add_files).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="清空列表", 
                   command=self._on_clear).pack(side=tk.LEFT, padx=4)

        # 文件列表
        self.tree = ttk.Treeview(self, columns=("path",), show="tree headings")
        self.tree.heading("#0", text="文件名")
        self.tree.heading("path", text="路径")
        self.tree.pack(fill=tk.BOTH, expand=True)

    def refresh(self):
        """从 dispatcher 刷新列表"""
        self.tree.delete(*self.tree.get_children())
        for i, fp in enumerate(self.dispatcher.file_list):
            name = os.path.basename(fp)
            self.tree.insert("", "end", text=name, values=(fp,))
```

---

## 💡 关键建议

1. **前后端交替开发**
   - 先搭 UI 框架（看到效果）
   - 再接数据（验证逻辑）
   - 最后优化交互

2. **保持后端不变**
   - 你的后端逻辑很完整，不要大改
   - UI 只是"视图层"，调用后端 API

3. **增量开发**
   - 每个面板独立开发、测试
   - 不要一次性全改

4. **复用现有组件**
   - LogWindow 的模式很好，参考它
   - 主题系统已经完善，直接用

5. **测试驱动**
   - 每个面板写一个 `if __name__ == "__main__"` 独立测试
   - 确保能单独运行

---

## 🎯 下一步行动

**现在就开始第一步**：

```bash
# 1. 创建文件列表面板
touch ui/file_list_panel.py

# 2. 参考 log_window.py 的结构
# 3. 30 分钟内完成基础框架
# 4. 立即看到效果！
```

要我现在就帮你写 `FileListPanel` 的完整代码吗？
