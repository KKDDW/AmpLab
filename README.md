# Ampacity Lab - 阶段一重构（MVC 架构）

## 📁 目录结构

```
NEW/
├── engine_core.py    # 纯净计算引擎（无 UI 依赖）
├── ui_basic.py       # 基础界面（不认识引擎）
├── dispatcher.py     # 调度器（连接引擎和 UI）
├── main.py          # 程序入口
└── README.md        # 本文件
```

## 🏗️ 架构设计

### 1. engine_core.py - 计算引擎层
**职责：** 纯粹的计算逻辑，不包含任何 UI 代码

**特点：**
- ✅ 完全移除了所有 `tkinter`、`customtkinter` 相关的 import
- ✅ 清除了所有界面直接操作代码（如 `self.root.after`、`self.log_text.insert` 等）
- ✅ 通过回调函数接口与外界通信：
  - `log_fn(msg, level)` - 日志回调
  - `progress_fn(current, total, elapsed)` - 进度回调
  - `result_fn(result)` - 结果回调

**核心类：**
- `AmpacityEngine` - 载流量寻优引擎
- `PointResult` - 单点结果数据类
- `MultiInspection` - 多文件扫描结果
- `OOMGuard` - 内存保护

### 2. ui_basic.py - 界面展示层
**职责：** 纯粹的 UI 元素创建和布局

**特点：**
- ✅ 绝对禁止 `import engine_core`（界面不认识引擎）
- ✅ 只创建 4 个按钮 + 1 个日志框
- ✅ 通过构造函数接收外部回调函数指针
- ✅ 按钮的 `command` 直接绑定外部传入的函数

**核心类：**
- `BasicPanel(ttk.Frame)` - 基础界面面板

**公开方法：**
- `append_log(message, level)` - 追加日志
- `clear_log()` - 清空日志
- `set_buttons_state(calculating)` - 设置按钮状态
- `get_log_content()` - 获取日志内容

### 3. dispatcher.py - 调度协调层
**职责：** 桥接引擎和 UI，编排业务逻辑

**特点：**
- ✅ 实例化 `AmpacityEngine`，定义回调方法接收引擎数据
- ✅ 实例化 `BasicPanel`，将业务方法注入到 UI 按钮
- ✅ 确保线程安全（使用 `root.after` 更新 UI）

**核心类：**
- `AppDispatcher` - 应用调度器

**业务方法：**
- `_on_add_files()` - 添加文件业务逻辑
- `_on_inspect()` - 检测模型业务逻辑
- `_on_calc()` - 开始计算业务逻辑
- `_on_stop()` - 中断计算业务逻辑

**回调处理：**
- `_handle_engine_log()` - 处理引擎日志推送
- `_handle_engine_progress()` - 处理引擎进度推送
- `_handle_engine_result()` - 处理引擎结果推送

### 4. main.py - 程序入口
**职责：** 极简启动

**特点：**
- ✅ 只负责创建主窗口和启动程序
- ✅ 所有业务逻辑都在 dispatcher 中

## 🔄 数据流向

```
用户点击按钮
    ↓
UI (ui_basic.py) 调用外部回调
    ↓
Dispatcher (dispatcher.py) 接收按钮事件
    ↓
Dispatcher 调用 Engine 的业务方法
    ↓
Engine (engine_core.py) 执行计算
    ↓
Engine 通过回调函数推送数据 (log_fn/progress_fn/result_fn)
    ↓
Dispatcher 接收回调数据
    ↓
Dispatcher 通过 root.after 线程安全地更新 UI
    ↓
UI 显示结果给用户
```

## 🚀 运行方式

### 方式一：直接运行主程序
```bash
cd NEW
python main.py
```

### 方式二：测试独立模块

**测试 UI 面板：**
```bash
python ui_basic.py
```

**测试调度器：**
```bash
python dispatcher.py
```

## ✅ 重构验证清单

### engine_core.py
- [x] 移除所有 tkinter/customtkinter 相关 import
- [x] 移除所有界面直接操作代码
- [x] 改造为回调函数接口 (log_fn, progress_fn, result_fn)
- [x] 保留所有核心计算逻辑

### ui_basic.py
- [x] 禁止 import engine_core
- [x] 只创建基础 UI 元素（4 按钮 + 1 日志框）
- [x] 通过构造函数接收外部回调函数
- [x] 提供公开方法供外部更新 UI

### dispatcher.py
- [x] 实例化 Engine 并注入回调
- [x] 实例化 UI 并注入按钮回调
- [x] 使用 root.after 确保线程安全
- [x] 编排所有业务逻辑

### main.py
- [x] 极简入口
- [x] 只负责启动程序

## 📝 后续扩展方向

阶段一完成了最小化可行产品（MVP），后续可以扩展：

1. **完善计算引擎**
   - 实现完整的 secant/bisect/interp 算法
   - 添加更多错误处理和边界情况
   - 实现 OOMGuard 的完整监控逻辑

2. **增强 UI 功能**
   - 添加进度条显示
   - 添加结果表格展示
   - 添加参数配置面板
   - 添加文件列表显示

3. **扩展调度器**
   - 添加配置管理
   - 添加结果导出功能
   - 添加任务队列管理
   - 添加并行计算支持

4. **代码优化**
   - 添加类型注解
   - 添加单元测试
   - 优化异常处理
   - 添加日志系统

## 🎯 设计原则总结

1. **分层解耦**：Engine、UI、Dispatcher 三层完全解耦
2. **单一职责**：每个模块只负责自己的核心功能
3. **依赖注入**：通过回调函数实现松耦合
4. **线程安全**：UI 更新统一通过 root.after 调度
5. **可测试性**：每个模块都可以独立测试

---

**版本：** MVP v1.0  
**日期：** 2026-07-15  
**状态：** ✅ 阶段一重构完成
