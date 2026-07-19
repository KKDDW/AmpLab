# -*- coding: utf-8 -*-
"""ampacity-lab (mini): 基础设置面板
=============================================

定位: 计算参数配置视图
职责:
  1. 显示和编辑计算相关的基础参数
  2. 与 config 双向绑定
  3. 输入验证和错误提示

设计模式:
  - 双向绑定: UI ↔ Config 自动同步
  - 观察者模式: 配置变化时通知其他组件
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional, Any, Dict, List

from .constants import BUTTON_PADDING_X
from tkinter import font as tkfont
from ..utils.logger import get_logger

log = get_logger(__name__)


class SettingsPanel(ttk.LabelFrame):
    """基础设置面板

    显示和编辑计算参数，包括：
    - 研究节点
    - 目标温度
    - 容差
    - 初始探测电流
    """

    # 下拉框选项定义
    STUDY_NODES_DEFAULT = ["等待检测..."]  # 默认显示

    def __init__(
        self,
        parent: tk.Misc,
        config: Optional[Any] = None,
        on_change: Optional[Callable[[str, Any], None]] = None,
    ) -> None:
        """
        Parameters
        ----------
        parent : tk.Misc
            父容器
        config : Config, optional
            配置管理器
        on_change : Callable[[str, Any], None], optional
            配置变化时的回调 (key, value)
        """
        super().__init__(parent, text="⚙️ 基础设置", padding=10)

        self.config = config
        self.on_change = on_change or (lambda k, v: None)

        # 存储所有输入控件的引用
        self._widgets: Dict[str, tk.Widget] = {}

        # 防止递归更新的标志
        self._updating = False

        self._build_ui()

        # 初始化时从 config 加载值
        if self.config:
            self.load_from_config()

        log.debug("SettingsPanel 初始化完成")

    def _build_ui(self) -> None:
        """构建 UI 布局 (两列网格)"""
        # 使用 grid 布局，左列标签，右列输入控件
        row = 0

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 第 1 行: 研究节点
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        ttk.Label(self, text="研究节点:").grid(
            row=row, column=0, sticky="e", padx=BUTTON_PADDING_X, pady=4
        )
        self._widgets["study_node"] = ttk.Combobox(
            self, values=self.STUDY_NODES_DEFAULT, state="readonly", width=15
        )
        self._widgets["study_node"].grid(row=row, column=1, sticky="w", pady=4)
        self._widgets["study_node"].bind("<<ComboboxSelected>>",
                                          lambda e: self._on_changed("solver.target_study"))
        row += 1

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 第 2 行: 目标值 | 误差
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        ttk.Label(self, text="目标值:").grid(
            row=row, column=0, sticky="e", padx=BUTTON_PADDING_X, pady=4
        )
        self._widgets["target_T"] = ttk.Entry(self, width=17)
        self._widgets["target_T"].grid(row=row, column=1, sticky="w", pady=4)
        self._widgets["target_T"].bind("<FocusOut>",
                                        lambda e: self._on_changed("compute.target_T"))

        ttk.Label(self, text="误差:").grid(
            row=row, column=2, sticky="e", padx=(20, BUTTON_PADDING_X), pady=4
        )
        self._widgets["tolerance"] = ttk.Entry(self, width=12)
        self._widgets["tolerance"].grid(row=row, column=3, sticky="w", pady=4)
        self._widgets["tolerance"].bind("<FocusOut>",
                                         lambda e: self._on_changed("compute.tolerance"))
        row += 1

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 第 3 行: 初始探测 | 收敛变量
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        ttk.Label(self, text="初始探测 (A):").grid(
            row=row, column=0, sticky="e", padx=BUTTON_PADDING_X, pady=4
        )
        self._widgets["initial_I"] = ttk.Entry(self, width=17)
        self._widgets["initial_I"].grid(row=row, column=1, sticky="w", pady=4)
        self._widgets["initial_I"].bind("<FocusOut>",
                                         lambda e: self._on_changed("compute.initial_I"))

        ttk.Label(self, text="收敛变量:").grid(
            row=row, column=2, sticky="e", padx=(20, BUTTON_PADDING_X), pady=4
        )
        # 收敛变量改成下拉框 (检测后填入模型参数, 默认 "I")
        self._widgets["temp_expression"] = ttk.Combobox(
            self, values=["I"], state="normal", width=12
        )
        self._widgets["temp_expression"].set("I")
        self._widgets["temp_expression"].grid(row=row, column=3, sticky="w", pady=4)
        # 收敛变量: 存到 solver.current_param (新 key, 跟 derived_expr 区分开)
        self._widgets["temp_expression"].bind("<<ComboboxSelected>>",
                                               lambda e: self._on_changed("solver.current_param"))
        self._widgets["temp_expression"].bind("<FocusOut>",
                                               lambda e: self._on_changed("solver.current_param"))
        row += 1

        # 派生表达式 (新加) - 默认 max(T, 1), 用来处理算结果时避免 T=0
        ttk.Label(self, text="派生表达式:").grid(
            row=row, column=0, sticky="e", padx=BUTTON_PADDING_X, pady=4
        )
        self._widgets["derived_expr"] = ttk.Entry(self, width=17)
        self._widgets["derived_expr"].grid(row=row, column=1, sticky="w", pady=4)
        self._widgets["derived_expr"].bind("<FocusOut>",
                                            lambda e: self._on_changed("solver.derived_expr"))
        row += 1

        # 设置列权重，让控件可以扩展
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(3, weight=1)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 参数组扫描 (第 4 块, 跟上面 grid 兼容)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 记录下一个可用 row
        self._next_row = row
        self._build_group_scan_frame(row=self._next_row)
        self._next_row += 1

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 独立参数扫描 (第 5 块)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        self._build_independent_scan_frame(row=self._next_row)
        self._next_row += 1

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 公开 API
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def load_from_config(self) -> None:
        """从 config 加载所有设置到 UI"""
        if not self.config:
            return

        self._updating = True  # 防止触发 on_change
        try:
            # 研究节点 - 从 solver.target_study 读取
            val = self.config.get("solver.target_study", "等待检测")
            if val and val != "等待检测":
                # 检查这个值是否在当前选项中
                current_values = list(self._widgets["study_node"]["values"])
                if val not in current_values:
                    # 如果不在，添加到选项中（可能是之前检测过的）
                    self._widgets["study_node"]["values"] = current_values + [val]
                self._widgets["study_node"].set(val)
            else:
                self._widgets["study_node"].set("等待检测...")

            # 收敛变量 (用什么参数去逼近 80°C, 默认 I)
            val = self.config.get("solver.current_param", "I")
            self._widgets["temp_expression"].delete(0, tk.END)
            self._widgets["temp_expression"].insert(0, str(val))

            # 派生表达式 (算出来的表达式, 默认 max(T, 1))
            val = self.config.get("solver.derived_expr", "max(T, 1)")
            if hasattr(self, "_widgets") and "derived_expr" in self._widgets:
                self._widgets["derived_expr"].delete(0, tk.END)
                self._widgets["derived_expr"].insert(0, str(val))

            # 目标值
            val = self.config.get("compute.target_T", 90.0)
            self._widgets["target_T"].delete(0, tk.END)
            self._widgets["target_T"].insert(0, str(val))

            # 误差
            val = self.config.get("compute.tolerance", 0.02)
            self._widgets["tolerance"].delete(0, tk.END)
            self._widgets["tolerance"].insert(0, str(val))

            # 初始探测
            val = self.config.get("compute.initial_I", 800.0)
            self._widgets["initial_I"].delete(0, tk.END)
            self._widgets["initial_I"].insert(0, str(val))

            log.debug("从 config 加载设置完成")
        finally:
            self._updating = False

    def save_to_config(self) -> None:
        """保存所有 UI 设置到 config"""
        if not self.config:
            return

        try:
            # 保存研究节点到 solver.target_study
            self.config.set("solver.target_study", self._widgets["study_node"].get())

            # 数字类型需要转换
            self.config.set("compute.target_T", float(self._widgets["target_T"].get()))
            self.config.set("compute.tolerance", float(self._widgets["tolerance"].get()))
            self.config.set("compute.initial_I", float(self._widgets["initial_I"].get()))

            log.debug("保存设置到 config 完成")
        except ValueError as e:
            log.error(f"保存设置失败: {e}")
            messagebox.showerror("输入错误", f"数值格式错误: {e}")

    def get_value(self, key: str) -> Any:
        """获取指定配置项的当前 UI 值

        Parameters
        ----------
        key : str
            配置键 (e.g., "compute.target_T" 或 "solver.target_study")

        Returns
        -------
        Any
            当前值
        """
        widget_map = {
            "solver.target_study": "study_node",
            "solver.current_param": "temp_expression",
            "solver.derived_expr": "derived_expr",
            "compute.target_T": "target_T",
            "compute.tolerance": "tolerance",
            "compute.initial_I": "initial_I",
        }

        widget_key = widget_map.get(key)
        if not widget_key:
            return None

        widget = self._widgets[widget_key]
        if isinstance(widget, ttk.Combobox):
            return widget.get()
        elif isinstance(widget, ttk.Entry):
            return widget.get()
        return None

    def update_study_nodes(self, nodes: List) -> None:
        """动态更新研究节点选项（供 dispatcher 调用）

        Parameters
        ----------
        nodes : List
            研究节点列表（从模型检测结果中获取）
            可以是字符串列表或字典列表 [{name, tag}, ...]
        """
        if not nodes:
            # 如果没有检测到节点，恢复默认
            self._widgets["study_node"]["values"] = self.STUDY_NODES_DEFAULT
            self._widgets["study_node"].set("等待检测...")
            return

        # 提取节点名称（支持字符串或字典）
        node_names = []
        for node in nodes:
            if isinstance(node, dict):
                # 字典格式：提取 name 字段
                node_names.append(node.get("name", str(node)))
            else:
                # 字符串格式：直接使用
                node_names.append(str(node))

        # 更新选项为检测到的实际节点
        self._widgets["study_node"]["values"] = node_names

        # 自动选择第一个检测到的节点
        self._widgets["study_node"].set(node_names[0])

        # 保存到 config（solver.target_study）
        if self.config:
            self.config.set("solver.target_study", node_names[0])

        log.debug(f"更新研究节点列表: {node_names}，已选择: {node_names[0]}")

    def update_parameters(self, parameters) -> None:
        """更新参数列表到下拉框 (供 dispatcher 调用, 检测后填入)

        Parameters
        ----------
        parameters : List
            参数列表 (从模型检测结果中获取)
            可以是 list[dict {name, value, description}] 或 list[str]
        """
        if not parameters:
            # 没有参数, 至少保留默认 "I"
            self._widgets["temp_expression"]["values"] = ["I"]
            return

        # 提取参数名称
        param_names = []
        for p in parameters:
            if isinstance(p, dict):
                param_names.append(p.get("name", str(p)))
            else:
                param_names.append(str(p))

        # 保留当前值 (如果还在列表里)
        current = self._widgets["temp_expression"].get()
        self._widgets["temp_expression"]["values"] = param_names
        if current in param_names:
            self._widgets["temp_expression"].set(current)
        elif "I" in param_names:
            self._widgets["temp_expression"].set("I")
        else:
            self._widgets["temp_expression"].set(param_names[0])

        log.debug(f"更新参数列表: {param_names}，已选择: {self._widgets['temp_expression'].get()}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 参数组扫描 UI
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # 列名默认值
    GROUP_DEFAULT_COLS = ["PackageNam", "D", "r3", "r2", "r1", "r0", "R", "d"]

    def _build_group_scan_frame(self, row: int = 0) -> None:
        """构建参数组扫描 UI (表格 + 增删按钮)"""
        frame = ttk.LabelFrame(self, text="📦 参数组包扫描", padding=6)
        frame.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(10, 4), padx=2)

        # 顶部: 启用 + 提示 + 增删按钮
        top = ttk.Frame(frame)
        top.pack(fill=tk.X, pady=(0, 4))

        self._group_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="启用", variable=self._group_enabled,
                        command=self._on_group_toggle).pack(side=tk.LEFT)

        ttk.Label(top, text="  ↓ 点格子直接改数值, {行} 增组 {列} 增变量",
                  foreground="gray").pack(side=tk.LEFT, padx=(8, 0))

        for text, cmd in [("+ 行", self._add_group_row),
                          ("- 行", self._del_group_row),
                          ("+ 列", self._add_group_col),
                          ("- 列", self._del_group_col),
                          ("重置", self._reset_group)]:
            ttk.Button(top, text=text, width=6, command=cmd).pack(
                side=tk.RIGHT, padx=2)

        # 表格区 (Treeview: 1 行表头 + N 行数据)
        self._group_tree_frame = ttk.Frame(frame)
        self._group_tree_frame.pack(fill=tk.BOTH, expand=True)

        # 默认 1 行 1 列 (启动时占位)
        self._group_data: List[List[str]] = [[""] * 1]  # 1 行 1 列
        self._group_col_names: List[str] = [self.GROUP_DEFAULT_COLS[0]]
        self._rebuild_group_tree()

    def _rebuild_group_tree(self) -> None:
        """根据 self._group_data + _group_col_names 重建 Treeview"""
        # 清掉旧的
        for w in self._group_tree_frame.winfo_children():
            w.destroy()

        # 表头: "#列名" + 各列名
        headers = ["# 行号"] + self._group_col_names

        self._group_tree = ttk.Treeview(
            self._group_tree_frame, columns=headers, show="headings", height=4
        )
        for h in headers:
            self._group_tree.heading(h, text=h)
            self._group_tree.column(h, width=80, anchor="center")

        # 数据行
        for i, row in enumerate(self._group_data):
            values = [f"#{i + 1}"] + row
            self._group_tree.insert("", tk.END, values=values)

        # 滚动条
        sb = ttk.Scrollbar(self._group_tree_frame, orient=tk.VERTICAL,
                           command=self._group_tree.yview)
        self._group_tree.configure(yscrollcommand=sb.set)
        self._group_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _on_group_toggle(self) -> None:
        """启用/禁用 组扫描 (disable 时表格灰)"""
        state = "normal" if self._group_enabled.get() else "disabled"
        # 启用时强制至少有 1 行
        if self._group_enabled.get() and not self._group_data:
            self._group_data = [[""]]
            self._rebuild_group_tree()

    def _add_group_row(self) -> None:
        if not self._group_enabled.get():
            return
        self._group_data.append([""] * len(self._group_col_names))
        self._rebuild_group_tree()

    def _del_group_row(self) -> None:
        if not self._group_enabled.get():
            return
        if len(self._group_data) > 1:
            self._group_data.pop()
            self._rebuild_group_tree()

    def _add_group_col(self) -> None:
        if not self._group_enabled.get():
            return
        # 用默认列名, 或者 #col_N
        next_idx = len(self._group_col_names)
        if next_idx < len(self.GROUP_DEFAULT_COLS):
            self._group_col_names.append(self.GROUP_DEFAULT_COLS[next_idx])
        else:
            self._group_col_names.append(f"col{next_idx + 1}")
        for row in self._group_data:
            row.append("")
        self._rebuild_group_tree()

    def _del_group_col(self) -> None:
        if not self._group_enabled.get():
            return
        if len(self._group_col_names) > 1:
            self._group_col_names.pop()
            for row in self._group_data:
                if row:
                    row.pop()
            self._rebuild_group_tree()

    def _reset_group(self) -> None:
        self._group_data = [[""]]
        self._group_col_names = [self.GROUP_DEFAULT_COLS[0]]
        self._rebuild_group_tree()

    def get_group_data(self) -> Dict:
        """返回参数组数据 (供 dispatcher 用)

        Returns
        -------
        dict
            {"enabled": bool, "columns": [...], "rows": [[...], ...]}
        """
        return {
            "enabled": self._group_enabled.get(),
            "columns": list(self._group_col_names),
            "rows": [list(r) for r in self._group_data],
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 独立参数扫描 UI
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _build_independent_scan_frame(self, row: int = 0) -> None:
        """构建独立参数扫描 UI (文本区 + 增删按钮)"""
        frame = ttk.LabelFrame(self, text="📝 独立参数扫描", padding=6)
        frame.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(4, 0), padx=2)

        # 顶部: 启用 + 提示 + 增删
        top = ttk.Frame(frame)
        top.pack(fill=tk.X, pady=(0, 4))

        self._ind_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="启用", variable=self._ind_enabled,
                        command=self._on_ind_toggle).pack(side=tk.LEFT)

        ttk.Label(top, text="  一行一变量: 变量名 = 数值1, 数值2, 数值3",
                  foreground="gray").pack(side=tk.LEFT, padx=(8, 0))

        for text, cmd in [("+ 行", self._add_ind_row),
                          ("- 行", self._del_ind_row)]:
            ttk.Button(top, text=text, width=6, command=cmd).pack(
                side=tk.RIGHT, padx=2)

        # 文本区
        self._ind_text = tk.Text(frame, height=4, font=("Consolas", 10),
                                  wrap=tk.NONE)
        self._ind_text.pack(fill=tk.BOTH, expand=True)

        # 默认放 1 行示例
        self._ind_text.insert("1.0", "# 例: xiayi = 0, 5000\nk = 1.2, 1.0, 0.8\n")

    def _on_ind_toggle(self) -> None:
        state = "normal" if self._ind_enabled.get() else "disabled"
        self._ind_text.configure(state=state)

    def _add_ind_row(self) -> None:
        if not self._ind_enabled.get():
            return
        # 在末尾加一行
        self._ind_text.insert(tk.END, "\n")

    def _del_ind_row(self) -> None:
        if not self._ind_enabled.get():
            return
        # 删最后一行
        last_line = self._ind_text.index("end-1c").split(".")[0]
        if int(last_line) > 1:
            self._ind_text.delete(f"{int(last_line) - 1}.0", f"{last_line}.0")

    def get_independent_data(self) -> Dict:
        """返回独立参数扫描数据 (供 dispatcher 用)

        Returns
        -------
        dict
            {"enabled": bool, "raw_text": str, "parsed": [{name, values}, ...]}
        """
        raw = self._ind_text.get("1.0", tk.END).rstrip()
        parsed = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                name, _, val = line.partition("=")
                name = name.strip()
                # 解析逗号分隔的数值
                values = [v.strip() for v in val.split(",") if v.strip()]
                try:
                    values = [float(v) for v in values]
                except ValueError:
                    pass  # 保留字符串
                parsed.append({"name": name, "values": values})
        return {
            "enabled": self._ind_enabled.get(),
            "raw_text": raw,
            "parsed": parsed,
        }

    def _on_changed(self, config_key: str) -> None:
        """配置项变化回调

        Parameters
        ----------
        config_key : str
            配置键名
        """
        if self._updating:
            return  # 正在批量更新，跳过

        value = self.get_value(config_key)
        if value is None:
            return

        # 数字类型需要验证和转换
        if config_key in ["compute.target_T", "compute.tolerance", "compute.initial_I"]:
            try:
                value = float(value)
                if config_key == "compute.target_T" and (value < 0 or value > 1000):
                    raise ValueError("目标值应在 0-1000 之间")
                if config_key == "compute.tolerance" and (value <= 0 or value > 100):
                    raise ValueError("误差应在 0-100 之间")
                if config_key == "compute.initial_I" and (value <= 0 or value > 10000):
                    raise ValueError("初始探测应在 0-10000A 之间")
            except ValueError as e:
                messagebox.showerror("输入错误", str(e))
                # 恢复原值
                if self.config:
                    self.load_from_config()
                return

        # 字符串类型：收敛变量，不需要特殊验证
        # solver.temp_expression, solver.target_study 直接保存

        # 保存到 config
        if self.config:
            self.config.set(config_key, value)

        # 通知外部
        self.on_change(config_key, value)
        log.debug(f"配置更新: {config_key} = {value}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 本地测试
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    from ..utils.config import Config

    # 创建测试配置
    test_config = Config()

    def on_setting_changed(key, value):
        print(f"配置变化: {key} = {value}")

    # 创建测试窗口
    root = tk.Tk()
    root.title("SettingsPanel 测试")
    root.geometry("700x350")

    # 创建面板
    panel = SettingsPanel(
        root,
        config=test_config,
        on_change=on_setting_changed
    )
    panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # 测试按钮
    btn_frame = ttk.Frame(root)
    btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

    ttk.Button(btn_frame, text="保存到 Config",
               command=panel.save_to_config).pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_frame, text="从 Config 加载",
               command=panel.load_from_config).pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_frame, text="打印 Config",
               command=lambda: print(test_config._data)).pack(side=tk.LEFT, padx=4)

    print("提示：修改任何设置都会自动保存到 config 并触发 on_change 回调")
    root.mainloop()
