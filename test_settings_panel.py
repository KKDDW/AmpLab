# -*- coding: utf-8 -*-
"""测试基础设置面板集成"""

import tkinter as tk
from mini.ui.basic import BasicPanel
from mini.utils.logger import init_logging
from mini.utils.config import ConfigStore

# 启动日志系统
ring = init_logging(log_dir="logs", level=10)

# 创建配置管理器
config = ConfigStore()

# 模拟文件列表数据
test_file_list = []


def mock_add_files():
    """模拟添加文件"""
    from tkinter import filedialog
    files = filedialog.askopenfilenames(
        title="选择 COMSOL 模型",
        filetypes=[("COMSOL Model", "*.mph"), ("All", "*.*")],
    )
    if files:
        test_file_list.extend(files)
        panel.refresh_file_list(test_file_list)
        panel.append_log(f"已添加 {len(files)} 个文件", "success")


def mock_clear_files():
    """模拟清空文件"""
    count = len(test_file_list)
    test_file_list.clear()
    panel.refresh_file_list(test_file_list)
    panel.append_log(f"已清空 {count} 个文件", "info")


def mock_inspect():
    panel.append_log("模拟：开始检测模型...", "sys")


def mock_calc():
    panel.append_log("模拟：开始计算...", "sys")
    panel.set_buttons_state("computing")


def mock_stop():
    panel.append_log("模拟：中断计算", "warning")
    panel.set_buttons_state("inspected")


# 创建主窗口
root = tk.Tk()
root.title("基础设置面板集成测试")
root.geometry("1300x750")

# 创建主面板
panel = BasicPanel(
    root,
    on_add_files=mock_add_files,
    on_inspect=mock_inspect,
    on_calc=mock_calc,
    on_stop=mock_stop,
    ring=ring,
    config=config,
)

# 注入清空文件回调
panel._on_clear_files = mock_clear_files

# 测试初始数据
panel.append_log("UI 启动完成 — 基础设置面板已集成", "success")
panel.append_log("提示：修改任何设置都会自动保存到配置", "info")

print("=" * 60)
print("测试说明：")
print("1. 左侧上方：文件列表面板")
print("2. 左侧下方：基础设置面板（可编辑）")
print("3. 修改任何设置 -> 自动保存到 config")
print("4. 点击主题切换 -> 所有组件跟随变化")
print("5. 查看控制台输出 -> 配置变化日志")
print("=" * 60)

# 打印当前配置
print("\n初始配置：")
print(f"  目标温度: {config.get('compute.target_T', 90.0)}°C")
print(f"  容差: {config.get('compute.tolerance', 0.02)}°C")
print(f"  初始探测: {config.get('compute.initial_I', 800.0)}A")
print(f"  收敛方法: {config.get('compute.convergence_method', 'interp 多段式插值')}")

root.mainloop()
