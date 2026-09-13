import datetime
import customtkinter as ctk
from tkinter import messagebox, filedialog
import mysql.connector
from pdf_generator import PDFGenerator


class POSView(ctk.CTkFrame):
    def __init__(self, master, db_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.db = db_manager
        self.app = app_instance

        self.pos_page = 1
        self.pos_page_size = 5
        self.pos_sort_column = None
        self.pos_sort_direction = None
        self.pos_expanded_categories = set()
        self.search_timer = None

        self.build_ui()
        self.load_pos_catalog()
        self.refresh_pos_cart()

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
        ctk.CTkLabel(title_frame, text="Point of Sale Terminal", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Direct inventory checkout, instant search filtering, category grouping & official receipt generator", font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

        pos_grid = ctk.CTkFrame(self, fg_color="transparent")
        pos_grid.pack(fill="both", expand=True)
        pos_grid.grid_columnconfigure(0, weight=3)
        pos_grid.grid_columnconfigure(1, weight=2)

        left = ctk.CTkFrame(pos_grid, corner_radius=12)
        left.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        ctk.CTkLabel(left, text="Stock Catalog", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))

        self.pos_search = ctk.CTkEntry(left, placeholder_text="🔍 Search stock catalog by category or description...", height=36)
        self.pos_search.pack(fill="x", padx=15, pady=8)
        self.pos_search.bind("<KeyRelease>", lambda e: self.debounce_search(self.reset_and_load_pos))

        self.pos_catalog_scroll = ctk.CTkScrollableFrame(left, corner_radius=8)
        self.pos_catalog_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        self.pos_page_bar = ctk.CTkFrame(left, fg_color="transparent", height=36)
        self.pos_page_bar.pack(fill="x", padx=15, pady=(0, 12))

        right = ctk.CTkFrame(pos_grid, corner_radius=12)
        right.grid(row=0, column=1, padx=(10, 0), sticky="nsew")

        ctk.CTkLabel(right, text="Active Order Cart", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=20, pady=(15, 5))

        self.pos_cust = ctk.CTkEntry(right, placeholder_text="Customer / Company Name", height=40)
        self.pos_cust.pack(fill="x", padx=20, pady=10)

        self.pos_cart_scroll = ctk.CTkScrollableFrame(right, corner_radius=8, height=220)
        self.pos_cart_scroll.pack(fill="both", expand=True, padx=20, pady=10)

        self.pos_total_lbl = ctk.CTkLabel(right, text="Total: ₱0.00", font=ctk.CTkFont(size=20, weight="bold"))
        self.pos_total_lbl.pack(anchor="e", padx=20, pady=10)

        btn_checkout = ctk.CTkButton(right, text="Checkout & Print Official Receipt 🧾", fg_color="#2ba84a", hover_color="#1e7a35", height=44, font=ctk.CTkFont(weight="bold"), command=self.complete_sale)
        btn_checkout.pack(fill="x", padx=20, pady=(0, 20))

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

        conn = self.db.get_connection()
        if not conn:
            return

        query_str = self.pos_search.get().strip() if hasattr(self, 'pos_search') else ""
        order_clause = "ORDER BY particulars ASC, description ASC"
        if self.pos_sort_column and self.pos_sort_direction:
            col_map = {"particulars": "particulars", "description": "description", "unit_cost": "unit_cost", "qty": "qty"}
            db_col = col_map.get(self.pos_sort_column, "particulars")
            order_clause = f"ORDER BY {db_col} {self.pos_sort_direction}, particulars ASC"

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT * FROM inventory WHERE qty > 0 AND (particulars LIKE %s OR description LIKE %s OR brand LIKE %s) {order_clause}",
            (f"%{query_str}%", f"%{query_str}%", f"%{query_str}%")
        )
        all_items = cursor.fetchall()
        cursor.close()
        conn.close()

        headers = [("Category", "particulars"), ("Description", "description"), ("Unit Cost", "unit_cost"), ("In Stock", "qty")]
        header_frame = ctk.CTkFrame(self.pos_catalog_scroll, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 5))

        for label_text, col_key in headers:
            sort_arrow = " ↕"
            if self.pos_sort_column == col_key:
                sort_arrow = " ▲" if self.pos_sort_direction == "ASC" else " ▼"
            btn = ctk.CTkButton(header_frame, text=f"{label_text}{sort_arrow}", font=ctk.CTkFont(size=11, weight="bold"), fg_color="transparent", text_color="gray", hover_color=("gray85", "gray25"), height=22, command=lambda k=col_key: self.toggle_pos_column_sort(k))
            btn.pack(side="left", expand=True, fill="x")

        grouped = {}
        for item in all_items:
            part = item["particulars"]
            grouped.setdefault(part, []).append(item)

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
            btn_toggle = ctk.CTkButton(cat_header, text=f"{arrow}  {part_name} ({len(items)} items)", font=ctk.CTkFont(size=13, weight="bold"), fg_color="transparent", anchor="w", command=lambda p=part_name: self.toggle_pos_category_accordion(p))
            btn_toggle.pack(side="left", fill="x", expand=True)

            if is_expanded:
                body = ctk.CTkFrame(cat_card, fg_color="transparent")
                body.pack(fill="x", padx=10, pady=(0, 6))

                for item in items:
                    row = ctk.CTkFrame(body, fg_color=("gray90", "gray20"), corner_radius=6)
                    row.pack(fill="x", pady=2)

                    brand_str = f"[{item['brand']}] " if item['brand'] else ""
                    ctk.CTkLabel(row, text=f"{brand_str}{item['description']}", font=ctk.CTkFont(weight="bold"), anchor="w").pack(side="left", padx=10, fill="x", expand=True)
                    ctk.CTkLabel(row, text=f"₱{item['unit_cost']:,.2f}", width=80).pack(side="left", padx=5)
                    ctk.CTkLabel(row, text=f"Stock: {item['qty']}", font=ctk.CTkFont(size=11), text_color="gray", width=70).pack(side="left", padx=5)
                    ctk.CTkButton(row, text="+ Add", width=55, height=26, fg_color="#1f6aa5", command=lambda i=item: self.add_item_directly_to_cart(i)).pack(side="right", padx=5, pady=2)

        self.bind_mouse_wheel(self.pos_catalog_scroll)
        self.render_pos_pagination(total_categories, total_pages)

    def render_pos_pagination(self, total_categories, total_pages):
        for w in self.pos_page_bar.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.pos_page_bar, text=f"Total Categories: {total_categories}", font=ctk.CTkFont(size=11), text_color="gray").pack(side="left", padx=5)

        opt = ctk.CTkOptionMenu(self.pos_page_bar, values=["5", "10", "15", "All"], width=70, height=26, command=self.change_pos_page_size)
        opt.set(str(self.pos_page_size))
        opt.pack(side="left", padx=5)

        btn_prev = ctk.CTkButton(self.pos_page_bar, text="◄ Prev", width=65, height=26, state="normal" if self.pos_page > 1 else "disabled", command=self.prev_pos_page)
        btn_prev.pack(side="right", padx=2)

        ctk.CTkLabel(self.pos_page_bar, text=f"Page {self.pos_page} of {total_pages}", font=ctk.CTkFont(size=12, weight="bold")).pack(side="right", padx=8)

        btn_next = ctk.CTkButton(self.pos_page_bar, text="Next ►", width=65, height=26, state="normal" if self.pos_page < total_pages else "disabled", command=self.next_pos_page)
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
        current_in_cart = sum(c["qty"] for c in self.app.cart if c.get("item_id") == item["item_id"])
        if current_in_cart + 1 > item["qty"]:
            messagebox.showerror("Stock Limit", f"Not enough stock! Available: {item['qty']}")
            return

        for c in self.app.cart:
            if c.get("item_id") == item["item_id"]:
                c["qty"] += 1
                c["subtotal"] = c["qty"] * c["unit_cost"]
                self.refresh_pos_cart()
                return

        self.app.cart.append({
            "item_id": item["item_id"], "particulars": item["particulars"], "description": item["description"],
            "qty": 1, "unit_cost": float(item["unit_cost"]), "subtotal": float(item["unit_cost"])
        })
        self.refresh_pos_cart()

    def refresh_pos_cart(self):
        for w in self.pos_cart_scroll.winfo_children():
            w.destroy()
        total = sum(i["subtotal"] for i in self.app.cart)

        for idx, item in enumerate(self.app.cart):
            row = ctk.CTkFrame(self.pos_cart_scroll, fg_color=("gray90", "gray20"), corner_radius=6)
            row.pack(fill="x", pady=2)

            desc_text = f"{item['particulars']} - {item['description']}" if item.get('description') else item['particulars']
            ctk.CTkLabel(row, text=f"{desc_text}", font=ctk.CTkFont(weight="bold"), anchor="w").pack(side="left", padx=8, fill="x", expand=True)

            btn_minus = ctk.CTkButton(row, text="-", width=22, height=22, fg_color="transparent", border_width=1, command=lambda i=idx: self.modify_cart_qty(i, -1))
            btn_minus.pack(side="left", padx=2)

            ctk.CTkLabel(row, text=f"{item['qty']}", font=ctk.CTkFont(weight="bold"), width=20).pack(side="left", padx=2)

            btn_plus = ctk.CTkButton(row, text="+", width=22, height=22, fg_color="transparent", border_width=1, command=lambda i=idx: self.modify_cart_qty(i, 1))
            btn_plus.pack(side="left", padx=2)

            ctk.CTkLabel(row, text=f"₱{item['subtotal']:,.2f}", width=80).pack(side="left", padx=8)

            btn_remove = ctk.CTkButton(row, text="❌", width=24, height=22, fg_color="transparent", text_color="#d9534f", command=lambda i=idx: self.remove_cart_item(i))
            btn_remove.pack(side="right", padx=5)

        self.bind_mouse_wheel(self.pos_cart_scroll)
        self.pos_total_lbl.configure(text=f"Total: ₱{total:,.2f} (VAT Inclusive)")

    def modify_cart_qty(self, idx, delta):
        item = self.app.cart[idx]
        new_qty = item["qty"] + delta
        if new_qty <= 0:
            self.remove_cart_item(idx)
            return

        if item.get("item_id"):
            conn = self.db.get_connection()
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
        self.app.cart.pop(idx)
        self.refresh_pos_cart()

    def complete_sale(self):
        cust = self.pos_cust.get().strip()
        if not cust or not self.app.cart:
            messagebox.showwarning("Warning", "Customer name and cart required.")
            return

        total = sum(i["subtotal"] for i in self.app.cart)
        vatable_sales = total / 1.12
        vat_amount = total - vatable_sales
        now = datetime.datetime.now()

        conn = self.db.get_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sales (customer_name, vatable_sales, vat_amount, total_amount, sale_date) VALUES (%s, %s, %s, %s, %s)",
                (cust, vatable_sales, vat_amount, total, now)
            )
            sale_id = cursor.lastrowid

            for item in self.app.cart:
                item_id_val = item.get("item_id")
                cursor.execute(
                    "INSERT INTO sale_items (sale_id, item_id, qty_sold, unit_cost, subtotal) VALUES (%s, %s, %s, %s, %s)",
                    (sale_id, item_id_val, item["qty"], item["unit_cost"], item["subtotal"])
                )
                if item_id_val is not None:
                    cursor.execute("UPDATE inventory SET qty = qty - %s WHERE item_id = %s", (item["qty"], item_id_val))

            conn.commit()
            cursor.close()
            conn.close()

            file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Document", "*.pdf")], initialfile=f"Receipt_{sale_id:06d}.pdf")
            if file_path:
                PDFGenerator.generate_receipt(file_path, sale_id, cust, now.strftime('%Y-%m-%d %H:%M'), self.app.cart, total)
                messagebox.showinfo("Success", f"Receipt saved to {file_path}")

            self.app.cart = []
            self.app.show_pos_view()