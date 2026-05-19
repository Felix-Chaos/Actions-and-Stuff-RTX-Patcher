"""
Theme Configuration for A&S RTX Patcher (Neon Dark)
"""

from PIL import Image
import customtkinter as ctk

# Color Palette (Monochrome & Neon)
COLOR_BG_TOP = "#2a2a2a"      # Lighter Gray (Top of Gradient)
COLOR_BG_BOTTOM = "#000000"   # Pure Black (Bottom of Gradient)

# Very dark gray/black for cards (semi-transparent feel)
COLOR_SURFACE = "#111111"

COLOR_ACCENT_1 = "#39FF14"    # Neon Green (Buttons)
COLOR_ACCENT_2 = "#00F3FF"    # Cyan (Buttons)

COLOR_TEXT = "#FFFFFF"        # White
COLOR_TEXT_DIM = "#AAAAAA"    # Dim Gray

COLOR_BORDER_MONO = "#444444"  # Standard Monochrome Border

# Standard Font
FONT_FAMILY = "Segoe UI"


def create_gradient_image(width, height, color1, color2):
    """Generates a vertical gradient image."""
    base = Image.new('RGB', (width, height), color1)
    bottom = Image.new('RGB', (width, height), color2)

    mask = Image.new('L', (width, height))
    mask_data = []
    for y in range(height):
        for _ in range(width):
            mask_data.append(int(255 * (y / height)))
    mask.putdata(mask_data)

    base.paste(bottom, (0, 0), mask)
    return base


def apply_theme():
    """Applies the base CustomTkinter theme settings."""
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("dark-blue")

# Stylized Element Helpers


def get_button_style(style="primary"):
    """Returns dictionary of kwargs for CTkButton based on style."""
    if style == "primary":
        # Neon Green Outline/Text
        return {
            "fg_color": "transparent",
            "border_width": 2,
            "border_color": COLOR_ACCENT_1,
            "text_color": COLOR_ACCENT_1,
            "hover_color": "#1a331a"
        }
    if style == "secondary":
        # Cyan Outline/Text
        return {
            "fg_color": "transparent",
            "border_width": 2,
            "border_color": COLOR_ACCENT_2,
            "text_color": COLOR_ACCENT_2,
            "hover_color": "#1a3333"
        }
    if style == "danger":
        return {
            "fg_color": "transparent",
            "border_width": 2,
            "border_color": "#FF3333",
            "text_color": "#FF3333",
            "hover_color": "#331a1a"
        }
    if style == "filled-primary":
        return {
            "fg_color": COLOR_ACCENT_1,
            "text_color": "black",
            "hover_color": "#32cc12"
        }
    return {}
