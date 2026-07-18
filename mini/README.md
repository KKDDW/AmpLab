# AmpLab mini

`mini/` 是 Ampacity Lab 的精简重构版, 相对原版改进了:
- 干掉硬编码路径
- 统一 `logging` + RingBuffer, 日志可落盘可回放
- UI 日志区默认隐藏, 点按钮才展开
- 引擎加 busy 锁, 防止 inspect / compute 并发打架
- 每个 solver step 都推到 dispatcher, 调试更细

## 目录结构

```
mini/
  main.py            # 入口 (30 行)
  dispatcher.py      # 业务编排 + 线程调度
  ui_basic.py        # 纯 UI, 不认识 engine
  engine_core.py     # 纯计算, 不认识 UI
  optimizer.py       # 纯数学, 零依赖
  logger.py          # logging 统一封装 + RingBuffer
  logs/              # 日志文件 (启动时自动创建, 按天切)
```

## 数据流

```
用户点 UI
  ↓ callback
Dispatcher
  ↓ 派发
Engine (后台线程)
  ↓ result_fn / step_fn
Dispatcher
  ├─→ logging (文件 + RingBuffer)
  └─→ UI.append_log (用户可见消息)
```

## 运行

```bash
# 项目根目录
cd NEW
python -m mini.main
```

或者在 PyCharm 里直接 run `mini/main.py`。

## 日志

- 文件: `mini/logs/ampacity_YYYYMMDD.log`, 保留 14 天
- 内存: 最近 2000 条, 首次展开 UI 日志区时回放
- 级别: 控制台 INFO 起, 文件 DEBUG 起, 内存全留

调整级别: `main.py` 里改 `init_logging(level=...)`。

## comsol_ampacity_mcp 路径解析

查找顺序:
1. 环境变量 `AMPACITY_MCP_SRC`
2. 父目录的 `comsol-ampacity-mcp/src`
3. `~/cable_tools/comsol-ampacity-mcp/src`
4. 走 sys.path 兜底

设置示例 (PowerShell):
```powershell
$env:AMPACITY_MCP_SRC = "D:\path\to\comsol-ampacity-mcp\src"
```

## Phase 3 TODO

- UI 业务展示区接入 (检测结果、批量进度条)
- 静态参数组 / 扫描参数 UI 编辑
- OOMGuard 真做实 (psutil 进程监控 + 自动重启引擎)
- 结果导出 CSV / Excel
