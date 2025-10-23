import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from ttkbootstrap import Style
from ttkbootstrap.widgets import Button, Entry, Label

class JSONSearcherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("JSON Searcher")
        self.root.geometry("600x450")
        self.style = Style("darkly")

        # Input folder
        self.input_label = Label(root, text="Input Folder:")
        self.input_label.pack(pady=(10, 0))
        self.input_entry = Entry(root, width=70)
        self.input_entry.pack(pady=2)
        self.input_button = Button(root, text="Browse", command=self.browse_input)
        self.input_button.pack(pady=(0, 10))

        # Output folder
        self.output_label = Label(root, text="Output Folder:")
        self.output_label.pack()
        self.output_entry = Entry(root, width=70)
        self.output_entry.pack(pady=2)
        self.output_button = Button(root, text="Browse", command=self.browse_output)
        self.output_button.pack(pady=(0, 10))

        # Search words entry (updated label)
        self.word_label = Label(root, text="Words to Search (comma-separated, case-insensitive):")
        self.word_label.pack()
        self.word_entry = Entry(root, width=40)
        self.word_entry.insert(0, "")  # default value
        self.word_entry.pack(pady=(0, 10))

        # Start button
        self.start_button = Button(root, text="Start Search", bootstyle="success", command=self.search_json_files)
        self.start_button.pack(pady=(0, 10))

        # Log output
        self.result_text = ScrolledText(root, height=10, width=70)
        self.result_text.pack(pady=10)

    def browse_input(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, folder)

    def browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, folder)

    def search_json_files(self):
        input_folder = self.input_entry.get()
        output_folder = self.output_entry.get()
        search_input = self.word_entry.get().strip().lower()
        match_count = 0
        self.result_text.delete("1.0", tk.END)

        if not os.path.isdir(input_folder) or not os.path.isdir(output_folder):
            messagebox.showerror("Error", "Please select valid input and output folders.")
            return

        if not search_input:
            messagebox.showerror("Error", "Please enter one or more words to search for.")
            return

        # Split and clean keywords
        keywords = [word.strip() for word in search_input.split(',') if word.strip()]
        if not keywords:
            messagebox.showerror("Error", "No valid keywords entered.")
            return

        for filename in os.listdir(input_folder):
            if filename.endswith(".json"):
                file_path = os.path.join(input_folder, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().lower()
                    if any(word in content for word in keywords):
                        shutil.copy(file_path, os.path.join(output_folder, filename))
                        self.result_text.insert(tk.END, f"Found and copied: {filename}\n")
                        match_count += 1

        self.result_text.insert(tk.END, f"\nTotal files containing any of {keywords}: {match_count}\n")

# Run the app
if __name__ == "__main__":
    root = tk.Tk()
    app = JSONSearcherApp(root)
    root.mainloop()
