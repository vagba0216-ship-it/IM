import datetime
import customtkinter as ctk

from database import DatabaseManager
from views.inventory_view import InventoryView
from views.presets_view import PresetsView
from views.pos_view import POSView
from views.estimator_view import EstimatorView
from views.sales_view import SalesView

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ModernAutoPartsERP(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Auto Parts Supply - Enterprise ERP System")
        self.geometry("1340x820")

        self.db = DatabaseManager()

        self.cart = []
        self.filter_low_stock = False
        self.current_view = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()

        self.main_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=25, pady=25, sticky="nsew")

        self.show_inventory_view()

    def _build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")

        brand_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        brand_frame.pack(fill="x", padx=20, pady=(25, 20))

        ctk.CTkLabel(brand_frame, text="⚡ AUTO PARTS", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(brand_frame, text="Enterprise ERP System", font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

        self.btn_nav_inv = self.create_nav_button("📦  Inventory System", self.show_inventory_view)
        self.btn_nav_presets = self.create_nav_button("⚙️  Presets & Configs", self.show_presets_view)
        self.btn_nav_pos = self.create_nav_button("🛒  POS Terminal", self.show_pos_view)
        self.btn_nav_est = self.create_nav_button("🧮  Job Estimator", self.show_estimator_view)
        self.btn_nav_sales = self.create_nav_button("🧾  Sales Analytics", self.show_sales_view)

        theme_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        theme_frame.pack(side="bottom", fill="x", padx=20, pady=20)

        ctk.CTkLabel(theme_frame, text="Appearance Theme", font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", pady=(0, 5))
        self.theme_option = ctk.CTkOptionMenu(theme_frame, values=["Dark", "Light", "System"], command=lambda m: ctk.set_appearance_mode(m))
        self.theme_option.pack(fill="x")

    def create_nav_button(self, text, command):
        btn = ctk.CTkButton(
            self.sidebar_frame, text=text, font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w", height=42, corner_radius=8, fg_color="transparent",
            text_color=("gray10", "gray90"), hover_color=("gray85", "gray25"), command=command
        )
        btn.pack(fill="x", padx=15, pady=4)
        return btn

    def clear_main_frame(self):
        if self.current_view is not None:
            self.current_view.destroy()

    def show_inventory_view(self):
        self.clear_main_frame()
        self.current_view = InventoryView(self.main_frame, self.db, self)
        self.current_view.pack(fill="both", expand=True)

    def show_presets_view(self):
        self.clear_main_frame()
        self.current_view = PresetsView(self.main_frame, self.db, self)
        self.current_view.pack(fill="both", expand=True)

    def show_pos_view(self):
        self.clear_main_frame()
        self.current_view = POSView(self.main_frame, self.db, self)
        self.current_view.pack(fill="both", expand=True)

    def show_estimator_view(self):
        self.clear_main_frame()
        self.current_view = EstimatorView(self.main_frame, self.db, self)
        self.current_view.pack(fill="both", expand=True)

    def show_sales_view(self):
        self.clear_main_frame()
        self.current_view = SalesView(self.main_frame, self.db, self)
        self.current_view.pack(fill="both", expand=True)

    def trigger_low_stock_filter(self):
        self.filter_low_stock = not self.filter_low_stock
        self.show_inventory_view()

    def render_kpi_cards(self, parent):
        kpi_frame = ctk.CTkFrame(parent, fg_color="transparent")
        kpi_frame.pack(fill="x", pady=(0, 15))
        kpi_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="kpi")

        conn = self.db.get_connection()
        total_items, low_stock, today_revenue, month_revenue = 0, 0, 0.0, 0.0

        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT SUM(qty) as total_qty FROM inventory")
            inv_stat = cursor.fetchone()
            total_items = inv_stat["total_qty"] or 0 if inv_stat else 0

            cursor.execute("SELECT COUNT(*) as count FROM inventory WHERE qty <= 5")
            low_stat = cursor.fetchone()
            low_stock = low_stat["count"] or 0 if low_stat else 0

            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            cursor.execute("SELECT SUM(total_amount) as rev FROM sales WHERE DATE(sale_date) = %s", (today_str,))
            sales_stat = cursor.fetchone()
            today_revenue = sales_stat["rev"] or 0.0 if sales_stat else 0.0

            month_str = datetime.datetime.now().strftime("%Y-%m")
            cursor.execute("SELECT SUM(total_amount) as m_rev FROM sales WHERE DATE_FORMAT(sale_date, '%%Y-%%m') = %s", (month_str,))
            m_stat = cursor.fetchone()
            month_revenue = m_stat["m_rev"] or 0.0 if m_stat else 0.0

            cursor.close()
            conn.close()

        cards_data = [
            ("Total Stock", f"{total_items:,} pcs", "📦", "#1f6aa5", None),
            ("Low Stock Alert (Click)", f"{low_stock} Items", "⚠️", "#d9534f" if low_stock > 0 else "#2ba84a", self.trigger_low_stock_filter),
            ("Today's Revenue", f"₱{today_revenue:,.2f}", "☀️", "#2ba84a", None),
            ("This Month's Rev.", f"₱{month_revenue:,.2f}", "📅", "#6b3e75", None),
        ]

        for idx, (title, val, icon, accent_color, click_cmd) in enumerate(cards_data):
            card = ctk.CTkFrame(kpi_frame, corner_radius=12)
            card.grid(row=0, column=idx, padx=6, pady=2, sticky="nsew")

            top_line = ctk.CTkFrame(card, fg_color=accent_color, height=4, corner_radius=2)
            top_line.pack(fill="x", side="top")

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=12, pady=10)

            ctk.CTkLabel(inner, text=f"{icon} {title}", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(anchor="w")

            if click_cmd:
                btn_val = ctk.CTkButton(inner, text=val, font=ctk.CTkFont(size=18, weight="bold"), fg_color="transparent", text_color=accent_color, hover_color=("gray85", "gray25"), anchor="w", command=click_cmd)
                btn_val.pack(anchor="w", pady=(2, 0))
            else:
                ctk.CTkLabel(inner, text=val, font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(4, 0))


if __name__ == "__main__":
    app = ModernAutoPartsERP()
    app.mainloop()