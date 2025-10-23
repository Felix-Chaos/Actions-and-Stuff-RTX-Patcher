import os
import numpy as np
from PIL import Image
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, Listbox, END

# Clean transparency by setting fully transparent pixels to black
def clean_transparency(input_path, output_path, threshold=10):
    image = Image.open(input_path).convert("RGBA")
    arr = np.array(image)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    mask = (a <= threshold)
    r[mask], g[mask], b[mask], a[mask] = 0, 0, 0, 0  # fully transparent and black
    cleaned = np.stack([r, g, b, a], axis=2)
    Image.fromarray(cleaned, "RGBA").save(output_path)

# Process all TGA/PNG files in folder
def batch_clean_transparency(input_folder, output_folder, log_callback=None):
    os.makedirs(output_folder, exist_ok=True)
    count = 0
    for filename in os.listdir(input_folder):
        if filename.lower().endswith((".tga", ".png")):
            in_path = os.path.join(input_folder, filename)
            out_path = os.path.join(output_folder, os.path.splitext(filename)[0] + ".png")
            try:
                clean_transparency(in_path, out_path)
                count += 1
                if log_callback:
                    log_callback(f"✓ Cleaned: {filename}")
            except Exception as e:
                if log_callback:
                    log_callback(f"❌ Failed: {filename} ({e})")
    if log_callback:
        log_callback(f"✅ Done! {count} files processed.")

# Select folder using file dialog
def select_folder(entry):
    path = filedialog.askdirectory()
    if path:
        entry.delete(0, END)
        entry.insert(0, path)

# Start button logic
def start_cleaning():
    input_folder = input_entry.get()
    output_folder = output_entry.get()
    log_box.delete(0, END)

    if not os.path.isdir(input_folder):
        log_box.insert(END, "❌ Invalid input folder.")
        return
    if not os.path.isdir(output_folder):
        log_box.insert(END, "❌ Invalid output folder.")
        return

    def log(msg):
        log_box.insert(END, msg)
        log_box.yview_moveto(1.0)  # Auto-scroll to bottom

    batch_clean_transparency(input_folder, output_folder, log)

# GUI setup
app = tb.Window(themename="darkly")
app.title("Transparency Cleaner")
app.geometry("600x400")
app.resizable(False, False)

# Input folder
tb.Label(app, text="Input Folder:").pack(pady=5)
input_frame = tb.Frame(app)
input_frame.pack(fill=X, padx=10)
input_entry = tb.Entry(input_frame)
input_entry.pack(side=LEFT, fill=X, expand=True)
tb.Button(input_frame, text="Browse", command=lambda: select_folder(input_entry)).pack(side=RIGHT, padx=5)

# Output folder
tb.Label(app, text="Output Folder:").pack(pady=5)
output_frame = tb.Frame(app)
output_frame.pack(fill=X, padx=10)
output_entry = tb.Entry(output_frame)
output_entry.pack(side=LEFT, fill=X, expand=True)
tb.Button(output_frame, text="Browse", command=lambda: select_folder(output_entry)).pack(side=RIGHT, padx=5)

# Start button
tb.Button(app, text="Clean Transparency", bootstyle=SUCCESS, command=start_cleaning).pack(pady=20)

# Log box
log_box = Listbox(app, height=10, bg="#1e1e1e", fg="white", selectbackground="#444", highlightthickness=0)
log_box.pack(fill=BOTH, expand=True, padx=10, pady=10)

# Run app
app.mainloop()
