import datetime
import customtkinter as ctk
from tkinter import messagebox, filedialog
import mysql.connector
from pdf_generator import PDFGenerator


class EstimatorView(ctk.CTkFrame):
    def __init__(self, master, db_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.db = db_manager
        self.app = app_instance

        self.estimate_items = []
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
        ctk.CTkLabel(title_frame, text="Job Estimator Terminal", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Calculate service quotes, save itemized records, print PDFs, or transfer quotes to POS", font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True)
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)

        left_card = ctk.CTkFrame(container, corner_radius=12)
        left_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        ctk.CTkLabel(left_card, text="Client & Stock Selection", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=20, pady=(15, 5))

        self.est_cust = ctk.CTkEntry(left_card, placeholder_text="Customer Name", height=34)
        self.est_cust.pack(fill="x", padx=20, pady=4)

        self.est_vehicle = ctk.CTkEntry(left_card, placeholder_text="Vehicle Details (Make/Model/Year)", height=34)
        self.est_vehicle.pack(fill="x", padx=20, pady=4)

        ctk.CTkLabel(left_card, text="Search & Add Inventory Parts", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray").pack(anchor="w", padx=20, pady=(8, 2))

        self.est_search = ctk.CTkEntry(left_card, placeholder_text="🔍 Search stock catalog...", height=32)
        self.est_search.pack(fill="x", padx=20, pady=4)
        self.est_search.bind("<KeyRelease>", lambda e: self.debounce_search(self.load_inventory_picker))

        self.est_picker_scroll = ctk.CTkScrollableFrame(left_card, corner_radius=8, height=120)
        self.est_picker_scroll.pack(fill="x", padx=20, pady=4)
        self.bind_mouse_wheel(self.est_picker_scroll)

        ctk.CTkLabel(left_card, text="Selected Quote Items", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray").pack(anchor="w", padx=20, pady=(6, 2))

        self.est_parts_list = ctk.CTkScrollableFrame(left_card, corner_radius=8, height=100)
        self.est_parts_list.pack(fill="x", padx=20, pady=4)
        self.bind_mouse_wheel(self.est_parts_list)

        row_meta = ctk.CTkFrame(left_card, fg_color="transparent")
        row_meta.pack(fill="x", padx=20, pady=4)
        row_meta.grid_columnconfigure((0, 1), weight=1)

        self.est_materials = ctk.CTkEntry(row_meta, placeholder_text="Materials Cost (₱)", height=34)
        self.est_materials.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.est_labor = ctk.CTkEntry(row_meta, placeholder_text="Labor Cost (₱)", height=34)
        self.est_labor.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        ctk.CTkButton(left_card, text="Save Job Estimate Quote 💾", fg_color="#2ba84a", hover_color="#1e7a35", height=38, font=ctk.CTkFont(weight="bold"), command=self.save_job_estimate).pack(fill="x", padx=20, pady=(8, 12))

        right_card = ctk.CTkFrame(container, corner_radius=12)
        right_card.grid(row=0, column=1, padx=(10, 0), sticky="nsew")

        ctk.CTkLabel(right_card, text="Saved Quotes & Actions", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=20, pady=(15, 10))

        self.est_quotes_scroll = ctk.CTkScrollableFrame(right_card, corner_radius=8)
        self.est_quotes_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.bind_mouse_wheel(self.est_quotes_scroll)

        self.load_inventory_picker()
        self.load_saved_estimates_table()

    def load_inventory_picker(self):
        for w in self.est_picker_scroll.winfo_children():
            w.destroy()

        conn = self.db.get_connection()
        if not conn:
            return

        query_str = self.est_search.get().strip() if hasattr(self, 'est_search') else ""
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM inventory WHERE qty > 0 AND (particulars LIKE %s OR description LIKE %s OR brand LIKE %s) ORDER BY particulars ASC LIMIT 25",
            (f"%{query_str}%", f"%{query_str}%", f"%{query_str}%")
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if not rows:
            ctk.CTkLabel(self.est_picker_scroll, text="No items found.", text_color="gray").pack(pady=5)
            return

        for item in rows:
            row = ctk.CTkFrame(self.est_picker_scroll, fg_color=("gray90", "gray20"), corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)

            brand_str = f"[{item['brand']}] " if item['brand'] else ""
            ctk.CTkLabel(row, text=f"{brand_str}{item['particulars']} - {item['description']}", font=ctk.CTkFont(size=11, weight="bold"), anchor="w").pack(side="left", padx=8, fill="x", expand=True)
            ctk.CTkLabel(row, text=f"₱{item['unit_cost']:,.2f}", font=ctk.CTkFont(size=11), width=65).pack(side="left", padx=2)

            qty_entry = ctk.CTkEntry(row, width=40, height=24, placeholder_text="1")
            qty_entry.pack(side="left", padx=4)

            ctk.CTkButton(row, text="+ Add", width=45, height=24, fg_color="#1f6aa5", command=lambda i=item, q_ent=qty_entry: self.add_part_to_quote(i, q_ent.get().strip())).pack(side="right", padx=4)

    def add_part_to_quote(self, item, qty_str):
        try:
            qty = int(qty_str) if qty_str else 1
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Qty", "Quantity must be a positive integer.")
            return

        subtotal = qty * float(item["unit_cost"])
        self.estimate_items.append({
            "item_id": item["item_id"],
            "particulars": item["particulars"],
            "description": item["description"],
            "qty": qty,
            "unit_cost": float(item["unit_cost"]),
            "subtotal": subtotal
        })
        self.refresh_parts_list()

    def refresh_parts_list(self):
        for w in self.est_parts_list.winfo_children():
            w.destroy()

        for idx, item in enumerate(self.estimate_items):
            row = ctk.CTkFrame(self.est_parts_list, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"{item['particulars']} - {item['description']} (x{item['qty']})", font=ctk.CTkFont(size=11)).pack(side="left")
            ctk.CTkButton(row, text="❌", width=20, height=20, fg_color="transparent", text_color="#d9534f", command=lambda i=idx: self.remove_part_from_quote(i)).pack(side="right", padx=2)
            ctk.CTkLabel(row, text=f"₱{item['subtotal']:,.2f}", font=ctk.CTkFont(size=11, weight="bold")).pack(side="right", padx=5)

    def remove_part_from_quote(self, idx):
        self.estimate_items.pop(idx)
        self.refresh_parts_list()

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

        conn = self.db.get_connection()
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
            self.refresh_parts_list()
            self.load_saved_estimates_table()

    def load_saved_estimates_table(self):
        for w in self.est_quotes_scroll.winfo_children():
            w.destroy()

        conn = self.db.get_connection()
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

            ctk.CTkLabel(top, text=f"Quote #{q['estimate_id']:04d} - {q['customer_name']}", font=ctk.CTkFont(weight="bold")).pack(side="left")
            ctk.CTkLabel(top, text=f"₱{q['total_estimate']:,.2f}", font=ctk.CTkFont(weight="bold"), text_color="#2ba84a").pack(side="right")

            ctk.CTkLabel(card, text=f"Vehicle: {q['vehicle_details']} | Parts: ₱{q['parts_cost']:,.2f} | Labor: ₱{q['labor_cost']:,.2f}", font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", padx=10, pady=(0, 6))

            btn_row = ctk.CTkFrame(card, fg_color="transparent")
            btn_row.pack(fill="x", padx=10, pady=(0, 6))

            ctk.CTkButton(btn_row, text="Transfer to POS 🛒", height=26, fg_color="#1f6aa5", command=lambda est=q: self.transfer_quote_to_pos(est)).pack(side="left", padx=(0, 4))
            ctk.CTkButton(btn_row, text="Print PDF 📄", height=26, fg_color="#6b3e75", command=lambda est=q: self.print_quote_pdf(est)).pack(side="left", padx=(0, 4))
            ctk.CTkButton(btn_row, text="Delete ❌", height=26, fg_color="#d9534f", hover_color="#b52b27", command=lambda eid=q['estimate_id']: self.delete_job_estimate(eid)).pack(side="right")

        self.bind_mouse_wheel(self.est_quotes_scroll)

    def print_quote_pdf(self, quote):
        file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Document", "*.pdf")], initialfile=f"Quote_EST-{quote['estimate_id']:04d}.pdf")
        if not file_path:
            return

        date_str = str(quote['estimate_date'])[:16]
        PDFGenerator.generate_job_quote(
            file_path,
            quote['estimate_id'],
            quote['customer_name'],
            quote['vehicle_details'],
            date_str,
            self.estimate_items,
            float(quote['materials_cost']),
            float(quote['labor_cost']),
            float(quote['total_estimate'])
        )
        messagebox.showinfo("Success", f"PDF Quote saved to {file_path}")

    def transfer_quote_to_pos(self, quote):
        self.app.cart = []

        # 1. Add physical inventory parts directly to POS Cart
        for item in self.estimate_items:
            self.app.cart.append({
                "item_id": item["item_id"],
                "particulars": item["particulars"],
                "description": item["description"],
                "qty": item["qty"],
                "unit_cost": float(item["unit_cost"]),
                "subtotal": float(item["subtotal"])
            })

        # 2. Add Miscellaneous Materials service item if cost > 0
        mat_cost = float(quote['materials_cost'])
        if mat_cost > 0:
            self.app.cart.append({
                "item_id": None,
                "particulars": "Misc. Job Materials",
                "description": f"Materials for {quote['vehicle_details']}",
                "qty": 1,
                "unit_cost": mat_cost,
                "subtotal": mat_cost
            })

        # 3. Add Service Labor item if cost > 0
        labor_cost = float(quote['labor_cost'])
        if labor_cost > 0:
            self.app.cart.append({
                "item_id": None,
                "particulars": "Service Labor",
                "description": f"Labor Charge ({quote['vehicle_details']})",
                "qty": 1,
                "unit_cost": labor_cost,
                "subtotal": labor_cost
            })

        messagebox.showinfo("POS Transfer", f"Quote #{quote['estimate_id']:04d} items transferred to POS Cart!\nSwitching to POS Terminal...")
        self.app.show_pos_view()
        self.app.current_view.pos_cust.delete(0, 'end')
        self.app.current_view.pos_cust.insert(0, quote['customer_name'])
        self.app.current_view.refresh_pos_cart()

    def delete_job_estimate(self, estimate_id):
        if not messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this job quote?"):
            return
        conn = self.db.get_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM job_estimates WHERE estimate_id = %s", (estimate_id,))
            conn.commit()
            cursor.close()
            conn.close()
            self.load_saved_estimates_table()