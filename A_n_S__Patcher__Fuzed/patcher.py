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
from PIL import Image, ImageTk

base_path = os.path.abspath(".")

# Lokale Datei importieren
import patcher_methods as patcher_methods  # Achte darauf, dass patcher_methods.py die Funktion center_window definiert

def show_main_window():
    root = ttk.Window(themename="darkly")
    root.title("A.n.S Patcher by Felix")

    # Korrekte Icon-Ladung mit .ico
    icon_path = os.path.join(base_path, "A_n_S__Patcher__Fuzed", "assets", "icon.ico")
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
    else:
        print(f"Icon Datei nicht gefunden: {icon_path}")

    root.geometry("600x400")
   

    patcher_methods.center_window(root)

    # ----- Menubar
    menubar = ttk.Menu(root)
    root.config(menu=menubar)

    # Tools Menu
    tools_menu = ttk.Menu(menubar, tearoff=False)
    menubar.add_cascade(label="Tools", menu=tools_menu)
    tools_menu.add_command(label="Tool 1", command=lambda: messagebox.showinfo("Info", "Placeholder for Tool 1"))
    tools_menu.add_command(label="Tool 2", command=lambda: messagebox.showinfo("Info", "Placeholder for Tool 2"))

    # Dependencies Menu
    dependencies_menu = ttk.Menu(menubar, tearoff=False)
    menubar.add_cascade(label="Dependencies", menu=dependencies_menu)
    dependencies_menu.add_command(label="Dependency 1", command=lambda: messagebox.showinfo("Info", "Placeholder for Dependency 1"))
    dependencies_menu.add_command(label="Dependency 2", command=lambda: messagebox.showinfo("Info", "Placeholder for Dependency 2"))

    # Help Menu
    help_menu = ttk.Menu(menubar, tearoff=False)
    menubar.add_cascade(label="Help", menu=help_menu)
    help_menu.add_command(label="About", command=lambda: messagebox.showinfo("Info", "Placeholder for About"))

    # Main content frame
    main_frame = ttk.Frame(root, padding=10)
    main_frame.pack(expand=True, fill=BOTH)

    # Image
    image_path = os.path.join(base_path, "A_n_S__Patcher__Fuzed", "assets", "logo.png")
    if os.path.exists(image_path):
        pil_image = Image.open(image_path)
        pil_image = pil_image.resize((200, 100))  # gewünschte Größe z.B. (64, 64)
        image = ImageTk.PhotoImage(pil_image)
        image_label = ttk.Label(main_frame, image=image)
        image_label.image = image  # Referenz halten
        image_label.pack(pady=10)
    else:
        print(f"Image Datei nicht gefunden: {image_path}")
    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    leave_button = ttk.Button(button_frame, text="Leave Patcher", command=root.quit, bootstyle="danger")
    leave_button.pack(side=LEFT, padx=10)

    patch_button = ttk.Button(button_frame, text="Start patching", command=lambda: messagebox.showinfo("Info", "Start patching..."), bootstyle="success")
    patch_button.pack(side=LEFT, padx=10)

    # Advanced setup button
    advanced_button = ttk.Button(main_frame, text="Advanced setup", command=lambda: messagebox.showinfo("Info", "Advanced setup..."), bootstyle="link")
    advanced_button.pack(side=RIGHT, anchor=SE, padx=10, pady=10)


    root.mainloop()

if __name__ == "__main__":
    show_main_window()
