import os
import tkinter as tk
from tkinter import filedialog, messagebox, PhotoImage

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.themes import user
from ttkbootstrap import (
    Toplevel,
    Button,
    Label,
    Frame,
    Entry,
    Checkbutton,
    Combobox,
    Progressbar,
    Scrollbar,
    Text,
    Window,
    Style,
)

style = ttk.Style("darkly")
base_path = os.path.abspath(".")

# Lokale Datei importieren
import patcher_methods as patcher_methods  # Achte darauf, dass patcher_methods.py die Funktion center_window definiert

def show_main_window():
    root = ttk.Window(themename="superhero")
    root.title("A.n.S Patcher by Felix")

    # Korrekte Icon-Ladung mit PhotoImage
    icon_path = os.path.join(base_path, "A_n_S__Patcher__Fuzed", "assets", "icon.png")
    if os.path.exists(icon_path):
        icon = PhotoImage(file=icon_path)
        root.iconphoto(True, icon)
    else:
        print(f"Icon Datei nicht gefunden: {icon_path}")

    root.geometry("600x400")
    root.minsize(600, 400) 

    patcher_methods.center_window(root)

    # ----- buttonbar
    buttonbar = Frame(root)
    buttonbar.pack(fill='x', pady=1, side='top')

    # Settings Button
    bb_settings_btn = Button(buttonbar, text='Settings', image='properties-light', compound='left')
    bb_settings_btn.configure(command=lambda: messagebox.showinfo("Info", "Changing settings"))
    bb_settings_btn.pack(side='left', ipadx=5, ipady=5, padx=0, pady=1)

    # Tools Button
    bb_tools_btn = Button(buttonbar, text='Stop', image='stop-light', compound='left')
    bb_tools_btn.configure(command=lambda: messagebox.showinfo("Info", "Stopping backup."))
    bb_tools_btn.pack(side='left', ipadx=5, ipady=5, padx=0, pady=1)

    # Help Button
    bb_help_btn = Button(buttonbar, text='Help', image='help-light', compound='left')
    bb_help_btn.configure(command=lambda: messagebox.showinfo("Info", "Help information"))
    bb_help_btn.pack(side='left', ipadx=5, ipady=5, padx=0, pady=1)

    root.mainloop()

if __name__ == "__main__":
    show_main_window()
