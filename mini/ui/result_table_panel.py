# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 计算结果表格面板
=============================================

定位: 计算结果展示视图
职责:
  1. 显示计算结果列表（表格形式）
  2. 实时更新结果（监听 result 事件）
  3. 状态颜色标记（成功/失败/跳过）
  4. 支持导出和右键菜单

设计模式:
  - 观察者模式: 监听事件总线的 result 事件
  - 只读表格: 用户不能直接编辑
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional, List, Any

from .constants import BUTTON_WIDTH_NARROW, BUTTON_PADDING_X
from ..utils.logger import get_logger

log = get_logger(__name__)


class ResultTablePanel(ttk.LabelFrame):
    """计算结果表格面板

    显示计算结果，包括：
    - 序号
    - 模型名称
    - 参数组名称
    - 环境变量
    - 电流 I (A)
    - 温度 T (°C)
    - 迭代次数
    - 耗时 (s)
    - 状态
    """

    # 列定义 (内部名称, 显示名称, 宽度)
    COLUMNS = [
        ("#", "#", 40),
        ("model", "模型", 150),
        ("group", "参数组", 120),
        ("env", "env", 80),
        ("I", "I (A)", 80),
        ("T", "T (°C)", 80),
        ("iters", "迭代", 60),
        ("time", "耗时(s)", 80),
        ("status", "状态", 80),
    ]

    def __init__(
        self,
        parent: tk.Misc,
        on_export: Optional[callable] = None,
    ) -> None:
        """
        Parameters
        ----------
        parent : tk.Misc
            父容器
        on_export : callable, optional
            导出按钮回调
        """
        super().__init__(parent, text="📊 计算结果", padding=10)

        self.on_export = on_export or (lambda: None)

        # 结果数据缓存 (用于导出)
        self._results: List[dict] = []

        self._build_ui()
        log.debug("ResultTablePanel 初始化完成")

    def _build_ui(self) -> None:
        """构建 UI 布局"""
        # 顶部工具栏
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))

        ttk.Label(toolbar, text="共 0 条结果").pack(side=tk.LEFT, padx=BUTTON_PADDING_X)

        self.lbl_count = ttk.Label(toolbar, text="共 0 条结果")
        self.lbl_count.pack(side=tk.LEFT, padx=BUTTON_PADDING_X)

        # 导出按钮
        self.btn_export = ttk.Button(
            toolbar,
            text="导出 CSV",
            command=self._on_export_clicked,
            width=BUTTON_WIDTH_NARROW * 2,
            state=tk.DISABLED  # 初始禁用
        )
        self.btn_export.pack(side=tk.RIGHT, padx=BUTTON_PADDING_X)

        # 清空按钮
        self.btn_clear = ttk.Button(
            toolbar,
            text="清空",
            command=self._on_clear_clicked,
            width=BUTTON_WIDTH_NARROW,
            state=tk.DISABLED  # 初始禁用
        )
        self.btn_clear.pack(side=tk.RIGHT, padx=BUTTON_PADDING_X)

        # 结果表格
        columns = [col[0] for col in self.COLUMNS]
        self.tree = ttk.Treeview(
            self,
            columns=columns,
            show="headings",  # 不显示 tree 列
            selectmode="extended",  # 支持多选
            height=15
        )

        # 设置列
        for col_id, col_name, col_width in self.COLUMNS:
            self.tree.heading(col_id, text=col_name)
            self.tree.column(col_id, width=col_width, anchor="center")

        # 滚动条
        scrollbar_y = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        # 布局（使用 pack 而不是 grid，保持一致）
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # 配置状态颜色标签
        self.tree.tag_configure("success", background="#C8E6C9")  # 浅绿
        self.tree.tag_configure("error", background="#FFCDD2")    # 浅红
        self.tree.tag_configure("skipped", background="#FFF9C4")  # 浅黄

        # 右键菜单
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="查看详情", command=self._on_view_details)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="复制选中", command=self._on_copy_selected)
        self.context_menu.add_command(label="删除选中", command=self._on_delete_selected)

        # 绑定事件
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Double-Button-1>", lambda e: self._on_view_details())

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 公开 API
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def append_result(self, result: dict) -> None:
        """追加一条计算结果

        Parameters
        ----------
        result : dict
            结果字典，包含以下字段：
            - task_id: 任务 ID
            - file_name: 模型文件名
            - group_name: 参数组名称
            - env: 环境变量
            - final_I: 最终电流
            - final_T: 最终温度
            - iterations: 迭代次数
            - elapsed_sec: 耗时（秒）
            - status: 状态 (success/error/skipped)
            - converged: 是否收敛
        """
        # 提取字段
        seq = len(self._results) + 1
        model = result.get("file_name", "N/A")
        group = result.get("group_name", "N/A")
        env = result.get("env", "-")
        final_I = result.get("final_I", 0.0)
        final_T = result.get("final_T", 0.0)
        iters = result.get("iterations", 0)
        elapsed = result.get("elapsed_sec", 0.0)
        status = result.get("status", "unknown")

        # 状态显示
        if status == "success" and result.get("converged", False):
            status_text = "✓ 成功"
            tag = "success"
        elif status == "skipped":
            status_text = "○ 跳过"
            tag = "skipped"
        else:
            status_text = "✗ 失败"
            tag = "error"

        # 插入表格
        values = (
            seq,
            model,
            group,
            env,
            f"{final_I:.2f}",
            f"{final_T:.2f}",
            iters,
            f"{elapsed:.2f}",
            status_text
        )

        self.tree.insert("", "end", values=values, tags=(tag,))

        # 缓存结果
        self._results.append(result)

        # 更新统计
        self._update_stats()

        # 自动滚动到最新
        self.tree.see(self.tree.get_children()[-1])

        log.debug(f"添加结果: {model} | {group} | {status_text}")

    def clear(self) -> None:
        """清空所有结果"""
        self.tree.delete(*self.tree.get_children())
        self._results.clear()
        self._update_stats()
        log.debug("清空结果表格")

    def get_results(self) -> List[dict]:
        """获取所有结果数据

        Returns
        -------
        List[dict]
            结果列表
        """
        return self._results.copy()

    def get_selected_results(self) -> List[dict]:
        """获取选中的结果

        Returns
        -------
        List[dict]
            选中的结果列表
        """
        selected_items = self.tree.selection()
        indices = []
        for item in selected_items:
            # 获取序号（第一列）
            values = self.tree.item(item)["values"]
            seq = int(values[0])
            indices.append(seq - 1)  # 转为 0-based

        return [self._results[i] for i in indices if 0 <= i < len(self._results)]

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 内部事件处理
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _update_stats(self) -> None:
        """更新统计信息"""
        count = len(self._results)
        self.lbl_count.config(text=f"共 {count} 条结果")

        # 更新按钮状态
        state = tk.NORMAL if count > 0 else tk.DISABLED
        self.btn_export.config(state=state)
        self.btn_clear.config(state=state)

    def _on_export_clicked(self) -> None:
        """导出按钮点击"""
        log.debug("用户点击 [导出 CSV]")
        self.on_export()

    def _on_clear_clicked(self) -> None:
        """清空按钮点击"""
        from tkinter import messagebox
        if messagebox.askyesno("确认", "确定要清空所有结果吗？"):
            self.clear()

    def _on_view_details(self) -> None:
        """查看详情"""
        selected = self.get_selected_results()
        if not selected:
            log.debug("未选中任何结果")
            return

        result = selected[0]  # 只看第一个
        from tkinter import messagebox
        details = (
            f"模型: {result.get('file_name', 'N/A')}\n"
            f"参数组: {result.get('group_name', 'N/A')}\n"
            f"电流: {result.get('final_I', 0):.2f} A\n"
            f"温度: {result.get('final_T', 0):.2f} °C\n"
            f"迭代: {result.get('iterations', 0)} 次\n"
            f"耗时: {result.get('elapsed_sec', 0):.2f} 秒\n"
            f"状态: {result.get('status', 'unknown')}\n"
            f"收敛: {'是' if result.get('converged', False) else '否'}"
        )
        messagebox.showinfo("结果详情", details)

    def _on_copy_selected(self) -> None:
        """复制选中结果到剪贴板"""
        selected = self.get_selected_results()
        if not selected:
            return

        # 生成 CSV 格式
        lines = ["模型,参数组,I(A),T(°C),迭代,耗时(s),状态"]
        for r in selected:
            line = (
                f"{r.get('file_name', '')},{r.get('group_name', '')},"
                f"{r.get('final_I', 0):.2f},{r.get('final_T', 0):.2f},"
                f"{r.get('iterations', 0)},{r.get('elapsed_sec', 0):.2f},"
                f"{r.get('status', '')}"
            )
            lines.append(line)

        text = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text)
        log.debug(f"已复制 {len(selected)} 条结果到剪贴板")

    def _on_delete_selected(self) -> None:
        """删除选中结果"""
        selected_items = self.tree.selection()
        if not selected_items:
            return

        from tkinter import messagebox
        if not messagebox.askyesno("确认", f"确定要删除 {len(selected_items)} 条结果吗？"):
            return

        # 获取索引（倒序删除）
        indices = []
        for item in selected_items:
            values = self.tree.item(item)["values"]
            seq = int(values[0])
            indices.append(seq - 1)

        # 倒序删除
        for i in sorted(indices, reverse=True):
            if 0 <= i < len(self._results):
                del self._results[i]

        # 删除 UI
        for item in selected_items:
            self.tree.delete(item)

        # 更新序号
        for i, item in enumerate(self.tree.get_children(), start=1):
            values = list(self.tree.item(item)["values"])
            values[0] = i
            self.tree.item(item, values=values)

        self._update_stats()
        log.debug(f"删除了 {len(selected_items)} 条结果")

    def _on_right_click(self, event) -> None:
        """右键菜单"""
        # 选中右键点击的项
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 本地测试
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    import random

    def test_export():
        results = panel.get_results()
        print(f"导出 {len(results)} 条结果")
        for r in results:
            print(f"  {r['file_name']} | {r['group_name']} | {r['final_I']:.2f}A")

    def test_add_random():
        """添加随机测试数据"""
        statuses = ["success", "error", "skipped"]
        status = random.choice(statuses)

        result = {
            "task_id": len(panel._results) + 1,
            "file_name": f"model_{random.randint(1, 5)}.mph",
            "group_name": f"参数组_{random.randint(1, 3)}",
            "env": f"env{random.randint(1, 2)}",
            "final_I": random.uniform(500, 1000),
            "final_T": random.uniform(80, 100),
            "iterations": random.randint(3, 10),
            "elapsed_sec": random.uniform(1, 10),
            "status": status,
            "converged": status == "success",
        }
        panel.append_result(result)

    # 创建测试窗口
    root = tk.Tk()
    root.title("ResultTablePanel 测试")
    root.geometry("1000x600")

    # 创建面板
    panel = ResultTablePanel(root, on_export=test_export)
    panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # 测试按钮
    btn_frame = ttk.Frame(root)
    btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

    ttk.Button(btn_frame, text="添加成功结果",
               command=lambda: panel.append_result({
                   "task_id": 1, "file_name": "test.mph", "group_name": "测试组",
                   "env": "env1", "final_I": 850.5, "final_T": 90.2,
                   "iterations": 5, "elapsed_sec": 3.5,
                   "status": "success", "converged": True
               })).pack(side=tk.LEFT, padx=4)

    ttk.Button(btn_frame, text="添加失败结果",
               command=lambda: panel.append_result({
                   "task_id": 2, "file_name": "test2.mph", "group_name": "测试组2",
                   "env": "env2", "final_I": 0, "final_T": 0,
                   "iterations": 0, "elapsed_sec": 0.5,
                   "status": "error", "converged": False
               })).pack(side=tk.LEFT, padx=4)

    ttk.Button(btn_frame, text="添加随机结果", command=test_add_random).pack(side=tk.LEFT, padx=4)

    print("提示：双击查看详情，右键菜单操作")
    root.mainloop()
