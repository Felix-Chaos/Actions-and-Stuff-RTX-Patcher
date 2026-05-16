import os
import webbrowser
from tkinter import messagebox
from functools import partial

from ..views.mainWindow import MainWindow
from ..views.patchFrames import MainMenuFrame, PatchProgressFrame
from ..views.otherFrames import CleanFrame, FixFrame
from ..views.modals import RTXSettingsModal, AllSettingsWindow, OptionsFilePickerModal

from ..models.configModel import ConfigModel
from ..models.fileSystemModel import FileSystemModel
from ..models.patcherModel import PatcherModel

from .patchController import PatchController
from .cleanController import CleanController
from .fixController import FixController
from ..utils.helpers import resourcePath, runScriptInThread


class AppController:
    def __init__(self):
        self.config = ConfigModel()
        self.fs = FileSystemModel()
        self.patcher = PatcherModel()

        self.root = MainWindow(
            title="A&S Minecraft RTX Community Patcher V2", onClose=self.quit)
        # Use new snake_case method
        self.root.setIcon(resourcePath(self.config.get_filename("icon")))

        # Load Menus
        self._load_tools_menu()
        self._load_dependencies_menu()
        self._load_help_menu()
        self.root.bindAdvancedToggle(self.on_advanced_toggle)

        self.is_advanced = False

        self._init_frames()
        self.root.showFrame("MainMenu")

    def _load_tools_menu(self):
        # Look for tools folder in bundled resources
        tools_path = resourcePath("tools")

        scripts = []
        if os.path.isdir(tools_path):
            for f in sorted(os.listdir(tools_path)):
                if f.endswith(".py") and f != "__init__.py":
                    label = os.path.splitext(f)[0]
                    path = os.path.join(tools_path, f)
                    # Create command closure using partial
                    cmd = partial(runScriptInThread, self.root, path, label)
                    scripts.append((label, path, cmd))

        self.root.populateToolsMenu(scripts)

    def _load_dependencies_menu(self):
        def openVanillaRtx():
            if messagebox.askokcancel("Visit Website", "Open Vanilla Reforged RTX page?"):
                webbrowser.open(
                    "https://www.curseforge.com/minecraft-bedrock/texture-packs/vanilla-reforged-rtx")

        def openBetterRtx():
            if messagebox.askokcancel("Visit Website", "Open BetterRTX (bedrock.graphics)?"):
                webbrowser.open("https://bedrock.graphics/")

        def openMarketplace():
            if messagebox.askokcancel("Visit Website", "Open Actions & Stuff (Marketplace)?"):
                webbrowser.open(
                    "https://www.minecraft.net/en-us/marketplace/pdp/oreville-studios/actions--stuff-1.6/61c7a786-d7ad-49e0-a710-817121cd9795")

        self.root.populateDepMenu([
            ("Install Vanilla Reforged RTX", openVanillaRtx),
            ("BetterRTX (Required)", openBetterRtx),
            ("Actions & Stuff (Marketplace)", openMarketplace)
        ])

    def _load_help_menu(self):
        def joinDiscord():
            if messagebox.askokcancel("Join Discord", "Open A&S RTX Community Discord?"):
                webbrowser.open("https://discord.gg/YrMMmN2kc7")

        def about():
            try:
                from .. import version
                ver_str = version.VERSION
                date_str = version.BUILD_DATE
            except ImportError:
                ver_str = "2.0.0 (Dev)"
                date_str = "Unknown"

            info = (
                f"A&S Minecraft RTX Community Patcher V2\n\n"
                f"Version: {ver_str}\n"
                f"Build Date: {date_str}\n\n"
                f"Created by Felix-Chaos & Community\n"
                f"Based on original work by Demente Parker"
            )
            messagebox.showinfo("About", info)

        self.root.populateHelpMenu([
            ("Join Discord Server", joinDiscord),
            ("About", about)
        ])

    def _init_frames(self):
        # 1. Main Menu
        menu_callbacks = {
            "marketplace": lambda: self.show_patch_frame("marketplace"),
            "manual": lambda: self.show_patch_frame("manual"),
            "clean": self.show_clean_frame,
            "fix": self.show_fix_frame,
            "exit": self.quit,
            "rtx_settings": self.show_rtx_settings,
            "all_settings": self.show_all_settings
        }
        self.main_menu_frame = MainMenuFrame(
            self.root.container, menu_callbacks)
        self.root.addFrame("MainMenu", self.main_menu_frame)

        # 2. Patch Frame
        self.patch_frame = PatchProgressFrame(
            self.root.container, "Patching", self.back_to_main)
        self.root.addFrame("PatchFrame", self.patch_frame)
        self.patch_controller = PatchController(
            self.config, self.patcher, self.fs, self.patch_frame)

        # 3. Clean Frame
        self.clean_frame = CleanFrame(
            self.root.container, None, self.back_to_main)
        self.root.addFrame("CleanFrame", self.clean_frame)
        self.clean_controller = CleanController(
            self.config, self.fs, self.clean_frame)
        self.clean_frame.confirmBtn.configure(
            command=self.clean_controller.deleteFolders)

        # 4. Fix Frame
        self.fix_frame = FixFrame(
            self.root.container, None, None, self.back_to_main)
        self.root.addFrame("FixFrame", self.fix_frame)
        self.fix_controller = FixController(self.config, self.fix_frame)
        self.fix_frame.moveBtn.configure(
            command=self.fix_controller.moveMarketplaceFolders)
        self.fix_frame.restoreBtn.configure(
            command=self.fix_controller.restoreMarketplaceFolders)

    def on_advanced_toggle(self, enabled: bool):
        self.is_advanced = enabled
        self.main_menu_frame.setAdvancedMode(enabled)
        self.patch_controller.setAdvancedMode(enabled)

    def show_main_menu(self):
        self.root.showFrame("MainMenu")

    def show_patch_frame(self, mode: str):
        # Disable advanced mode switch when leaving main menu
        self.root.setAdvancedSwitchEnabled(False)

        # Read cleanup preference from main menu checkbox
        self.patch_controller.should_clean = self.main_menu_frame.cleanOldVersionsVar.get()
        # Sync the advanced-mode checkbox too
        self.patch_frame.cleanOldVersionsVar.set(self.patch_controller.should_clean)

        self.root.showFrame("PatchFrame")
        if mode == "marketplace":
            self.patch_frame.titleLabel.configure(
                text="Patch from Marketplace")
            self.patch_controller.startMarketplacePatch()
        else:
            self.patch_frame.titleLabel.configure(text="Patch from Zip/McPack")
            self.patch_controller.startZipPatch()

    def show_clean_frame(self):
        # Disable advanced mode switch when leaving main menu
        self.root.setAdvancedSwitchEnabled(False)

        self.clean_controller.startScan()
        self.root.showFrame("CleanFrame")

    def show_fix_frame(self):
        # Disable advanced mode switch when leaving main menu
        self.root.setAdvancedSwitchEnabled(False)

        self.root.showFrame("FixFrame")

    def back_to_main(self):
        # Re-enable advanced mode switch when returning to main menu
        self.root.setAdvancedSwitchEnabled(True)

        # If patching was in progress, clean up
        if hasattr(self, 'patch_controller') and self.patch_frame.is_patching:
            self.patch_controller.cleanup()
            self.patch_frame.is_patching = False

        self.root.showFrame("MainMenu")

    def _get_options_files_then(self, callback):
        """
        Resolves which options.txt file(s) to work with, then calls
        callback(selected_paths).  Shows a picker when multiple files exist.
        """
        all_files = self.config.find_all_options_txt()

        if not all_files:
            # Fallback: try legacy single-file lookup
            single = self.config.find_options_txt()
            if single:
                all_files = [("options.txt", single)]
            else:
                messagebox.showerror(
                    "Error", "Could not find any Minecraft options.txt.")
                return

        # Always show picker so the user can browse for additional files
        OptionsFilePickerModal(self.root, all_files, callback)

    def show_rtx_settings(self):
        def on_files_selected(paths):
            # Define callback to apply changes to every selected file
            def on_apply(changes):
                success_count = 0
                for path in paths:
                    current_options = self.config.read_options_txt(path)
                    for k, v in changes.items():
                        current_options[k] = v
                    if self.config.write_options_txt(path, current_options):
                        success_count += 1

                if success_count == len(paths):
                    messagebox.showinfo("Settings",
                                        f"RTX Settings applied to {success_count} file(s).")
                else:
                    messagebox.showwarning("Settings",
                                           f"Applied to {success_count}/{len(paths)} file(s). Some failed.")

            RTXSettingsModal(self.root, on_apply)

        self._get_options_files_then(on_files_selected)

    def show_all_settings(self):
        def on_files_selected(paths):
            # Read from first file for editing UI
            current_options = self.config.read_options_txt(paths[0])

            def on_save(new_config):
                success_count = 0
                for path in paths:
                    if self.config.write_options_txt(path, new_config):
                        success_count += 1

                if success_count == len(paths):
                    messagebox.showinfo("Settings",
                                        f"Configuration saved to {success_count} file(s).")
                else:
                    messagebox.showwarning("Settings",
                                           f"Saved to {success_count}/{len(paths)} file(s). Some failed.")

            AllSettingsWindow(self.root, current_options, on_save)

        self._get_options_files_then(on_files_selected)

    def run(self):
        self.root.mainloop()

    def quit(self):
        self.root.destroy()
