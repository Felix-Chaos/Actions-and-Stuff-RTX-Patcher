import customtkinter as ctk
from src.gui.theme import COLOR_BG_TOP, COLOR_BG_BOTTOM


class GradientFrame(ctk.CTkFrame):
    """
    A Frame that draws a vertical gradient background.
    """

    def __init__(self, parent, top_color=COLOR_BG_TOP, bottom_color=COLOR_BG_BOTTOM, **kwargs):
        # Remove fg_color from kwargs if present, we'll set it to transparent
        kwargs['fg_color'] = 'transparent'
        super().__init__(parent, **kwargs)
        self.top_color = top_color
        self.bottom_color = bottom_color

        # We use a Canvas implementation for the gradient
        self.canvas = ctk.CTkCanvas(
            self, highlightthickness=0, bg=bottom_color)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)

        self.bind("<Configure>", self._draw_gradient)

    def _hex_to_rgb(self, hex_col):
        hex_col = hex_col.lstrip('#')
        return tuple(int(hex_col[i:i+2], 16) for i in (0, 2, 4))

    def _rgb_to_hex(self, rgb):
        return '#%02x%02x%02x' % rgb

    def _draw_gradient(self, event=None):
        """Draws the gradient on the canvas."""
        width = self.winfo_width()
        height = self.winfo_height()

        if width < 1 or height < 1:
            return

        self.canvas.delete("gradient")

        # Limit steps for performance
        steps = min(height, 100)

        r1, g1, b1 = self._hex_to_rgb(self.top_color)
        r2, g2, b2 = self._hex_to_rgb(self.bottom_color)

        for i in range(steps):
            r = int(r1 + (r2 - r1) * i / steps)
            g = int(g1 + (g2 - g1) * i / steps)
            b = int(b1 + (b2 - b1) * i / steps)
            color = self._rgb_to_hex((r, g, b))

            y0 = int(i * height / steps)
            y1 = int((i + 1) * height / steps)

            self.canvas.create_rectangle(
                0, y0, width, y1, fill=color, outline=color, tags="gradient")
