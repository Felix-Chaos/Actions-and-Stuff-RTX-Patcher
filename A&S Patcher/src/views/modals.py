import os
import customtkinter as ctk
from src.gui.theme import *


class SelectionModal(ctk.CTkToplevel):
    """
    Generic Modal for selecting multiple items.
    """

    def __init__(self, parent, title: str, options: list, on_apply: callable):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x500")
        self.resizable(False, False)

        # Center Modal
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 200
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 250
        self.geometry(f"+{x}+{y}")
        self.transient(parent)
        self.grab_set()

        # Ensure title and icon
        self.title(title)
        self.after(100, lambda: self.title(title))  # Enforce title update

        try:
            # Try to set icon from parent if available
            if hasattr(parent, "iconbitmap"):
                # We can't easily access the icon path of parent unless stored.
                # But we can try to re-apply if we know the path or just ignore.
                pass
        except Exception:
            pass

        self.on_apply = on_apply
        self.options = options
        self.vars = {}

        # Content
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(self.container, text=title, font=(
            FONT_FAMILY, 18, "bold"), text_color=COLOR_TEXT).pack(pady=(0, 20))

        # Scrollable Options
        self.scroll = ctk.CTkScrollableFrame(
            self.container, fg_color=COLOR_SURFACE)
        self.scroll.pack(fill="both", expand=True, pady=10)

        for opt in options:
            # opt can be a string or a dict/tuple. Assuming string label for now.
            # If we need specific values vs labels, we can adapt.
            # Let's assume options is a list of {"label": "...", "value": "...", "checked": bool}
            label = opt.get("label", "Unknown")
            val = opt.get("value", label)
            is_checked = opt.get("checked", False)

            var = ctk.BooleanVar(value=is_checked)
            self.vars[val] = var
            chk = ctk.CTkCheckBox(self.scroll, text=label, variable=var,
                                  fg_color=COLOR_ACCENT_2, hover_color=COLOR_ACCENT_1, checkmark_color="black")
            chk.pack(anchor="w", pady=5, padx=10)

        # Buttons
        btn_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(20, 0))

        ctk.CTkButton(btn_frame, text="Apply", command=self.apply, **
                      get_button_style("filled-primary")).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy, fg_color="transparent",
                      border_width=1, border_color="gray").pack(side="right", padx=5)

    def apply(self):
        # Gather selected values
        selected = [k for k, v in self.vars.items() if v.get()]
        self.on_apply(selected)
        self.destroy()


class RTXSettingsModal(SelectionModal):
    """
    Preset modal for RTX Adjustments.
    Instead of generic apply, it maps specific actions.
    """

    def __init__(self, parent, on_apply_config: callable):
        # We construct options matching the requirement
        options = [
            {"label": "Disable Dithering (Blocks)",
             "value": "disable_dithering_blocks", "checked": True},
            {"label": "Disable Dithering (Mobs)",
             "value": "disable_dithering_mobs", "checked": True},
            {"label": "Force Graphics Mode 3 (Deferred)",
             "value": "force_graphics_mode_3", "checked": True},
            {"label": "Enable Graphics Switch",
                "value": "enable_graphics_switch", "checked": True},
        ]

        def internal_apply(selected_keys):
            # selected_keys is list of 'values' that identify the action
            changes = {}
            if "disable_dithering_blocks" in selected_keys:
                changes["enable_dithering_blocks"] = 0
            if "disable_dithering_mobs" in selected_keys:
                changes["enable_dithering_mobs"] = 0
            if "force_graphics_mode_3" in selected_keys:
                changes["graphics_mode"] = 3
            if "enable_graphics_switch" in selected_keys:
                changes["graphics_mode_switch"] = 1

            on_apply_config(changes)

        super().__init__(parent, "Adjust Settings for RTX", options, internal_apply)


