import customtkinter as ctk
from tkinter import messagebox
import mysql.connector


class PresetsView(ctk.CTkFrame):
    def __init__(self, master, db_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.db = db_manager
        self.app = app_instance

        self.build_ui()

    def fetch_presets(self, category):
        conn = self.db.get_connection()
        if not conn:
            return []
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT value FROM presets WHERE category = %s ORDER BY value ASC", (category,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r["value"] for r in rows]

    def bind_mouse_wheel(self, scrollable_frame):
        canvas = scrollable_frame._parent_canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        def _bind_children(widget):
            widget.bind("<MouseWheel>", _on_mousewheel, add="+")
            for child in widget.winfo_children():
                _bind_children(child)
        scrollable_frame.bind("<MouseWheel>", _on_mousewheel, add="+")
        canvas.bind("<MouseWheel>", _on_mousewheel, add="+")
        _bind_children(scrollable_frame)

    def build_ui(self):
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(title_frame, text="Presets & Sub-System Configuration", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Configure reusable Particulars, Brands, and Units to speed up manual entry", font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure((0, 1, 2), weight=1)

        self.render_preset_card(grid, "Particulars / Categories", "particulars", 0)
        self.render_preset_card(grid, "Brands", "brand", 1)
        self.render_preset_card(grid, "Measurement Units", "unit", 2)

    def render_preset_card(self, parent, title, cat_key, col_idx):
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.grid(row=0, column=col_idx, padx=8, pady=5, sticky="nsew")

        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))

        entry = ctk.CTkEntry(card, placeholder_text=f"New {title[:-1]}...", height=36)
        entry.pack(fill="x", padx=15, pady=8)

        btn_add = ctk.CTkButton(card, text="Add Preset ➕", height=32, fg_color="#2ba84a", command=lambda: self.add_preset_item(cat_key, entry.get().strip()))
        btn_add.pack(fill="x", padx=15, pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(card, corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        presets = self.fetch_presets(cat_key)
        for val in presets:
            row = ctk.CTkFrame(scroll, fg_color=("gray90", "gray20"))
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=val, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)
            ctk.CTkButton(row, text="❌", width=28, height=24, fg_color="transparent", text_color="#d9534f", command=lambda v=val: self.delete_preset_item(cat_key, v)).pack(side="right", padx=5)

        self.bind_mouse_wheel(scroll)

    def add_preset_item(self, category, val):
        if not val:
            return
        conn = self.db.get_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO presets (category, value) VALUES (%s, %s)", (category, val))
                conn.commit()
            except mysql.connector.Error:
                messagebox.showwarning("Duplicate", "This preset value already exists.")
            finally:
                cursor.close()
                conn.close()
            self.app.show_presets_view()

    def delete_preset_item(self, category, val):
        conn = self.db.get_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM presets WHERE category=%s AND value=%s", (category, val))
            conn.commit()
            cursor.close()
            conn.close()
            self.app.show_presets_view()