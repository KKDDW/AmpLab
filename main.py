# -*- coding: utf-8 -*-
"""ampacity-lab: 程序入口
=============================================

极简入口文件，只负责启动应用程序。
所有业务逻辑都在 dispatcher 中处理。
"""
import tkinter as tk
from dispatcher import AppDispatcher


def main():
    """程序主入口"""
    # 创建主窗口
    root = tk.Tk()
    root.title("Ampacity MVP")
    root.geometry("1000x700")

    # 创建调度器（自动创建引擎和 UI）
    app = AppDispatcher(root)

    # 窗口关闭时清理资源
    def on_closing():
        app.cleanup()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # 启动主循环
    root.mainloop()


if __name__ == '__main__':
    main()
