import datetime
import os
import csv
import customtkinter as ctk
from tkinter import messagebox, filedialog
import mysql.connector
from PIL import Image

# Graphing & Visualization
import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# PDF Generation Library
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# Set Modern Appearance Theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ==============================================================================
# DATABASE CONFIGURATION & SECURE INITIALIZATION
# ==============================================================================

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "test",
}


def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"]
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
        cursor.close()
        conn.close()
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        print(f"Database Security Error: {err}")
        return None


def init_db():
    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            item_id INT AUTO_INCREMENT PRIMARY KEY,
            particulars VARCHAR(255) NOT NULL,
            brand VARCHAR(100) DEFAULT '',
            description VARCHAR(255) NOT NULL,
            unit VARCHAR(50) NOT NULL DEFAULT 'pcs',
            qty INT NOT NULL DEFAULT 0,
            unit_cost DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            image_path TEXT DEFAULT NULL,
            INDEX idx_particulars (particulars),
            INDEX idx_search (description, brand)
        ) ENGINE=InnoDB
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presets (
            preset_id INT AUTO_INCREMENT PRIMARY KEY,
            category VARCHAR(50) NOT NULL,
            value VARCHAR(255) NOT NULL UNIQUE
        ) ENGINE=InnoDB
    """)

    default_presets = [
        ('unit', 'pcs'), ('unit', 'set'), ('unit', 'box'), ('unit', 'ltr'), ('unit', 'can'),
        ('particulars', 'Oil filter'), ('particulars', 'Fuel filter'), ('particulars', 'Brake pad'),
        ('particulars', 'Spark plug'),
        ('brand', 'Vic'), ('brand', 'Baldwin'), ('brand', 'Bosch'), ('brand', 'NGK')
    ]
    cursor.executemany("INSERT IGNORE INTO presets (category, value) VALUES (%s, %s)", default_presets)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            sale_id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            vatable_sales DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            vat_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            total_amount DECIMAL(10,2) NOT NULL,
            sale_date DATETIME NOT NULL,
            INDEX idx_sale_date (sale_date)
        ) ENGINE=InnoDB
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            sale_item_id INT AUTO_INCREMENT PRIMARY KEY,
            sale_id INT,
            item_id INT,
            qty_sold INT,
            unit_cost DECIMAL(10,2),
            subtotal DECIMAL(10,2),
            FOREIGN KEY (sale_id) REFERENCES sales (sale_id) ON DELETE CASCADE,
            FOREIGN KEY (item_id) REFERENCES inventory (item_id) ON DELETE RESTRICT
        ) ENGINE=InnoDB
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_estimates (
            estimate_id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            vehicle_details VARCHAR(255),
            parts_cost DECIMAL(10,2) NOT NULL,
            materials_cost DECIMAL(10,2) NOT NULL,
            labor_cost DECIMAL(10,2) NOT NULL,
            total_estimate DECIMAL(10,2) NOT NULL,
            estimate_date DATETIME NOT NULL
        ) ENGINE=InnoDB
    """)

    conn.commit()
    cursor.close()
    conn.close()


# ==============================================================================
# PDF RECEIPT GENERATOR
# ==============================================================================

def generate_pdf_receipt(file_path, sale_id, customer, date_str, items, total):
    vatable_sales = total / 1.12
    vat_amount = total - vatable_sales

    doc = SimpleDocTemplate(file_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()

    header_data = [
        [
            Paragraph(
                "<b>Auto Parts Supply Inc.</b><br/>123 Mechanic St., Manila, Philippines<br/>VAT Reg. TIN: 000-123-456-0000",
                styles["Normal"]),
            Paragraph("<font size=20 color='#4a285d'><b>OFFICIAL RECEIPT</b></font>", styles["Normal"])
        ]
    ]
    header_table = Table(header_data, colWidths=[300, 240])
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
    story.append(header_table)
    story.append(Spacer(1, 20))

    info_data = [
        [
            Paragraph(f"<b>Billed To:</b><br/>{customer}", styles["Normal"]),
            Paragraph(f"<b>Receipt #:</b> {sale_id:06d}<br/><b>Date:</b> {date_str}", styles["Normal"])
        ]
    ]
    info_table = Table(info_data, colWidths=[300, 240])
    info_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
    story.append(info_table)
    story.append(Spacer(1, 20))

    table_data = [["QTY", "Particulars & Description", "Unit Cost", "Amount"]]
    for item in items:
        desc_str = f"{item['particulars']} - {item['description']}" if item.get('description') else item['particulars']
        table_data.append([
            str(item["qty"]),
            desc_str,
            f"PHP {item['unit_cost']:,.2f}",
            f"PHP {item['subtotal']:,.2f}"
        ])

    item_table = Table(table_data, colWidths=[50, 270, 110, 110])
    item_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6b3e75')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0'))
    ]))
    story.append(item_table)
    story.append(Spacer(1, 15))

    totals_data = [
        ["Vatable Sales:", f"PHP {vatable_sales:,.2f}"],
        ["12% VAT Amount:", f"PHP {vat_amount:,.2f}"],
        ["TOTAL AMOUNT DUE:", f"PHP {total:,.2f}"]
    ]
    totals_table = Table(totals_data, colWidths=[380, 160])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
        ('LINEABOVE', (0, 2), (-1, 2), 1, colors.HexColor('#6b3e75'))
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 30))

    notes = Paragraph(
        "<b>Notes:</b><br/>Prices are inclusive of 12% VAT. Thank you for your purchase! Please retain this receipt for warranty or exchange purposes within 30 days.",
        styles["Normal"])
    story.append(notes)

    doc.build(story)


# ==============================================================================
# MAIN SYSTEM GUI
# ==============================================================================

