# -*- coding: utf-8 -*-
"""测试文件列表面板集成到主界面"""

import tkinter as tk
from mini.ui.basic import BasicPanel
from mini.utils.logger import init_logging

# 启动日志系统
ring = init_logging(log_dir="logs", level=10)

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
        print(f"添加了 {len(files)} 个文件，当前总数: {len(test_file_list)}")


def mock_clear_files():
    """模拟清空文件"""
    count = len(test_file_list)
    test_file_list.clear()
    panel.refresh_file_list(test_file_list)
    panel.append_log(f"已清空 {count} 个文件", "info")
    print(f"清空了 {count} 个文件")


def mock_inspect():
    panel.append_log("模拟：开始检测模型...", "sys")
    print("点击了检测")


def mock_calc():
    panel.append_log("模拟：开始计算...", "sys")
    panel.set_buttons_state("computing")
    print("点击了计算")


def mock_stop():
    panel.append_log("模拟：中断计算", "warning")
    panel.set_buttons_state("inspected")
    print("点击了中断")


# 创建主窗口
root = tk.Tk()
root.title("文件列表面板集成测试")
root.geometry("1200x700")

# 创建主面板
panel = BasicPanel(
    root,
    on_add_files=mock_add_files,
    on_inspect=mock_inspect,
    on_calc=mock_calc,
    on_stop=mock_stop,
    ring=ring,
)

# 注入清空文件回调
panel._on_clear_files = mock_clear_files

# 测试初始数据
test_file_list = [
    r"D:\models\cable_test_1.mph",
    r"D:\models\cable_test_2.mph",
]
panel.refresh_file_list(test_file_list)
panel.append_log("UI 启动完成 — 文件列表面板已集成", "success")

print("=" * 60)
print("测试说明：")
print("1. 点击顶部 [添加文件] 按钮 -> 选择文件 -> 文件列表更新")
print("2. 点击文件列表面板的 [清空列表] -> 列表清空")
print("3. 右键点击文件 -> 删除选中")
print("4. 点击 [日志] 查看日志窗口")
print("5. 点击 [切换主题] 测试主题系统")
print("=" * 60)

root.mainloop()
