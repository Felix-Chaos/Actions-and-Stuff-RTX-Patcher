import os
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox

def compress_deterministic(folder_path, output_zip):
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in sorted(os.walk(folder_path)):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path).replace("\\", "/")

                # Consistent DOS-compatible timestamp: Jan 1, 1980
                info = zipfile.ZipInfo(arcname)
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED

                with open(file_path, 'rb') as f:
                    zf.writestr(info, f.read())

def select_and_compress(status_label):
    folder_path = filedialog.askdirectory(title="Select a folder to compress")
    if not folder_path:
        return

    output_zip = filedialog.asksaveasfilename(
        title="Save As",
        defaultextension=".zip",
        filetypes=[("Zip files", "*.zip")],
    )
    if not output_zip:
        return

    try:
        status_label.config(text=f"Compressing {os.path.basename(folder_path)}...")
        compress_deterministic(folder_path, output_zip)
        messagebox.showinfo("Success", f"Successfully compressed to {output_zip}")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
    finally:
        status_label.config(text="Select a folder to compress.")

def main():
    print("Starting Deterministic Zipper GUI...")
    root = tk.Tk()
    root.title("Deterministic Zipper")
    root.geometry("400x150")

    status_label = tk.Label(root, text="Select a folder to compress.", padx=10, pady=10)
    status_label.pack()

    compress_button = tk.Button(
        root,
        text="Select Folder and Compress",
        command=lambda: select_and_compress(status_label)
    )
    compress_button.pack(pady=20)

    root.mainloop()

if __name__ == "__main__":
    main()