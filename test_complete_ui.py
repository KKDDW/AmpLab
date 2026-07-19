# -*- coding: utf-8 -*-
"""测试计算结果表格完整集成"""

import tkinter as tk
import random
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
    """模拟检测 - 检测后更新研究节点"""
    panel.append_log("模拟：开始检测模型...", "sys")

    # 模拟检测延迟
    def finish_inspect():
        # 模拟检测到的研究节点
        detected_nodes = ["研究 1", "研究 2", "参数化扫描 1"]
        panel.update_study_nodes(detected_nodes)

        panel.append_log(
            f"✓ model1.mph 检测完成 (研究节点: {', '.join(detected_nodes)})",
            "success"
        )
        panel.append_log("研究节点已更新，请在基础设置中查看", "info")

    root.after(1000, finish_inspect)  # 1秒后完成检测


def mock_calc():
    """模拟计算 - 自动生成随机结果"""
    panel.append_log("=" * 50, "sys")
    panel.append_log("模拟：开始批量计算...", "sys")
    panel.set_buttons_state("computing")

    # 模拟添加 5 条结果
    def add_result(i):
        if i < 5:
            status = random.choice(["success", "success", "success", "error", "skipped"])
            result = {
                "task_id": i + 1,
                "file_name": f"cable_model_{random.randint(1, 3)}.mph",
                "group_name": f"参数组_{random.randint(1, 5)}",
                "env": f"env{random.randint(1, 2)}",
                "final_I": random.uniform(700, 950),
                "final_T": random.uniform(85, 95),
                "iterations": random.randint(4, 8),
                "elapsed_sec": random.uniform(2, 8),
                "status": status,
                "converged": status == "success",
            }
            panel.append_result(result)

            # 日志
            if status == "success":
                panel.append_log(
                    f"✓ task {i+1}: {result['file_name']} | {result['group_name']} | "
                    f"I={result['final_I']:.2f}A -> T={result['final_T']:.2f}°C",
                    "success"
                )
            elif status == "skipped":
                panel.append_log(f"○ task {i+1} 跳过", "warning")
            else:
                panel.append_log(f"✗ task {i+1} 失败", "error")

            # 继续下一个
            root.after(800, lambda: add_result(i + 1))
        else:
            panel.append_log("计算完成！", "sys")
            panel.set_buttons_state("inspected")

    root.after(500, lambda: add_result(0))


def mock_stop():
    """模拟停止"""
    panel.append_log("模拟：中断计算", "warning")
    panel.set_buttons_state("inspected")


# 创建主窗口
root = tk.Tk()
root.title("完整界面集成测试 - 包含结果表格")
root.geometry("1400x800")

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

# 注入导出结果回调
def mock_export_results():
    results = panel.result_table_panel.get_results()
    panel.append_log(f"导出 {len(results)} 条结果到 CSV", "info")
    print(f"导出 {len(results)} 条结果")

panel._on_export_results = mock_export_results

# 测试初始数据
panel.append_log("✨ UI 启动完成 - 完整功能界面", "success")
panel.append_log("左侧：文件列表 + 基础设置", "info")
panel.append_log("右侧：计算结果表格", "info")
panel.append_log("点击 [开始计算] 模拟批量计算", "sys")

print("=" * 60)
print("完整界面测试：")
print("1. 左上：文件列表面板（添加/清空文件）")
print("2. 左下：基础设置面板（研究节点、温度、容差、电流）")
print("3. 右侧：计算结果表格（实时显示结果）")
print("4. 点击 [开始计算] -> 自动模拟 5 条计算结果")
print("5. 右侧表格：双击查看详情，右键菜单操作")
print("6. 点击 [导出 CSV] 导出结果")
print("7. 切换主题 -> 所有组件跟随变化")
print("=" * 60)

root.mainloop()
