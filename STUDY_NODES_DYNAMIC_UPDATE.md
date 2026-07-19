# 研究节点动态更新功能说明

## 功能概述

**研究节点**的下拉列表内容现在会根据**模型检测结果**动态设置。

## 工作流程

```
1. 用户添加 .mph 文件
   ↓
2. 点击 [检测模型] 按钮
   ↓
3. dispatcher 调用 engine.inspect_mph(file)
   ↓
4. 检测结果返回，包含模型中的研究节点列表
   ↓
5. dispatcher 调用 ui.update_study_nodes(nodes)
   ↓
6. 基础设置面板的"研究节点"下拉框自动更新选项
```

## 实现细节

### UI 层新增方法

**BasicPanel** (`ui/basic.py`):
```python
def update_study_nodes(self, nodes: list) -> None:
    """更新研究节点选项 (供 dispatcher 调用，检测模型后)"""
    self.settings_panel.update_study_nodes(nodes)
```

**SettingsPanel** (`ui/settings_panel.py`):
```python
def update_study_nodes(self, nodes: List[str]) -> None:
    """动态更新研究节点选项（从检测结果中获取）
    
    - 保存当前选中值
    - 更新下拉框选项
    - 如果当前值仍在列表中，保持选中
    - 否则选择第一个
    """
```

### Dispatcher 集成示例

```python
def _on_inspect(self) -> None:
    file_list = list(self.file_list)
    
    def work() -> None:
        for fp in file_list:
            res = self.engine.inspect_mph(fp)
            if res.ok:
                # 获取检测到的研究节点
                study_nodes = res.data.get("study_nodes", [])
                if study_nodes:
                    # 更新 UI 下拉框
                    self.ui.update_study_nodes(study_nodes)
                    
                self.ui.append_log(
                    f"✓ {os.path.basename(fp)} 检测完成 (研究节点: {', '.join(study_nodes)})",
                    "success"
                )
```

## 使用示例

### 场景 1：单个模型
```
1. 添加 model1.mph
2. 点击检测
3. 检测结果：["研究 1", "研究 2"]
4. 下拉框更新为这两个选项
```

### 场景 2：多个模型
```
1. 添加 model1.mph 和 model2.mph
2. 点击检测
3. model1 检测到：["研究 1", "研究 2"]
4. model2 检测到：["研究 1", "研究 3", "参数化扫描"]
5. 合并所有唯一节点：["研究 1", "研究 2", "研究 3", "参数化扫描"]
6. 下拉框更新
```

### 场景 3：保持用户选择
```
1. 当前选中："研究 1"
2. 检测新模型后节点列表更新为：["研究 1", "研究 2", "研究 3"]
3. "研究 1" 仍在列表中 → 保持选中
```

### 场景 4：用户选择不在新列表
```
1. 当前选中："研究 2"
2. 检测新模型后节点列表更新为：["研究 1", "研究 3"]
3. "研究 2" 不在新列表 → 自动选中第一个 "研究 1"
```

## 与后端集成

需要确保 `engine.inspect_mph()` 返回结果中包含 `study_nodes` 字段：

```python
# engine/inspector.py 或类似文件
def inspect_mph(self, file_path: str) -> Result:
    # ... 检测逻辑 ...
    
    data = {
        "parameters": [...],
        "study_nodes": ["研究 1", "研究 2"],  # 从模型中提取
        # ... 其他信息 ...
    }
    
    return Result(ok=True, data=data)
```

## 好处

1. **动态适应**：不同模型有不同的研究节点，下拉框自动适配
2. **避免错误**：用户只能选择模型中实际存在的节点
3. **用户友好**：不需要手动输入，减少拼写错误
4. **智能保持**：尽可能保持用户之前的选择

## 测试

修改 `test_complete_ui.py` 中的 `mock_inspect()` 来测试：

```python
def mock_inspect():
    """模拟检测 - 更新研究节点"""
    panel.append_log("模拟：开始检测模型...", "sys")
    
    # 模拟检测到的节点
    detected_nodes = ["研究 1", "研究 2", "参数化扫描 1"]
    panel.update_study_nodes(detected_nodes)
    
    panel.append_log(
        f"✓ model1.mph 检测完成 (节点: {', '.join(detected_nodes)})",
        "success"
    )
```

运行后，基础设置面板的"研究节点"下拉框会自动更新为检测到的节点。
