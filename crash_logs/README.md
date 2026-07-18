# crash_logs/

JVM 崩溃日志的临时存放目录 (COMSOL 用 OpenJDK, 崩溃时自动写 `hs_err_pid*.log`)。

## 怎么用

崩溃日志**自动**会出现在 `mini/` 目录 (因为我们从 `mini/main.py` 启动) 或者项目根目录。
**手动移**到这个目录就行:

```powershell
# 崩溃后
mv mini\hs_err_pid*.log crash_logs\
```

## 为什么不进 git

崩溃日志是**临时调试产物**, 不是项目代码。
`.gitignore` 排除 `hs_err_pid*.log` 规则已经写好, 你 git add 不到这些文件。

## 这个目录本身进 git 吗?

- 目录**本身**进 git (有 README)
- 目录**内容** (`.log` 文件) 不进 git

这样的好处:
- 项目克隆下来, 这个目录是空的 (有 README 说明)
- 崩溃后你可以手动 `mv` 进来
- 别人看到目录名就知道 "这里放崩溃日志"
- `.gitignore` 配 `crash_logs/*.log` 自动排除日志内容