class OptionsFilePickerModal(ctk.CTkToplevel):
    """
    Modal to let the user choose which options.txt file(s) to edit
    when multiple user profiles are detected.
    """

    def __init__(self, parent, files: list, on_select: callable):
        """
        Args:
            parent: Parent widget.
            files: list of (label, path) tuples.
            on_select: callback receiving a list of selected paths.
        """
        super().__init__(parent)
        self.title("Select Options File(s)")
        self.geometry("500x400")
        self.resizable(False, False)

        # Center
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 250
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 200
        self.geometry(f"+{x}+{y}")
        self.transient(parent)
        self.grab_set()

        self.on_select = on_select
        self.vars = {}  # path -> BooleanVar

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            container,
            text="Multiple options files found",
            font=(FONT_FAMILY, 18, "bold"),
            text_color=COLOR_TEXT
        ).pack(pady=(0, 5))

        ctk.CTkLabel(
            container,
            text="Select which file(s) to edit:",
            font=(FONT_FAMILY, 12),
            text_color=COLOR_TEXT_DIM
        ).pack(pady=(0, 15))

        # Scrollable checkboxes
        scroll = ctk.CTkScrollableFrame(container, fg_color=COLOR_SURFACE)
        scroll.pack(fill="both", expand=True, pady=5)

        for label, path in files:
            var = ctk.BooleanVar(value=True)
            self.vars[path] = var
            chk = ctk.CTkCheckBox(
                scroll, text=label, variable=var,
                fg_color=COLOR_ACCENT_2, hover_color=COLOR_ACCENT_1,
                checkmark_color="black"
            )
            chk.pack(anchor="w", pady=5, padx=10)

        # Action buttons row
        action_frame = ctk.CTkFrame(container, fg_color="transparent")
        action_frame.pack(fill="x", pady=(10, 0))

        ctk.CTkButton(
            action_frame, text="Select All",
            command=self._select_all,
            fg_color="transparent", border_width=1,
            border_color=COLOR_ACCENT_2, text_color=COLOR_ACCENT_2,
            width=100
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            action_frame, text="Browse…",
            command=self._browse_file,
            fg_color="transparent", border_width=1,
            border_color="#888888", text_color="#AAAAAA",
            width=100
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            action_frame, text="Apply",
            command=self._apply,
            **get_button_style("filled-primary"),
            width=100
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            action_frame, text="Cancel",
            command=self.destroy,
            fg_color="transparent", border_width=1,
            border_color="gray", width=100
        ).pack(side="right", padx=5)

    def _select_all(self):
        for var in self.vars.values():
            var.set(True)

    def _browse_file(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select options.txt",
            filetypes=[("Options File", "options.txt"),
                       ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if path and path not in self.vars:
            var = ctk.BooleanVar(value=True)
            self.vars[path] = var
            # Add checkbox dynamically (find the scroll frame)
            for widget in self.winfo_children():
                for child in widget.winfo_children():
                    if isinstance(child, ctk.CTkScrollableFrame):
                        chk = ctk.CTkCheckBox(
                            child, text=f"Custom — {os.path.basename(os.path.dirname(path))}",
                            variable=var, fg_color=COLOR_ACCENT_2,
                            hover_color=COLOR_ACCENT_1, checkmark_color="black"
                        )
                        chk.pack(anchor="w", pady=5, padx=10)
                        return

    def _apply(self):
        selected = [p for p, v in self.vars.items() if v.get()]
        self.destroy()
        if selected:
            # Call after window is fully destroyed to prevent grab_set conflicts
            self.master.after(10, lambda: self.on_select(selected))


class AllSettingsWindow(ctk.CTkToplevel):
    """
    Full JSON Editor
    """

    def __init__(self, parent, config_data: dict, on_save: callable):
        super().__init__(parent)
        self.title("Advanced Configuration Editor")
        self.geometry("600x700")

        # Center
        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 300
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 350
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

        self.config_data = config_data  # Reference to config dict
        self.on_save = on_save
        self.widgets = {}

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(self.container, text="Edit Configuration",
                     font=(FONT_FAMILY, 20, "bold")).pack(pady=(0, 20))

        # Scrollable Form
        self.scroll = ctk.CTkScrollableFrame(
            self.container, fg_color=COLOR_SURFACE)
        self.scroll.pack(fill="both", expand=True, pady=10)

        self._build_form(self.config_data, self.scroll)

        # Footer
        btn_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)

        ctk.CTkButton(btn_frame, text="Save Changes", command=self.save,
                      **get_button_style("filled-primary")).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Close", command=self.destroy, fg_color="transparent",
                      border_width=1, border_color="gray").pack(side="right", padx=5)

    def _build_form(self, data, parent_frame, prefix=""):
        # Recursive builder for JSON data
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key

            row = ctk.CTkFrame(parent_frame, fg_color="transparent")
            row.pack(fill="x", pady=5)

            ctk.CTkLabel(row, text=key, width=150,
                         anchor="w").pack(side="left", padx=5)

            if isinstance(value, bool):
                # Switch
                var = ctk.BooleanVar(value=value)
                self.widgets[full_key] = var
                ctk.CTkSwitch(row, text="", variable=var,
                              progress_color=COLOR_ACCENT_1).pack(side="right")

            elif isinstance(value, int):
                # Entry (Int)
                var = ctk.StringVar(value=str(value))
                self.widgets[full_key] = var
                ctk.CTkEntry(row, textvariable=var,
                             width=200).pack(side="right")

            elif isinstance(value, str):
                # Entry (Str)
                var = ctk.StringVar(value=value)
                self.widgets[full_key] = var
                ctk.CTkEntry(row, textvariable=var,
                             width=200).pack(side="right")

            elif isinstance(value, list):
                # Simple list display (editable as comma string? or just readonly for now to avoid complexity)
                # Converting list to string for editing
                var = ctk.StringVar(value=", ".join(map(str, value)))
                self.widgets[full_key] = var
                ctk.CTkEntry(row, textvariable=var,
                             width=200).pack(side="right")
                ctk.CTkLabel(row, text="(List)", font=(
                    "Unk", 10)).pack(side="right", padx=5)

            elif isinstance(value, dict):
                # Recurse? Nested dicts in flat list might be messy.
                # Let's add a Label and indent
                ctk.CTkLabel(row, text="(Group)",
                             text_color="gray").pack(side="right")

                sub_frame = ctk.CTkFrame(
                    parent_frame, fg_color="#222222")  # Slightly darker
                sub_frame.pack(fill="x", padx=20, pady=5)
                self._build_form(value, sub_frame, full_key)

    def save(self):
        # Reconstruct dict from widgets
        # This is tricky with recursion.
        # Simplified: We only support top-level or limited nesting edits for this MVP?
        # Actually, let's keep it simple. We iterate existing config and try to pull from widgets.

        def update_dict(target_dict, prefix=""):
            for key, val in target_dict.items():
                full_key = f"{prefix}.{key}" if prefix else key

                if full_key in self.widgets:
                    var = self.widgets[full_key]
                    raw_val = var.get()

                    if isinstance(val, bool):
                        target_dict[key] = bool(raw_val)
                    elif isinstance(val, int):
                        try:
                            target_dict[key] = int(raw_val)
                        except Exception:
                            pass
                    elif isinstance(val, str):
                        target_dict[key] = str(raw_val)
                    elif isinstance(val, list):
                        # Split string back to list
                        target_dict[key] = [x.strip() for x in str(
                            raw_val).split(",") if x.strip()]

                elif isinstance(val, dict):
                    update_dict(val, full_key)

        new_config = self.config_data.copy()  # Shallow copy
        update_dict(new_config)
        self.on_save(new_config)
        self.destroy()
