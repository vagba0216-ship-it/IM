import datetime
import customtkinter as ctk
from tkinter import messagebox
import mysql.connector

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class SalesView(ctk.CTkFrame):
    def __init__(self, master, db_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.db = db_manager
        self.app = app_instance

        self.sales_sort_column = None
        self.sales_sort_direction = None
        self.search_timer = None

        self.build_ui()

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

    def build_ui(self):
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(title_frame, text="Sales Audit Log & Revenue Analytics",
                     font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Click any row to inspect itemized parts, labor, and costs per invoice",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

        self.app.render_kpi_cards(self)

        split_view = ctk.CTkFrame(self, fg_color="transparent")
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

        conn = self.db.get_connection()
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
            ("Receipt #", "sale_id"), ("Customer", "customer_name"), ("Date", "sale_date"),
            ("Vatable", "vatable_sales"), ("12% VAT", "vat_amount"), ("Total", "total_amount"), ("Action", None)
        ]

        for idx, (label_text, col_key) in enumerate(headers):
            if col_key:
                sort_arrow = " ↕"
                if self.sales_sort_column == col_key:
                    sort_arrow = " ▲" if self.sales_sort_direction == "ASC" else " ▼"
                btn = ctk.CTkButton(header_frame, text=f"{label_text}{sort_arrow}",
                                    font=ctk.CTkFont(size=11, weight="bold"), fg_color="transparent", text_color="gray",
                                    hover_color=("gray85", "gray25"), height=24,
                                    command=lambda k=col_key: self.toggle_sales_column_sort(k))
                btn.grid(row=0, column=idx, sticky="ew")
            else:
                ctk.CTkLabel(header_frame, text=label_text, font=ctk.CTkFont(size=11, weight="bold"),
                             text_color="gray").grid(row=0, column=idx, sticky="ew")

        if self.sales_sort_column and self.sales_sort_direction:
            reverse = (self.sales_sort_direction == "DESC")
            sales.sort(key=lambda x: x[self.sales_sort_column] or "", reverse=reverse)

        for s in sales:
            row = ctk.CTkFrame(self.sales_scroll, fg_color=("gray90", "gray20"), corner_radius=6)
            row.pack(fill="x", pady=2)
            row.grid_columnconfigure((0, 1, 2, 3, 4, 5, 6), weight=1, uniform="sales_col")

            click_cmd = lambda e, sale=s: self.open_sale_details_modal(sale)

            lbl_id = ctk.CTkLabel(row, text=f"#{s['sale_id']:06d}", font=ctk.CTkFont(weight="bold"))
            lbl_id.grid(row=0, column=0, sticky="ew", padx=2)
            lbl_id.bind("<Button-1>", click_cmd)

            lbl_cust = ctk.CTkLabel(row, text=s['customer_name'][:18], anchor="w")
            lbl_cust.grid(row=0, column=1, sticky="ew", padx=2)
            lbl_cust.bind("<Button-1>", click_cmd)

            lbl_date = ctk.CTkLabel(row, text=str(s['sale_date'])[:10], text_color="gray")
            lbl_date.grid(row=0, column=2, sticky="ew", padx=2)
            lbl_date.bind("<Button-1>", click_cmd)

            lbl_vatable = ctk.CTkLabel(row, text=f"₱{s['vatable_sales']:,.2f}")
            lbl_vatable.grid(row=0, column=3, sticky="ew", padx=2)
            lbl_vatable.bind("<Button-1>", click_cmd)

            lbl_vat = ctk.CTkLabel(row, text=f"₱{s['vat_amount']:,.2f}")
            lbl_vat.grid(row=0, column=4, sticky="ew", padx=2)
            lbl_vat.bind("<Button-1>", click_cmd)

            lbl_total = ctk.CTkLabel(row, text=f"₱{s['total_amount']:,.2f}", font=ctk.CTkFont(weight="bold"))
            lbl_total.grid(row=0, column=5, sticky="ew", padx=2)
            lbl_total.bind("<Button-1>", click_cmd)

            ctk.CTkButton(row, text="Delete", fg_color="#d9534f", hover_color="#b52b27", height=26,
                          command=lambda sid=s['sale_id']: self.delete_sale(sid)).grid(row=0, column=6, padx=4, pady=2)

        self.bind_mouse_wheel(self.sales_scroll)

    def open_sale_details_modal(self, sale):
        modal = ctk.CTkToplevel(self)
        modal.title(f"Invoice #{sale['sale_id']:06d} Breakdown")
        modal.geometry("640x500")
        modal.grab_set()

        ctk.CTkLabel(modal, text=f"Official Receipt #{sale['sale_id']:06d}",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(padx=20, pady=(15, 2))
        ctk.CTkLabel(modal, text=f"Customer: {sale['customer_name']} | Date: {sale['sale_date']}",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(padx=20, pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(modal, corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        conn = self.db.get_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT si.*, 
                       COALESCE(i.particulars, 'Service / Job Charge') AS particulars, 
                       COALESCE(i.description, 'Standard Charge') AS description
                FROM sale_items si
                LEFT JOIN inventory i ON si.item_id = i.item_id
                WHERE si.sale_id = %s
            """, (sale['sale_id'],))
            items = cursor.fetchall()
            cursor.close()
            conn.close()

            header = ctk.CTkFrame(scroll, fg_color="transparent")
            header.pack(fill="x", pady=2)
            ctk.CTkLabel(header, text="Item / Particulars", font=ctk.CTkFont(weight="bold"), anchor="w").pack(
                side="left", padx=5, fill="x", expand=True)
            ctk.CTkLabel(header, text="Qty", font=ctk.CTkFont(weight="bold"), width=40).pack(side="left", padx=5)
            ctk.CTkLabel(header, text="Unit Cost", font=ctk.CTkFont(weight="bold"), width=85).pack(side="left", padx=5)
            ctk.CTkLabel(header, text="Subtotal", font=ctk.CTkFont(weight="bold"), width=95).pack(side="right", padx=5)

            for item in items:
                row = ctk.CTkFrame(scroll, fg_color=("gray90", "gray20"), corner_radius=6)
                row.pack(fill="x", pady=2)

                desc = f"{item['particulars']} - {item['description']}" if item['description'] else item['particulars']
                ctk.CTkLabel(row, text=desc, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left",
                                                                                                        padx=5,
                                                                                                        fill="x",
                                                                                                        expand=True)
                ctk.CTkLabel(row, text=str(item['qty_sold']), width=40).pack(side="left", padx=5)
                ctk.CTkLabel(row, text=f"₱{item['unit_cost']:,.2f}", width=85).pack(side="left", padx=5)
                ctk.CTkLabel(row, text=f"₱{item['subtotal']:,.2f}", font=ctk.CTkFont(size=11, weight="bold"),
                             width=95).pack(side="right", padx=5)

        footer = ctk.CTkFrame(modal, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(footer, text=f"Vatable: ₱{sale['vatable_sales']:,.2f}  |  VAT (12%): ₱{sale['vat_amount']:,.2f}",
                     font=ctk.CTkFont(size=11), text_color="gray").pack(side="left")
        ctk.CTkLabel(footer, text=f"Total: ₱{sale['total_amount']:,.2f}", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#2ba84a").pack(side="right")

    def render_revenue_graph(self, parent_frame):
        conn = self.db.get_connection()
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
        conn = self.db.get_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT item_id, qty_sold FROM sale_items WHERE sale_id = %s", (sale_id,))
            items = cursor.fetchall()
            for item in items:
                if item["item_id"] is not None:
                    cursor.execute("UPDATE inventory SET qty = qty + %s WHERE item_id = %s",
                                   (item["qty_sold"], item["item_id"]))

            cursor.execute("DELETE FROM sales WHERE sale_id = %s", (sale_id,))
            conn.commit()
            cursor.close()
            conn.close()
            self.app.show_sales_view()