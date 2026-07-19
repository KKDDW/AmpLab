# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 文件列表面板
=============================================

定位: 模型文件管理视图
职责:
  1. 显示已添加的 .mph 模型文件列表
  2. 提供添加/删除文件的 UI 操作
  3. 与 dispatcher.file_list 双向同步

设计模式:
  - 哑组件 (Dumb Component): 所有业务逻辑通过回调传入
  - 观察者模式: 监听 dispatcher 文件列表变化自动刷新
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, List

from .constants import BUTTON_WIDTH_STANDARD, BUTTON_PADDING_X
from ..utils.logger import get_logger

log = get_logger(__name__)


class FileListPanel(ttk.LabelFrame):
    """模型文件列表面板

    显示已添加的 .mph 文件，支持添加/删除操作
    """

    def __init__(
        self,
        parent: tk.Misc,
        on_add_files: Optional[Callable[[], None]] = None,
        on_clear_files: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Parameters
        ----------
        parent : tk.Misc
            父容器
        on_add_files : Callable
            添加文件回调（由 dispatcher 提供）
        on_clear_files : Callable
            清空列表回调
        """
        super().__init__(parent, text="📁 模型文件列表", padding=10)

        self.on_add_files = on_add_files or (lambda: None)
        self.on_clear_files = on_clear_files or (lambda: None)

        self._build_ui()
        log.debug("FileListPanel 初始化完成")

    def _build_ui(self) -> None:
        """构建 UI 布局"""
        # 顶部工具栏
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))

        self.btn_clear = ttk.Button(
            toolbar,
            text="清空列表",
            command=self._on_clear_clicked,
            width=BUTTON_WIDTH_STANDARD
        )
        self.btn_clear.pack(side=tk.LEFT, padx=BUTTON_PADDING_X)

        # 文件列表 (Treeview)
        # 使用 Treeview 而不是 Listbox，方便后续扩展显示文件详细信息
        columns = ("序号", "路径")
        self.tree = ttk.Treeview(
            self,
            columns=columns,
            show="tree headings",
            selectmode="extended",  # 支持多选
            height=8
        )

        # 列宽设置
        self.tree.column("#0", width=250, anchor="w")  # 文件名列
        self.tree.column("序号", width=50, anchor="center")
        self.tree.column("路径", width=400, anchor="w")

        # 列标题
        self.tree.heading("#0", text="文件名")
        self.tree.heading("序号", text="#")
        self.tree.heading("路径", text="完整路径")

        # 滚动条
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # 布局
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 右键菜单
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="删除选中", command=self._on_delete_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="全选", command=self._on_select_all)

        # 绑定事件
        self.tree.bind("<Button-3>", self._on_right_click)  # 右键
        self.tree.bind("<Delete>", lambda e: self._on_delete_selected())  # Delete 键

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 公开 API
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def refresh(self, file_list: List[str]) -> None:
        """从文件列表刷新显示

        Parameters
        ----------
        file_list : List[str]
            文件路径列表
        """
        # 清空现有内容
        self.tree.delete(*self.tree.get_children())

        # 重新填充
        for i, file_path in enumerate(file_list, start=1):
            file_name = os.path.basename(file_path)
            self.tree.insert(
                "",
                "end",
                text=file_name,  # 显示在 #0 列
                values=(i, file_path)  # 显示在其他列
            )

        # 更新按钮状态
        self._update_button_state(len(file_list))
        log.debug(f"文件列表已刷新: {len(file_list)} 个文件")

    def get_selected_indices(self) -> List[int]:
        """获取当前选中项的索引列表

        Returns
        -------
        List[int]
            选中项在 file_list 中的索引 (0-based)
        """
        selected_items = self.tree.selection()
        indices = []
        for item in selected_items:
            # values[0] 是序号 (1-based)
            seq = self.tree.item(item)["values"][0]
            indices.append(seq - 1)  # 转为 0-based
        return indices

    def set_buttons_state(self, enabled: bool) -> None:
        """设置按钮的启用/禁用状态

        Parameters
        ----------
        enabled : bool
            True 启用，False 禁用
        """
        state = tk.NORMAL if enabled else tk.DISABLED
        self.btn_add.config(state=state)
        self.btn_clear.config(state=state)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 内部事件处理
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _on_clear_clicked(self) -> None:
        """清空列表按钮点击"""
        if self.tree.get_children():
            log.debug("用户点击 [清空列表]")
            self.on_clear_files()
        else:
            log.debug("列表已空，忽略清空操作")

    def _on_delete_selected(self) -> None:
        """删除选中的文件"""
        selected = self.tree.selection()
        if not selected:
            log.debug("未选中任何文件")
            return

        # 获取选中的索引
        indices = self.get_selected_indices()
        log.debug(f"用户删除选中文件: {indices}")

        # 通知上层删除（需要传递索引）
        # 注意：这里需要 dispatcher 提供删除接口
        if hasattr(self, 'on_delete_files') and self.on_delete_files:
            self.on_delete_files(indices)

    def _on_select_all(self) -> None:
        """全选"""
        all_items = self.tree.get_children()
        self.tree.selection_set(all_items)
        log.debug(f"全选 {len(all_items)} 个文件")

    def _on_right_click(self, event) -> None:
        """右键菜单"""
        # 选中右键点击的项
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def _update_button_state(self, file_count: int) -> None:
        """根据文件数量更新按钮状态

        Parameters
        ----------
        file_count : int
            当前文件数量
        """
        # 清空按钮：有文件时才启用
        clear_state = tk.NORMAL if file_count > 0 else tk.DISABLED
        self.btn_clear.config(state=clear_state)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 本地测试
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    from tkinter import filedialog, messagebox

    # 模拟数据
    test_files = []

    def test_add_files():
        """测试添加文件"""
        files = filedialog.askopenfilenames(
            title="选择 COMSOL 模型",
            filetypes=[("COMSOL Model", "*.mph"), ("All", "*.*")],
        )
        if files:
            test_files.extend(files)
            panel.refresh(test_files)
            print(f"添加了 {len(files)} 个文件，当前总数: {len(test_files)}")

    def test_clear_files():
        """测试清空列表"""
        if messagebox.askyesno("确认", "确定要清空所有文件吗？"):
            test_files.clear()
            panel.refresh(test_files)
            print("已清空文件列表")

    def test_delete_files(indices):
        """测试删除选中文件"""
        # 倒序删除，避免索引错乱
        for i in sorted(indices, reverse=True):
            if 0 <= i < len(test_files):
                removed = test_files.pop(i)
                print(f"删除文件: {removed}")
        panel.refresh(test_files)

    # 创建测试窗口
    root = tk.Tk()
    root.title("FileListPanel 测试")
    root.geometry("800x400")

    # 创建面板
    panel = FileListPanel(
        root,
        on_add_files=test_add_files,
        on_clear_files=test_clear_files,
    )
    panel.on_delete_files = test_delete_files  # 动态添加删除回调
    panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # 初始测试数据
    test_files = [
        r"D:\models\cable_model_1.mph",
        r"D:\models\cable_model_2.mph",
        r"D:\models\test.mph",
    ]
    panel.refresh(test_files)

    print("提示：可以点击按钮测试添加/清空，右键测试删除")
    root.mainloop()