class ModernAutoPartsERP(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Auto Parts Supply - Enterprise ERP System")
        self.geometry("1340x820")

        self.cart = []
        self.estimate_items = []
        self.selected_item_id = None
        self.current_image_path = None
        self.filter_low_stock = False

        # Inventory Pagination & Global Sort State
        self.inv_page = 1
        self.inv_page_size = 5  # Pagination by Category count (5 per page)
        self.sort_column = None
        self.sort_direction = None
        self.expanded_categories = set()

        # POS Pagination & Sort State
        self.pos_page = 1
        self.pos_page_size = 5  # Pagination by Category count (5 per page)
        self.pos_sort_column = None
        self.pos_sort_direction = None
        self.pos_expanded_categories = set()

        self.sales_sort_column = None
        self.sales_sort_direction = None

        self.search_timer = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar Navigation
        self.sidebar_frame = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")

        brand_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        brand_frame.pack(fill="x", padx=20, pady=(25, 20))

        ctk.CTkLabel(brand_frame, text="⚡ AUTO PARTS", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(brand_frame, text="Enterprise ERP System", font=ctk.CTkFont(size=12), text_color="gray").pack(
            anchor="w")

        self.btn_nav_inv = self.create_nav_button("📦  Inventory System", self.show_inventory_view)
        self.btn_nav_presets = self.create_nav_button("⚙️  Presets & Configs", self.show_presets_view)
        self.btn_nav_pos = self.create_nav_button("🛒  POS Terminal", self.show_pos_view)
        self.btn_nav_est = self.create_nav_button("🧮  Job Estimator", self.show_estimator_view)
        self.btn_nav_sales = self.create_nav_button("🧾  Sales Analytics", self.show_sales_view)

        theme_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        theme_frame.pack(side="bottom", fill="x", padx=20, pady=20)

        ctk.CTkLabel(theme_frame, text="Appearance Theme", font=ctk.CTkFont(size=11), text_color="gray").pack(
            anchor="w", pady=(0, 5))
        self.theme_option = ctk.CTkOptionMenu(theme_frame, values=["Dark", "Light", "System"],
                                              command=lambda m: ctk.set_appearance_mode(m))
        self.theme_option.pack(fill="x")

        # Workspace Container
        self.main_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=25, pady=25, sticky="nsew")

        self.show_inventory_view()

    def create_nav_button(self, text, command):
        btn = ctk.CTkButton(
            self.sidebar_frame,
            text=text,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
            height=42,
            corner_radius=8,
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray85", "gray25"),
            command=command
        )
        btn.pack(fill="x", padx=15, pady=4)
        return btn

    def clear_main_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def fetch_presets(self, category):
        conn = get_db_connection()
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

    def debounce_search(self, callback_func, delay=250):
        if self.search_timer is not None:
            self.after_cancel(self.search_timer)
        self.search_timer = self.after(delay, callback_func)

    # --------------------------------------------------------------------------
    # KPI CARDS
    # --------------------------------------------------------------------------
    def render_kpi_cards(self, parent):
        kpi_frame = ctk.CTkFrame(parent, fg_color="transparent")
        kpi_frame.pack(fill="x", pady=(0, 15))
        kpi_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="kpi")

        conn = get_db_connection()
        total_items, low_stock, today_revenue, month_revenue = 0, 0, 0.0, 0.0

        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT SUM(qty) as total_qty FROM inventory")
            inv_stat = cursor.fetchone()
            total_items = inv_stat["total_qty"] or 0

            cursor.execute("SELECT COUNT(*) as count FROM inventory WHERE qty <= 5")
            low_stock = cursor.fetchone()["count"] or 0

            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            cursor.execute("SELECT SUM(total_amount) as rev FROM sales WHERE DATE(sale_date) = %s", (today_str,))
            sales_stat = cursor.fetchone()
            today_revenue = sales_stat["rev"] or 0.0

            month_str = datetime.datetime.now().strftime("%Y-%m")
            cursor.execute("SELECT SUM(total_amount) as m_rev FROM sales WHERE DATE_FORMAT(sale_date, '%%Y-%%m') = %s",
                           (month_str,))
            m_stat = cursor.fetchone()
            month_revenue = m_stat["m_rev"] or 0.0

            cursor.close()
            conn.close()

        cards_data = [
            ("Total Stock", f"{total_items:,} pcs", "📦", "#1f6aa5", None),
            ("Low Stock Alert (Click)", f"{low_stock} Items", "⚠️", "#d9534f" if low_stock > 0 else "#2ba84a",
             self.trigger_low_stock_filter),
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

            ctk.CTkLabel(inner, text=f"{icon} {title}", font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="gray").pack(anchor="w")

            if click_cmd:
                btn_val = ctk.CTkButton(inner, text=val, font=ctk.CTkFont(size=18, weight="bold"),
                                        fg_color="transparent", text_color=accent_color,
                                        hover_color=("gray85", "gray25"), anchor="w", command=click_cmd)
                btn_val.pack(anchor="w", pady=(2, 0))
            else:
                ctk.CTkLabel(inner, text=val, font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(4, 0))

    def trigger_low_stock_filter(self):
        self.filter_low_stock = not self.filter_low_stock
        self.inv_page = 1
        self.show_inventory_view()

    # --------------------------------------------------------------------------
    # 1. INVENTORY MODULE (CATEGORY-BASED PAGINATION + GLOBAL SORTING)
    # --------------------------------------------------------------------------
    def show_inventory_view(self):
        self.clear_main_frame()

        title_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 10))

        status_text = " (Filtering Low Stock <= 5)" if self.filter_low_stock else ""
        ctk.CTkLabel(title_frame, text=f"Inventory Dashboard{status_text}",
                     font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Hierarchical stock view, pre-set values, and bulk CSV export/import",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

        self.render_kpi_cards(self.main_frame)

        content_split = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        content_split.pack(fill="both", expand=True)
        content_split.grid_columnconfigure(0, weight=3)
        content_split.grid_columnconfigure(1, weight=2)

        left_card = ctk.CTkFrame(content_split, corner_radius=12)
        left_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        ctrl_bar = ctk.CTkFrame(left_card, fg_color="transparent")
        ctrl_bar.pack(fill="x", padx=15, pady=12)

        self.inv_search = ctk.CTkEntry(ctrl_bar, placeholder_text="🔍 Search category, brand, or description...",
                                       height=36)
        self.inv_search.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.inv_search.bind("<KeyRelease>", lambda e: self.debounce_search(self.reset_and_load_inventory))

        if self.filter_low_stock:
            btn_clear_filter = ctk.CTkButton(ctrl_bar, text="Clear Filter ❌", height=36, fg_color="#d9534f",
                                             command=self.trigger_low_stock_filter)
            btn_clear_filter.pack(side="right", padx=(5, 0))

        btn_export = ctk.CTkButton(ctrl_bar, text="Export CSV 📄", height=36, fg_color="#2ba84a",
                                   command=self.export_csv_dialog)
        btn_export.pack(side="right", padx=(5, 0))

        btn_import = ctk.CTkButton(ctrl_bar, text="Import CSV 📁", height=36, fg_color="#1f6aa5",
                                   command=self.import_csv_dialog)
        btn_import.pack(side="right")

        self.stock_scroll = ctk.CTkScrollableFrame(left_card, corner_radius=8)
        self.stock_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        # Pagination Control Bar
        self.inv_page_bar = ctk.CTkFrame(left_card, fg_color="transparent", height=36)
        self.inv_page_bar.pack(fill="x", padx=15, pady=(0, 12))

        form_card = ctk.CTkFrame(content_split, corner_radius=12)
        form_card.grid(row=0, column=1, padx=(10, 0), sticky="nsew")

        ctk.CTkLabel(form_card, text="Stock Item Details", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w",
                                                                                                          padx=20,
                                                                                                          pady=(15, 2))
        ctk.CTkLabel(form_card, text="Use dropdown presets or type custom values", font=ctk.CTkFont(size=11),
                     text_color="gray").pack(anchor="w", padx=20, pady=(0, 10))

        self.image_preview_label = ctk.CTkLabel(form_card, text="No Image Attached", width=120, height=75,
                                                fg_color=("gray85", "gray25"), corner_radius=8)
        self.image_preview_label.pack(pady=4)

        btn_img = ctk.CTkButton(form_card, text="Attach Image 📷", height=26, fg_color="transparent",
                                text_color=("gray10", "gray90"), border_width=1, command=self.select_image_file)
        btn_img.pack(pady=(0, 8))

        particulars_presets = self.fetch_presets('particulars') or ["Oil filter", "Fuel filter", "Brake pad"]
        self.inv_particulars_opt = ctk.CTkOptionMenu(form_card, values=particulars_presets, height=34,
                                                     command=lambda v: self.set_particulars_input(v))
        self.inv_particulars_opt.pack(fill="x", padx=20, pady=4)

        self.inv_particulars = ctk.CTkEntry(form_card, placeholder_text="Particulars / Category", height=34)
        self.inv_particulars.pack(fill="x", padx=20, pady=4)

        brand_presets = self.fetch_presets('brand') or ["Vic", "Baldwin", "Bosch"]
        self.inv_brand_opt = ctk.CTkOptionMenu(form_card, values=brand_presets, height=34,
                                               command=lambda v: self.set_brand_input(v))
        self.inv_brand_opt.pack(fill="x", padx=20, pady=4)

        self.inv_brand = ctk.CTkEntry(form_card, placeholder_text="Brand", height=34)
        self.inv_brand.pack(fill="x", padx=20, pady=4)

        self.inv_desc = ctk.CTkEntry(form_card, placeholder_text="Description / Model Code (e.g. C226)", height=34)
        self.inv_desc.pack(fill="x", padx=20, pady=4)

        row_meta = ctk.CTkFrame(form_card, fg_color="transparent")
        row_meta.pack(fill="x", padx=20, pady=4)
        row_meta.grid_columnconfigure((0, 1), weight=1)

        self.inv_qty = ctk.CTkEntry(row_meta, placeholder_text="Qty", height=34)
        self.inv_qty.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        unit_presets = self.fetch_presets('unit') or ["pcs", "set", "box"]
        self.inv_unit_opt = ctk.CTkOptionMenu(row_meta, values=unit_presets, height=34)
        self.inv_unit_opt.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        self.inv_cost = ctk.CTkEntry(form_card, placeholder_text="Unit Cost (₱)", height=34)
        self.inv_cost.pack(fill="x", padx=20, pady=4)

        btn_bar = ctk.CTkFrame(form_card, fg_color="transparent")
        btn_bar.pack(fill="x", padx=20, pady=(15, 10))

        ctk.CTkButton(btn_bar, text="Save / Update Item", fg_color="#2ba84a", hover_color="#1e7a35", height=38,
                      font=ctk.CTkFont(weight="bold"), command=self.save_inventory_item).pack(fill="x", pady=4)
        ctk.CTkButton(btn_bar, text="Delete Selected", fg_color="#d9534f", hover_color="#b52b27", height=34,
                      command=self.delete_inventory_item).pack(fill="x", pady=4)
        ctk.CTkButton(btn_bar, text="Clear Form", fg_color="transparent", text_color="gray",
                      command=self.reset_inventory_form).pack(fill="x", pady=2)

        self.load_inventory_table()

    def reset_and_load_inventory(self):
        self.inv_page = 1
        self.load_inventory_table()

    def set_particulars_input(self, val):
        self.inv_particulars.delete(0, 'end')
        self.inv_particulars.insert(0, val)

    def set_brand_input(self, val):
        self.inv_brand.delete(0, 'end')
        self.inv_brand.insert(0, val)

    def select_image_file(self):
        f = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")])
        if f:
            self.current_image_path = os.path.abspath(f)
            self.display_image_preview(f)

    def display_image_preview(self, path):
        if path and os.path.exists(path):
            try:
                img = Image.open(path)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 75))
                self.image_preview_label.configure(image=ctk_img, text="")
                return
            except Exception:
                pass
        self.image_preview_label.configure(image=None, text="No Image")

    def reset_inventory_form(self):
        self.selected_item_id = None
        self.current_image_path = None
        self.inv_particulars.delete(0, 'end')
        self.inv_brand.delete(0, 'end')
        self.inv_qty.delete(0, 'end')
        self.inv_desc.delete(0, 'end')
        self.inv_cost.delete(0, 'end')
        self.display_image_preview(None)

    def save_inventory_item(self):
        particulars = self.inv_particulars.get().strip()
        desc = self.inv_desc.get().strip()
        qty = self.inv_qty.get().strip()
        unit = self.inv_unit_opt.get().strip()
        cost = self.inv_cost.get().strip()

        if not particulars or not desc or not qty or not cost:
            messagebox.showwarning("Warning", "Particulars, Description, Qty, and Unit Cost are required.")
            return

        try:
            clean_qty = int(qty)
            clean_cost = float(cost)
        except ValueError:
            messagebox.showerror("Invalid Input", "Qty must be an integer and Unit Cost must be a number.")
            return

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            if self.selected_item_id:
                cursor.execute("""
                    UPDATE inventory SET particulars=%s, brand=%s, description=%s, unit=%s, qty=%s, unit_cost=%s, image_path=%s WHERE item_id=%s
                """, (particulars, self.inv_brand.get().strip(), desc, unit, clean_qty, clean_cost,
                      self.current_image_path, self.selected_item_id))
            else:
                cursor.execute("""
                    INSERT INTO inventory (particulars, brand, description, unit, qty, unit_cost, image_path) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (particulars, self.inv_brand.get().strip(), desc, unit, clean_qty, clean_cost,
                      self.current_image_path))
            conn.commit()
            cursor.close()
            conn.close()
            self.reset_inventory_form()
            self.show_inventory_view()

    def delete_inventory_item(self):
        if not self.selected_item_id:
            messagebox.showwarning("Select Item", "Please select an item from the table to delete.")
            return
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM inventory WHERE item_id = %s", (self.selected_item_id,))
                conn.commit()
            except mysql.connector.Error:
                messagebox.showerror("Security Error", "Cannot delete item connected to existing sales records.")
            finally:
                cursor.close()
                conn.close()
            self.reset_inventory_form()
            self.show_inventory_view()

    def toggle_column_sort(self, col_key):
        if self.sort_column != col_key:
            self.sort_column = col_key
            self.sort_direction = "ASC"
        elif self.sort_direction == "ASC":
            self.sort_direction = "DESC"
        else:
            self.sort_column = None
            self.sort_direction = None
        self.load_inventory_table()

    def toggle_category_accordion(self, category_name):
        if category_name in self.expanded_categories:
            self.expanded_categories.remove(category_name)
        else:
            self.expanded_categories.add(category_name)
        self.load_inventory_table()

    def load_inventory_table(self):
        for widget in self.stock_scroll.winfo_children():
            widget.destroy()

        conn = get_db_connection()
        if not conn:
            return

        query_str = self.inv_search.get().strip() if hasattr(self, 'inv_search') else ""

        # Global Order By SQL clause
        order_clause = "ORDER BY particulars ASC, description ASC"
        if self.sort_column and self.sort_direction:
            col_map = {
                "qty": "qty",
                "unit": "unit",
                "particulars": "particulars",
                "description": "description",
                "unit_cost": "unit_cost",
                "amount": "(qty * unit_cost)"
            }
            db_col = col_map.get(self.sort_column, "particulars")
            order_clause = f"ORDER BY {db_col} {self.sort_direction}, particulars ASC"

        cursor = conn.cursor(dictionary=True)
        if self.filter_low_stock:
            cursor.execute(
                f"SELECT *, (qty * unit_cost) AS amount FROM inventory WHERE qty <= 5 AND (particulars LIKE %s OR description LIKE %s OR brand LIKE %s) {order_clause}",
                (f"%{query_str}%", f"%{query_str}%", f"%{query_str}%"))
        else:
            cursor.execute(
                f"SELECT *, (qty * unit_cost) AS amount FROM inventory WHERE particulars LIKE %s OR description LIKE %s OR brand LIKE %s {order_clause}",
                (f"%{query_str}%", f"%{query_str}%", f"%{query_str}%"))
        all_items = cursor.fetchall()
        cursor.close()
        conn.close()

        # Render Header Controls
        headers = [
            ("Qty", "qty"),
            ("Unit", "unit"),
            ("Particulars", "particulars"),
            ("Description", "description"),
            ("Unit Cost", "unit_cost"),
            ("Amount", "amount")
        ]

        header_frame = ctk.CTkFrame(self.stock_scroll, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 5))

        for idx, (label_text, col_key) in enumerate(headers):
            sort_arrow = " ↕"
            if self.sort_column == col_key:
                sort_arrow = " ▲" if self.sort_direction == "ASC" else " ▼"

            btn = ctk.CTkButton(
                header_frame,
                text=f"{label_text}{sort_arrow}",
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="transparent",
                text_color="gray",
                hover_color=("gray85", "gray25"),
                height=24,
                command=lambda k=col_key: self.toggle_column_sort(k)
            )
            btn.pack(side="left", expand=True, fill="x")

        # Group items preserving global order
        grouped = {}
        for item in all_items:
            part = item["particulars"]
            if part not in grouped:
                grouped[part] = []
            grouped[part].append(item)

        categories_list = list(grouped.keys())
        total_categories = len(categories_list)

        # Apply Category-Based Pagination (e.g. 5 categories per page)
        if self.inv_page_size == "All":
            displayed_categories = categories_list
            total_pages = 1
        else:
            p_size = int(self.inv_page_size)
            total_pages = max(1, (total_categories + p_size - 1) // p_size)
            self.inv_page = min(self.inv_page, total_pages)
            start_idx = (self.inv_page - 1) * p_size
            displayed_categories = categories_list[start_idx:start_idx + p_size]

        # Build accordion panels for current page's categories
        for part_name in displayed_categories:
            items = grouped[part_name]
            total_qty = sum(i["qty"] for i in items)
            total_val = sum(i["amount"] for i in items)
            is_expanded = part_name in self.expanded_categories or bool(query_str) or self.filter_low_stock

            cat_card = ctk.CTkFrame(self.stock_scroll, corner_radius=8, fg_color=("gray85", "gray25"))
            cat_card.pack(fill="x", pady=3)

            cat_header = ctk.CTkFrame(cat_card, fg_color="transparent")
            cat_header.pack(fill="x", padx=10, pady=8)

            arrow = "▼" if is_expanded else "►"
            btn_toggle = ctk.CTkButton(
                cat_header,
                text=f"{arrow}  {part_name} ({len(items)} variants)",
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color="transparent",
                anchor="w",
                command=lambda p=part_name: self.toggle_category_accordion(p)
            )
            btn_toggle.pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(cat_header, text=f"Stock: {total_qty} pcs | ₱{total_val:,.2f}",
                         font=ctk.CTkFont(size=12, weight="bold"), text_color="gray").pack(side="right", padx=10)

            # Lazy Virtualization: Instantiates row widgets ONLY IF expanded
            if is_expanded:
                body = ctk.CTkFrame(cat_card, fg_color="transparent")
                body.pack(fill="x", padx=15, pady=(0, 8))

                for item in items:
                    row = ctk.CTkFrame(body, fg_color=("gray90", "gray20"), corner_radius=6)
                    row.pack(fill="x", pady=2)

                    qty_color = "#d9534f" if item['qty'] <= 5 else ("gray10", "gray90")

                    ctk.CTkLabel(row, text=f"{item['qty']}", font=ctk.CTkFont(weight="bold"), text_color=qty_color,
                                 width=40).pack(side="left", padx=5)
                    ctk.CTkLabel(row, text=f"{item['unit']}", width=40).pack(side="left", padx=5)

                    brand_str = f"[{item['brand']}] " if item['brand'] else ""
                    btn_item = ctk.CTkButton(
                        row,
                        text=f"{brand_str}{item['description']}",
                        font=ctk.CTkFont(weight="bold"),
                        fg_color="transparent",
                        anchor="w",
                        command=lambda i=item: self.select_inventory_item(i)
                    )
                    btn_item.pack(side="left", fill="x", expand=True, padx=5)

                    ctk.CTkLabel(row, text=f"₱{item['unit_cost']:,.2f}", width=80).pack(side="left", padx=5)
                    ctk.CTkLabel(row, text=f"₱{item['amount']:,.2f}", font=ctk.CTkFont(weight="bold"), width=90).pack(
                        side="right", padx=5)

        self.bind_mouse_wheel(self.stock_scroll)
        self.render_inventory_pagination(total_categories, total_pages)

    def render_inventory_pagination(self, total_categories, total_pages):
        for w in self.inv_page_bar.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.inv_page_bar, text=f"Total Categories: {total_categories}", font=ctk.CTkFont(size=11),
                     text_color="gray").pack(side="left", padx=5)

        # Page Size Option Menu (Counted by Categories)
        opt = ctk.CTkOptionMenu(
            self.inv_page_bar,
            values=["5", "10", "15", "All"],
            width=70,
            height=26,
            command=self.change_inv_page_size
        )
        opt.set(str(self.inv_page_size))
        opt.pack(side="left", padx=5)

        # Previous Page Button
        btn_prev = ctk.CTkButton(
            self.inv_page_bar,
            text="◄ Prev",
            width=65,
            height=26,
            state="normal" if self.inv_page > 1 else "disabled",
            command=self.prev_inv_page
        )
        btn_prev.pack(side="right", padx=2)

        # Page Indicator
        ctk.CTkLabel(self.inv_page_bar, text=f"Page {self.inv_page} of {total_pages}",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="right", padx=8)

        # Next Page Button
        btn_next = ctk.CTkButton(
            self.inv_page_bar,
            text="Next ►",
            width=65,
            height=26,
            state="normal" if self.inv_page < total_pages else "disabled",
            command=self.next_inv_page
        )
        btn_next.pack(side="right", padx=2)

    def change_inv_page_size(self, val):
        self.inv_page_size = val if val == "All" else int(val)
        self.inv_page = 1
        self.load_inventory_table()

    def prev_inv_page(self):
        if self.inv_page > 1:
            self.inv_page -= 1
            self.load_inventory_table()

    def next_inv_page(self):
        self.inv_page += 1
        self.load_inventory_table()

    def select_inventory_item(self, item):
        self.selected_item_id = item["item_id"]
        self.inv_particulars.delete(0, 'end')
        self.inv_particulars.insert(0, item["particulars"])
        self.inv_brand.delete(0, 'end')
        self.inv_brand.insert(0, item["brand"] or "")
        self.inv_qty.delete(0, 'end')
        self.inv_qty.insert(0, str(item["qty"]))
        self.inv_desc.delete(0, 'end')
        self.inv_desc.insert(0, item["description"] or "")
        self.inv_cost.delete(0, 'end')
        self.inv_cost.insert(0, str(item["unit_cost"]))
        self.display_image_preview(item["image_path"])

    def export_csv_dialog(self):
        f = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Document", "*.csv")],
                                         initialfile="Inventory_Export.csv")
        if not f:
            return

        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT qty AS Qty, unit AS Unit, particulars AS Particulars, description AS Description, unit_cost AS 'Unit Cost', (qty * unit_cost) AS Amount FROM inventory")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if rows:
            with open(f, mode='w', newline='', encoding='utf-8') as csv_file:
                writer = csv.DictWriter(csv_file,
                                        fieldnames=["Qty", "Unit", "Particulars", "Description", "Unit Cost", "Amount"])
                writer.writeheader()
                writer.writerows(rows)
            messagebox.showinfo("Export Successful", f"Inventory saved to {f}")

    def import_csv_dialog(self):
        f = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if not f:
            return

        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()
        imported_count = 0

        try:
            with open(f, mode='r', encoding='utf-8', errors='ignore') as csv_file:
                reader = csv.reader(csv_file)

                header = None
                for row in reader:
                    clean_row = [c.strip() for c in row if c.strip()]
                    if any('unit' in c.lower() or 'particular' in c.lower() or 'description' in c.lower() for c in
                           clean_row):
                        header = [c.strip() for c in row]
                        break

                if not header:
                    messagebox.showerror("CSV Error", "Could not find valid column headers in the CSV file.")
                    return

                header_map = {col.lower(): idx for idx, col in enumerate(header)}

                def get_val(row, key_names, default=""):
                    for k in key_names:
                        if k in header_map and header_map[k] < len(row):
                            v = row[header_map[k]].strip()
                            if v:
                                return v
                    return default

                for row in reader:
                    if not any(row):
                        continue

                    qty_str = get_val(row, ['qty.', 'qty', 'quantity'], '0')
                    unit = get_val(row, ['unit'], 'pcs')
                    particulars = get_val(row, ['particulars', 'pariculars', 'particular'], '')
                    desc = get_val(row, ['description', 'desc'], '')
                    cost_str = get_val(row, ['unit cost', 'unit_cost', 'cost', 'unitcost'], '0.0')

                    try:
                        clean_qty = int(float(qty_str.replace(',', '').replace('"', '').strip()))
                        clean_cost = float(cost_str.replace(',', '').replace('"', '').strip())
                    except ValueError:
                        continue

                    if particulars or desc:
                        if not particulars:
                            particulars = desc

                        cursor.execute("""
                            INSERT INTO inventory (qty, unit, particulars, description, unit_cost)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (clean_qty, unit, particulars, desc, clean_cost))
                        imported_count += 1

            conn.commit()
            messagebox.showinfo("Success", f"Successfully imported {imported_count} items from CSV!")
            self.show_inventory_view()
        except Exception as err:
            messagebox.showerror("CSV Error", f"Failed to import CSV file:\n{err}")
        finally:
            cursor.close()
            conn.close()

    # --------------------------------------------------------------------------
    # 2. SUB-MODULE: PRESETS & CONFIGURATIONS MANAGER
    # --------------------------------------------------------------------------
    def show_presets_view(self):
        self.clear_main_frame()

        title_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(title_frame, text="Presets & Sub-System Configuration",
                     font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Configure reusable Particulars, Brands, and Units to speed up manual entry",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

        grid = ctk.CTkFrame(self.main_frame, fg_color="transparent")
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

        btn_add = ctk.CTkButton(card, text="Add Preset ➕", height=32, fg_color="#2ba84a",
                                command=lambda: self.add_preset_item(cat_key, entry.get().strip()))
        btn_add.pack(fill="x", padx=15, pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(card, corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        presets = self.fetch_presets(cat_key)
        for val in presets:
            row = ctk.CTkFrame(scroll, fg_color=("gray90", "gray20"))
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=val, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)
            ctk.CTkButton(row, text="❌", width=28, height=24, fg_color="transparent", text_color="#d9534f",
                          command=lambda v=val: self.delete_preset_item(cat_key, v)).pack(side="right", padx=5)

        self.bind_mouse_wheel(scroll)

    def add_preset_item(self, category, val):
        if not val:
            return
        conn = get_db_connection()
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
            self.show_presets_view()

    def delete_preset_item(self, category, val):
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM presets WHERE category=%s AND value=%s", (category, val))
            conn.commit()
            cursor.close()
            conn.close()
            self.show_presets_view()

    # --------------------------------------------------------------------------
    # 3. HIGH-PERFORMANCE POS MODULE (CATEGORY-BASED PAGINATION)
    # --------------------------------------------------------------------------
    def show_pos_view(self):
        self.clear_main_frame()

        title_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(title_frame, text="Point of Sale Terminal", font=ctk.CTkFont(size=24, weight="bold")).pack(
            anchor="w")
        ctk.CTkLabel(title_frame,
                     text="Direct inventory checkout, instant search filtering, category grouping & official receipt generator",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

        pos_grid = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        pos_grid.pack(fill="both", expand=True)
        pos_grid.grid_columnconfigure(0, weight=3)
        pos_grid.grid_columnconfigure(1, weight=2)

        left = ctk.CTkFrame(pos_grid, corner_radius=12)
        left.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        ctk.CTkLabel(left, text="Stock Catalog", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15,
                                                                                                pady=(15, 5))

        self.pos_search = ctk.CTkEntry(left, placeholder_text="🔍 Search stock catalog by category or description...",
                                       height=36)
        self.pos_search.pack(fill="x", padx=15, pady=8)
        self.pos_search.bind("<KeyRelease>", lambda e: self.debounce_search(self.reset_and_load_pos))

        self.pos_catalog_scroll = ctk.CTkScrollableFrame(left, corner_radius=8)
        self.pos_catalog_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        # POS Pagination Control Bar
        self.pos_page_bar = ctk.CTkFrame(left, fg_color="transparent", height=36)
        self.pos_page_bar.pack(fill="x", padx=15, pady=(0, 12))

        right = ctk.CTkFrame(pos_grid, corner_radius=12)
        right.grid(row=0, column=1, padx=(10, 0), sticky="nsew")

        ctk.CTkLabel(right, text="Active Order Cart", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w",
                                                                                                     padx=20,
                                                                                                     pady=(15, 5))

        self.pos_cust = ctk.CTkEntry(right, placeholder_text="Customer / Company Name", height=40)
        self.pos_cust.pack(fill="x", padx=20, pady=10)

        self.pos_cart_scroll = ctk.CTkScrollableFrame(right, corner_radius=8, height=220)
        self.pos_cart_scroll.pack(fill="both", expand=True, padx=20, pady=10)

        self.pos_total_lbl = ctk.CTkLabel(right, text="Total: ₱0.00", font=ctk.CTkFont(size=20, weight="bold"))
        self.pos_total_lbl.pack(anchor="e", padx=20, pady=10)

        btn_checkout = ctk.CTkButton(
            right,
            text="Checkout & Print Official Receipt 🧾",
            fg_color="#2ba84a",
            hover_color="#1e7a35",
            height=44,
            font=ctk.CTkFont(weight="bold"),
            command=self.complete_sale
        )
        btn_checkout.pack(fill="x", padx=20, pady=(0, 20))

        self.load_pos_catalog()
        self.refresh_pos_cart()

    def reset_and_load_pos(self):
        self.pos_page = 1
        self.load_pos_catalog()

    def toggle_pos_category_accordion(self, category_name):
        if category_name in self.pos_expanded_categories:
            self.pos_expanded_categories.remove(category_name)
        else:
            self.pos_expanded_categories.add(category_name)
        self.load_pos_catalog()

    def toggle_pos_column_sort(self, col_key):
        if self.pos_sort_column != col_key:
            self.pos_sort_column = col_key
            self.pos_sort_direction = "ASC"
        elif self.pos_sort_direction == "ASC":
            self.pos_sort_direction = "DESC"
        else:
            self.pos_sort_column = None
            self.pos_sort_direction = None
        self.load_pos_catalog()

    def load_pos_catalog(self):
        for w in self.pos_catalog_scroll.winfo_children():
            w.destroy()

        conn = get_db_connection()
        if not conn:
            return

        query_str = self.pos_search.get().strip() if hasattr(self, 'pos_search') else ""

        order_clause = "ORDER BY particulars ASC, description ASC"
        if self.pos_sort_column and self.pos_sort_direction:
            col_map = {
                "particulars": "particulars",
                "description": "description",
                "unit_cost": "unit_cost",
                "qty": "qty"
            }
            db_col = col_map.get(self.pos_sort_column, "particulars")
            order_clause = f"ORDER BY {db_col} {self.pos_sort_direction}, particulars ASC"

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT * FROM inventory WHERE qty > 0 AND (particulars LIKE %s OR description LIKE %s OR brand LIKE %s) {order_clause}",
            (f"%{query_str}%", f"%{query_str}%", f"%{query_str}%"))
        all_items = cursor.fetchall()
        cursor.close()
        conn.close()

        headers = [
            ("Category", "particulars"),
            ("Description", "description"),
            ("Unit Cost", "unit_cost"),
            ("In Stock", "qty")
        ]

        header_frame = ctk.CTkFrame(self.pos_catalog_scroll, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 5))

        for idx, (label_text, col_key) in enumerate(headers):
            sort_arrow = " ↕"
            if self.pos_sort_column == col_key:
                sort_arrow = " ▲" if self.pos_sort_direction == "ASC" else " ▼"

            btn = ctk.CTkButton(
                header_frame,
                text=f"{label_text}{sort_arrow}",
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="transparent",
                text_color="gray",
                hover_color=("gray85", "gray25"),
                height=22,
                command=lambda k=col_key: self.toggle_pos_column_sort(k)
            )
            btn.pack(side="left", expand=True, fill="x")

        grouped = {}
        for item in all_items:
            part = item["particulars"]
            if part not in grouped:
                grouped[part] = []
            grouped[part].append(item)

        categories_list = list(grouped.keys())
        total_categories = len(categories_list)

        if self.pos_page_size == "All":
            displayed_categories = categories_list
            total_pages = 1
        else:
            p_size = int(self.pos_page_size)
            total_pages = max(1, (total_categories + p_size - 1) // p_size)
            self.pos_page = min(self.pos_page, total_pages)
            start_idx = (self.pos_page - 1) * p_size
            displayed_categories = categories_list[start_idx:start_idx + p_size]

        for part_name in displayed_categories:
            items = grouped[part_name]
            is_expanded = part_name in self.pos_expanded_categories or bool(query_str)

            cat_card = ctk.CTkFrame(self.pos_catalog_scroll, corner_radius=8, fg_color=("gray85", "gray25"))
            cat_card.pack(fill="x", pady=3)

            cat_header = ctk.CTkFrame(cat_card, fg_color="transparent")
            cat_header.pack(fill="x", padx=10, pady=6)

            arrow = "▼" if is_expanded else "►"
            btn_toggle = ctk.CTkButton(
                cat_header,
                text=f"{arrow}  {part_name} ({len(items)} items)",
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color="transparent",
                anchor="w",
                command=lambda p=part_name: self.toggle_pos_category_accordion(p)
            )
            btn_toggle.pack(side="left", fill="x", expand=True)

            if is_expanded:
                body = ctk.CTkFrame(cat_card, fg_color="transparent")
                body.pack(fill="x", padx=10, pady=(0, 6))

                for item in items:
                    row = ctk.CTkFrame(body, fg_color=("gray90", "gray20"), corner_radius=6)
                    row.pack(fill="x", pady=2)

                    brand_str = f"[{item['brand']}] " if item['brand'] else ""
                    ctk.CTkLabel(row, text=f"{brand_str}{item['description']}", font=ctk.CTkFont(weight="bold"),
                                 anchor="w").pack(side="left", padx=10, fill="x", expand=True)
                    ctk.CTkLabel(row, text=f"₱{item['unit_cost']:,.2f}", width=80).pack(side="left", padx=5)
                    ctk.CTkLabel(row, text=f"Stock: {item['qty']}", font=ctk.CTkFont(size=11), text_color="gray",
                                 width=70).pack(side="left", padx=5)

                    ctk.CTkButton(
                        row,
                        text="+ Add",
                        width=55,
                        height=26,
                        fg_color="#1f6aa5",
                        command=lambda i=item: self.add_item_directly_to_cart(i)
                    ).pack(side="right", padx=5, pady=2)

        self.bind_mouse_wheel(self.pos_catalog_scroll)
        self.render_pos_pagination(total_categories, total_pages)

    def render_pos_pagination(self, total_categories, total_pages):
        for w in self.pos_page_bar.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.pos_page_bar, text=f"Total Categories: {total_categories}", font=ctk.CTkFont(size=11),
                     text_color="gray").pack(side="left", padx=5)

        opt = ctk.CTkOptionMenu(
            self.pos_page_bar,
            values=["5", "10", "15", "All"],
            width=70,
            height=26,
            command=self.change_pos_page_size
        )
        opt.set(str(self.pos_page_size))
        opt.pack(side="left", padx=5)

        btn_prev = ctk.CTkButton(
            self.pos_page_bar,
            text="◄ Prev",
            width=65,
            height=26,
            state="normal" if self.pos_page > 1 else "disabled",
            command=self.prev_pos_page
        )
        btn_prev.pack(side="right", padx=2)

        ctk.CTkLabel(self.pos_page_bar, text=f"Page {self.pos_page} of {total_pages}",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="right", padx=8)

        btn_next = ctk.CTkButton(
            self.pos_page_bar,
            text="Next ►",
            width=65,
            height=26,
            state="normal" if self.pos_page < total_pages else "disabled",
            command=self.next_pos_page
        )
        btn_next.pack(side="right", padx=2)

    def change_pos_page_size(self, val):
        self.pos_page_size = val if val == "All" else int(val)
        self.pos_page = 1
        self.load_pos_catalog()

    def prev_pos_page(self):
        if self.pos_page > 1:
            self.pos_page -= 1
            self.load_pos_catalog()

    def next_pos_page(self):
        self.pos_page += 1
        self.load_pos_catalog()

    def add_item_directly_to_cart(self, item):
        current_in_cart = sum(c["qty"] for c in self.cart if c.get("item_id") == item["item_id"])
        if current_in_cart + 1 > item["qty"]:
            messagebox.showerror("Stock Limit", f"Not enough stock! Available: {item['qty']}")
            return

        for c in self.cart:
            if c.get("item_id") == item["item_id"]:
                c["qty"] += 1
                c["subtotal"] = c["qty"] * c["unit_cost"]
                self.refresh_pos_cart()
                return

        self.cart.append({
            "item_id": item["item_id"],
            "particulars": item["particulars"],
            "description": item["description"],
            "qty": 1,
            "unit_cost": float(item["unit_cost"]),
            "subtotal": float(item["unit_cost"])
        })
        self.refresh_pos_cart()

    def refresh_pos_cart(self):
        for w in self.pos_cart_scroll.winfo_children():
            w.destroy()
        total = sum(i["subtotal"] for i in self.cart)

        for idx, item in enumerate(self.cart):
            row = ctk.CTkFrame(self.pos_cart_scroll, fg_color=("gray90", "gray20"), corner_radius=6)
            row.pack(fill="x", pady=2)

            desc_text = f"{item['particulars']} - {item['description']}" if item.get('description') else item[
                'particulars']
            ctk.CTkLabel(row, text=f"{desc_text}", font=ctk.CTkFont(weight="bold"), anchor="w").pack(side="left",
                                                                                                     padx=8, fill="x",
                                                                                                     expand=True)

            btn_minus = ctk.CTkButton(row, text="-", width=22, height=22, fg_color="transparent", border_width=1,
                                      command=lambda i=idx: self.modify_cart_qty(i, -1))
            btn_minus.pack(side="left", padx=2)

            ctk.CTkLabel(row, text=f"{item['qty']}", font=ctk.CTkFont(weight="bold"), width=20).pack(side="left",
                                                                                                     padx=2)

            btn_plus = ctk.CTkButton(row, text="+", width=22, height=22, fg_color="transparent", border_width=1,
                                     command=lambda i=idx: self.modify_cart_qty(i, 1))
            btn_plus.pack(side="left", padx=2)

            ctk.CTkLabel(row, text=f"₱{item['subtotal']:,.2f}", width=80).pack(side="left", padx=8)

            btn_remove = ctk.CTkButton(row, text="❌", width=24, height=22, fg_color="transparent", text_color="#d9534f",
                                       command=lambda i=idx: self.remove_cart_item(i))
            btn_remove.pack(side="right", padx=5)

        self.bind_mouse_wheel(self.pos_cart_scroll)
        self.pos_total_lbl.configure(text=f"Total: ₱{total:,.2f} (VAT Inclusive)")

    def modify_cart_qty(self, idx, delta):
        item = self.cart[idx]
        new_qty = item["qty"] + delta
        if new_qty <= 0:
            self.remove_cart_item(idx)
            return

        if item.get("item_id"):
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT qty FROM inventory WHERE item_id = %s", (item["item_id"],))
                db_item = cursor.fetchone()
                cursor.close()
                conn.close()
                if db_item and new_qty > db_item["qty"]:
                    messagebox.showerror("Stock Limit", f"Max stock available: {db_item['qty']}")
                    return

        item["qty"] = new_qty
        item["subtotal"] = item["qty"] * item["unit_cost"]
        self.refresh_pos_cart()

    def remove_cart_item(self, idx):
        self.cart.pop(idx)
        self.refresh_pos_cart()

    def complete_sale(self):
        cust = self.pos_cust.get().strip()
        if not cust or not self.cart:
            messagebox.showwarning("Warning", "Customer name and cart required.")
            return

        total = sum(i["subtotal"] for i in self.cart)
        vatable_sales = total / 1.12
        vat_amount = total - vatable_sales
        now = datetime.datetime.now()

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sales (customer_name, vatable_sales, vat_amount, total_amount, sale_date) VALUES (%s, %s, %s, %s, %s)",
                (cust, vatable_sales, vat_amount, total, now))
            sale_id = cursor.lastrowid

            for item in self.cart:
                if item.get("item_id"):
                    cursor.execute(
                        "INSERT INTO sale_items (sale_id, item_id, qty_sold, unit_cost, subtotal) VALUES (%s, %s, %s, %s, %s)",
                        (sale_id, item["item_id"], item["qty"], item["unit_cost"], item["subtotal"]))
                    cursor.execute("UPDATE inventory SET qty = qty - %s WHERE item_id = %s",
                                   (item["qty"], item["item_id"]))

            conn.commit()
            cursor.close()
            conn.close()

            file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Document", "*.pdf")],
                                                     initialfile=f"Receipt_{sale_id:06d}.pdf")
            if file_path:
                generate_pdf_receipt(file_path, sale_id, cust, now.strftime('%Y-%m-%d %H:%M'), self.cart, total)
                messagebox.showinfo("Success", f"Receipt saved to {file_path}")

            self.cart = []
            self.show_pos_view()

    # --------------------------------------------------------------------------
    # 4. JOB ESTIMATOR MODULE
    # --------------------------------------------------------------------------
    def show_estimator_view(self):
        self.clear_main_frame()

        title_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(title_frame, text="Job Estimator Terminal", font=ctk.CTkFont(size=24, weight="bold")).pack(
            anchor="w")
        ctk.CTkLabel(title_frame,
                     text="Calculate service quotes, save records, or transfer quotes directly into POS cart",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

        container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        container.pack(fill="both", expand=True)
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)

        left_card = ctk.CTkFrame(container, corner_radius=12)
        left_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        ctk.CTkLabel(left_card, text="Client & Stock Selection", font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=20, pady=(15, 10))

        self.est_cust = ctk.CTkEntry(left_card, placeholder_text="Customer Name", height=38)
        self.est_cust.pack(fill="x", padx=20, pady=6)

        self.est_vehicle = ctk.CTkEntry(left_card, placeholder_text="Vehicle Details (Make/Model/Year)", height=38)
        self.est_vehicle.pack(fill="x", padx=20, pady=6)

        ctk.CTkLabel(left_card, text="Select Needed Inventory Parts", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="gray").pack(anchor="w", padx=20, pady=(12, 4))

        self.est_inv_map = self.fetch_pos_inventory_map()
        options = list(self.est_inv_map.keys()) or ["No Inventory Items"]

        self.est_item_opt = ctk.CTkOptionMenu(left_card, values=options, height=38)
        self.est_item_opt.pack(fill="x", padx=20, pady=6)

        self.est_qty = ctk.CTkEntry(left_card, placeholder_text="Quantity Required", height=38)
        self.est_qty.pack(fill="x", padx=20, pady=6)

        ctk.CTkButton(left_card, text="Add Part to Quote", height=38, command=self.add_part_to_estimate).pack(fill="x",
                                                                                                              padx=20,
                                                                                                              pady=10)

        self.est_parts_list = ctk.CTkScrollableFrame(left_card, corner_radius=8, height=100)
        self.est_parts_list.pack(fill="x", padx=20, pady=5)
        self.bind_mouse_wheel(self.est_parts_list)

        self.est_materials = ctk.CTkEntry(left_card, placeholder_text="Misc Materials Cost (₱)", height=38)
        self.est_materials.pack(fill="x", padx=20, pady=6)

        self.est_labor = ctk.CTkEntry(left_card, placeholder_text="Labor Cost (₱)", height=38)
        self.est_labor.pack(fill="x", padx=20, pady=6)

        ctk.CTkButton(
            left_card,
            text="Save Job Estimate Quote 💾",
            fg_color="#2ba84a",
            hover_color="#1e7a35",
            height=40,
            font=ctk.CTkFont(weight="bold"),
            command=self.save_job_estimate
        ).pack(fill="x", padx=20, pady=(10, 15))

        right_card = ctk.CTkFrame(container, corner_radius=12)
        right_card.grid(row=0, column=1, padx=(10, 0), sticky="nsew")

        ctk.CTkLabel(right_card, text="Saved Quotes & POS Transfer", font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=20, pady=(15, 10))

        self.est_quotes_scroll = ctk.CTkScrollableFrame(right_card, corner_radius=8)
        self.est_quotes_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.bind_mouse_wheel(self.est_quotes_scroll)

        self.load_saved_estimates_table()

    def fetch_pos_inventory_map(self):
        conn = get_db_connection()
        if not conn:
            return {}
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM inventory WHERE qty > 0 LIMIT 100")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return {f"{r['particulars']} - {r['description']} (Stock: {r['qty']} | ₱{r['unit_cost']:,.2f})": r for r in
                rows}

    def add_part_to_estimate(self):
        selected = self.est_item_opt.get()
        qty_str = self.est_qty.get().strip()

        if selected not in self.est_inv_map or not qty_str:
            messagebox.showwarning("Warning", "Select a valid item and quantity.")
            return

        try:
            qty = int(qty_str)
        except ValueError:
            messagebox.showerror("Invalid Qty", "Quantity must be a valid integer.")
            return

        item = self.est_inv_map[selected]
        subtotal = qty * float(item["unit_cost"])

        self.estimate_items.append({
            "item_id": item["item_id"],
            "particulars": item["particulars"],
            "description": item["description"],
            "qty": qty,
            "unit_cost": float(item["unit_cost"]),
            "subtotal": subtotal
        })

        row = ctk.CTkFrame(self.est_parts_list, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=f"{item['particulars']} - {item['description']} (x{qty})").pack(side="left")
        ctk.CTkLabel(row, text=f"₱{subtotal:,.2f}").pack(side="right")

    def save_job_estimate(self):
        cust = self.est_cust.get().strip()
        veh = self.est_vehicle.get().strip()

        try:
            m_cost = float(self.est_materials.get().strip() or 0)
            l_cost = float(self.est_labor.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid Cost", "Materials and Labor costs must be valid numbers.")
            return

        p_cost = sum(i["subtotal"] for i in self.estimate_items)
        total = p_cost + m_cost + l_cost

        if not cust or not veh:
            messagebox.showwarning("Warning", "Customer and Vehicle info required.")
            return

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO job_estimates (customer_name, vehicle_details, parts_cost, materials_cost, labor_cost, total_estimate, estimate_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (cust, veh, p_cost, m_cost, l_cost, total, datetime.datetime.now()))
            conn.commit()
            cursor.close()
            conn.close()

            messagebox.showinfo(
                "Estimate Saved",
                f"Quote Created Successfully!\n\nParts Cost: ₱{p_cost:,.2f}\nMaterials: ₱{m_cost:,.2f}\nLabor: ₱{l_cost:,.2f}\n--------------------\nTotal Estimate: ₱{total:,.2f}"
            )
            self.estimate_items = []
            self.show_estimator_view()

    def load_saved_estimates_table(self):
        for w in self.est_quotes_scroll.winfo_children():
            w.destroy()

        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM job_estimates ORDER BY estimate_id DESC LIMIT 50")
        quotes = cursor.fetchall()
        cursor.close()
        conn.close()

        for q in quotes:
            card = ctk.CTkFrame(self.est_quotes_scroll, corner_radius=8, fg_color=("gray85", "gray25"))
            card.pack(fill="x", pady=4, padx=2)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(6, 2))

            ctk.CTkLabel(top, text=f"Quote #{q['estimate_id']:04d} - {q['customer_name']}",
                         font=ctk.CTkFont(weight="bold")).pack(side="left")
            ctk.CTkLabel(top, text=f"₱{q['total_estimate']:,.2f}", font=ctk.CTkFont(weight="bold"),
                         text_color="#2ba84a").pack(side="right")

            ctk.CTkLabel(card,
                         text=f"Vehicle: {q['vehicle_details']} | Parts: ₱{q['parts_cost']:,.2f} | Labor: ₱{q['labor_cost']:,.2f}",
                         font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", padx=10, pady=(0, 6))

            btn_row = ctk.CTkFrame(card, fg_color="transparent")
            btn_row.pack(fill="x", padx=10, pady=(0, 6))

            ctk.CTkButton(
                btn_row,
                text="Transfer Quote to POS Cart 🛒",
                height=28,
                fg_color="#1f6aa5",
                command=lambda est=q: self.transfer_quote_to_pos(est)
            ).pack(side="left", padx=(0, 5))

            ctk.CTkButton(
                btn_row,
                text="Delete Quote ❌",
                height=28,
                fg_color="#d9534f",
                hover_color="#b52b27",
                command=lambda eid=q['estimate_id']: self.delete_job_estimate(eid)
            ).pack(side="right")

        self.bind_mouse_wheel(self.est_quotes_scroll)

    def transfer_quote_to_pos(self, quote):
        self.cart = []

        service_total = float(quote['labor_cost']) + float(quote['materials_cost'])
        if service_total > 0:
            self.cart.append({
                "item_id": None,
                "particulars": f"Service Labor & Materials ({quote['vehicle_details']})",
                "description": "Job Estimate Charge",
                "qty": 1,
                "unit_cost": service_total,
                "subtotal": service_total
            })

        messagebox.showinfo("POS Transfer",
                            f"Quote #{quote['estimate_id']:04d} transferred to POS Cart!\nSwitching to POS Terminal...")
        self.show_pos_view()
        self.pos_cust.delete(0, 'end')
        self.pos_cust.insert(0, quote['customer_name'])
        self.refresh_pos_cart()

    def delete_job_estimate(self, estimate_id):
        if not messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this job quote?"):
            return
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM job_estimates WHERE estimate_id = %s", (estimate_id,))
            conn.commit()
            cursor.close()
            conn.close()
            self.load_saved_estimates_table()

    # --------------------------------------------------------------------------
    # 5. SALES AUDIT LOG & VISUAL ANALYTICS MODULE
    # --------------------------------------------------------------------------
    def show_sales_view(self):
        self.clear_main_frame()

        title_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(title_frame, text="Sales Audit Log & Revenue Analytics",
                     font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Aligned audit table, daily/monthly tracking, and revenue trends chart",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

        self.render_kpi_cards(self.main_frame)

        split_view = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        split_view.pack(fill="both", expand=True)
        split_view.grid_columnconfigure(0, weight=3)
        split_view.grid_columnconfigure(1, weight=2)

        table_card = ctk.CTkFrame(split_view, corner_radius=12)
        table_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        search_bar = ctk.CTkFrame(table_card, fg_color="transparent")
        search_bar.pack(fill="x", padx=15, pady=12)

        self.sales_search = ctk.CTkEntry(search_bar, placeholder_text="🔍 Search customer name...", height=36)
        self.sales_search.pack(fill="x")
        self.sales_search.bind("<KeyRelease>", lambda e: self.debounce_search(self.load_sales_table))

        self.sales_scroll = ctk.CTkScrollableFrame(table_card, corner_radius=8)
        self.sales_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        graph_card = ctk.CTkFrame(split_view, corner_radius=12)
        graph_card.grid(row=0, column=1, padx=(10, 0), sticky="nsew")

        ctk.CTkLabel(graph_card, text="Revenue Trends (Last 30 Days)", font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=15, pady=(15, 5))

        self.render_revenue_graph(graph_card)
        self.load_sales_table()

    def toggle_sales_column_sort(self, col_key):
        if self.sales_sort_column != col_key:
            self.sales_sort_column = col_key
            self.sales_sort_direction = "ASC"
        elif self.sales_sort_direction == "ASC":
            self.sales_sort_direction = "DESC"
        else:
            self.sales_sort_column = None
            self.sales_sort_direction = None
        self.load_sales_table()

    def load_sales_table(self):
        for w in self.sales_scroll.winfo_children():
            w.destroy()

        conn = get_db_connection()
        if not conn:
            return

        q = self.sales_search.get().strip() if hasattr(self, 'sales_search') else ""
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM sales WHERE customer_name LIKE %s ORDER BY sale_id DESC LIMIT 50", (f"%{q}%",))
        sales = cursor.fetchall()
        cursor.close()
        conn.close()

        header_frame = ctk.CTkFrame(self.sales_scroll, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 8))
        header_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5, 6), weight=1, uniform="sales_col")

        headers = [
            ("Receipt #", "sale_id"),
            ("Customer", "customer_name"),
            ("Date", "sale_date"),
            ("Vatable", "vatable_sales"),
            ("12% VAT", "vat_amount"),
            ("Total", "total_amount"),
            ("Action", None)
        ]

        for idx, (label_text, col_key) in enumerate(headers):
            if col_key:
                sort_arrow = " ↕"
                if self.sales_sort_column == col_key:
                    sort_arrow = " ▲" if self.sales_sort_direction == "ASC" else " ▼"

                btn = ctk.CTkButton(
                    header_frame,
                    text=f"{label_text}{sort_arrow}",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color="transparent",
                    text_color="gray",
                    hover_color=("gray85", "gray25"),
                    height=24,
                    command=lambda k=col_key: self.toggle_sales_column_sort(k)
                )
                btn.grid(row=0, column=idx, sticky="ew")
            else:
                ctk.CTkLabel(header_frame, text=label_text, font=ctk.CTkFont(size=11, weight="bold"),
                             text_color="gray").grid(row=0, column=idx, sticky="ew")

        if self.sales_sort_column and self.sales_sort_direction:
            reverse = (self.sales_sort_direction == "DESC")
            sales.sort(key=lambda x: x[self.sales_sort_column] or "", reverse=reverse)

        for r_idx, s in enumerate(sales, start=1):
            row = ctk.CTkFrame(self.sales_scroll, fg_color=("gray90", "gray20"), corner_radius=6)
            row.pack(fill="x", pady=2)
            row.grid_columnconfigure((0, 1, 2, 3, 4, 5, 6), weight=1, uniform="sales_col")

            ctk.CTkLabel(row, text=f"#{s['sale_id']:06d}", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0,
                                                                                                 sticky="ew", padx=2)
            ctk.CTkLabel(row, text=s['customer_name'][:18], anchor="w").grid(row=0, column=1, sticky="ew", padx=2)
            ctk.CTkLabel(row, text=str(s['sale_date'])[:10], text_color="gray").grid(row=0, column=2, sticky="ew",
                                                                                     padx=2)
            ctk.CTkLabel(row, text=f"₱{s['vatable_sales']:,.2f}").grid(row=0, column=3, sticky="ew", padx=2)
            ctk.CTkLabel(row, text=f"₱{s['vat_amount']:,.2f}").grid(row=0, column=4, sticky="ew", padx=2)
            ctk.CTkLabel(row, text=f"₱{s['total_amount']:,.2f}", font=ctk.CTkFont(weight="bold")).grid(row=0, column=5,
                                                                                                       sticky="ew",
                                                                                                       padx=2)

            ctk.CTkButton(
                row,
                text="Delete",
                fg_color="#d9534f",
                hover_color="#b52b27",
                height=26,
                command=lambda sid=s['sale_id']: self.delete_sale(sid)
            ).grid(row=0, column=6, padx=4, pady=2)

        self.bind_mouse_wheel(self.sales_scroll)

    def render_revenue_graph(self, parent_frame):
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT DATE(sale_date) as day, SUM(total_amount) as total 
            FROM sales 
            WHERE sale_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) 
            GROUP BY DATE(sale_date) 
            ORDER BY day ASC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        days = [r["day"].strftime("%m/%d") for r in rows] or [datetime.datetime.now().strftime("%m/%d")]
        totals = [float(r["total"]) for r in rows] or [0.0]

        fig, ax = plt.subplots(figsize=(4.5, 3.8), dpi=100)
        fig.patch.set_facecolor('#2b2b2b')
        ax.set_facecolor('#1e1e1e')

        ax.bar(days, totals, color='#2ba84a', width=0.5)
        ax.set_ylabel("Revenue (₱)", color='white', fontsize=9)
        ax.tick_params(colors='white', labelsize=8)
        plt.xticks(rotation=45)

        for spine in ax.spines.values():
            spine.set_color('#444444')

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def delete_sale(self, sale_id):
        if not messagebox.askyesno("Confirm", "Delete this sale record and restore inventory stock?"):
            return
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT item_id, qty_sold FROM sale_items WHERE sale_id = %s", (sale_id,))
            items = cursor.fetchall()
            for item in items:
                cursor.execute("UPDATE inventory SET qty = qty + %s WHERE item_id = %s",
                               (item["qty_sold"], item["item_id"]))

            cursor.execute("DELETE FROM sales WHERE sale_id = %s", (sale_id,))
            conn.commit()
            cursor.close()
            conn.close()
            self.show_sales_view()


if __name__ == "__main__":
    init_db()
    app = ModernAutoPartsERP()
    app.mainloop()