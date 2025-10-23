import tkinter as tk
import ttkbootstrap as ttk

class UIManager:
    def __init__(self, main_menu_builder):
        self.main_menu_builder = main_menu_builder
        self.main_menu = None
        self.tool_window = None

    def show_main_menu(self):
        if self.main_menu is None:
            self.main_menu = self.main_menu_builder(self)
            self.main_menu.protocol("WM_DELETE_WINDOW", self.main_menu.quit)
        self.main_menu.deiconify()
        if self.tool_window:
            self.tool_window.destroy()
            self.tool_window = None
        self.main_menu.mainloop()

    def show_tool_window(self, tool_builder):
        self.main_menu.withdraw()
        self.tool_window = tool_builder(self)
        self.tool_window.protocol("WM_DELETE_WINDOW", self.show_main_menu)
