import os
import csv
import threading
import queue
import customtkinter as ctk
from tkinter import messagebox, filedialog
from PIL import Image
import mysql.connector


class InventoryView(ctk.CTkFrame):
    def __init__(self, master, db_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.db = db_manager
        self.app = app_instance

        self.selected_item_id = None
        self.current_image_path = None
        self.search_timer = None
        self.import_queue = queue.Queue()

        self.inv_page = 1
        self.inv_page_size = 5
        self.sort_column = None
        self.sort_direction = None
        self.expanded_categories = set()

        self.build_ui()
        self.load_inventory_table()

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

    def debounce_search(self, callback_func, delay=250):
        if self.search_timer is not None:
            self.after_cancel(self.search_timer)
        self.search_timer = self.after(delay, callback_func)

    def build_ui(self):
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 10))

        status_text = " (Filtering Low Stock <= 5)" if self.app.filter_low_stock else ""
        ctk.CTkLabel(title_frame, text=f"Inventory Dashboard{status_text}", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Hierarchical stock view, pre-set values, and bulk CSV export/import", font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

        self.app.render_kpi_cards(self)

        content_split = ctk.CTkFrame(self, fg_color="transparent")
        content_split.pack(fill="both", expand=True)
        content_split.grid_columnconfigure(0, weight=3)
        content_split.grid_columnconfigure(1, weight=2)

        left_card = ctk.CTkFrame(content_split, corner_radius=12)
        left_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        ctrl_bar = ctk.CTkFrame(left_card, fg_color="transparent")
        ctrl_bar.pack(fill="x", padx=15, pady=12)

        self.inv_search = ctk.CTkEntry(ctrl_bar, placeholder_text="🔍 Search category, brand, or description...", height=36)
        self.inv_search.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.inv_search.bind("<KeyRelease>", lambda e: self.debounce_search(self.reset_and_load_inventory))

        if self.app.filter_low_stock:
            btn_clear_filter = ctk.CTkButton(ctrl_bar, text="Clear Filter ❌", height=36, fg_color="#d9534f", command=self.app.trigger_low_stock_filter)
            btn_clear_filter.pack(side="right", padx=(5, 0))

        btn_export = ctk.CTkButton(ctrl_bar, text="Export CSV 📄", height=36, fg_color="#2ba84a", command=self.export_csv_dialog)
        btn_export.pack(side="right", padx=(5, 0))

        btn_import = ctk.CTkButton(ctrl_bar, text="Import CSV 📁", height=36, fg_color="#1f6aa5", command=self.import_csv_dialog)
        btn_import.pack(side="right")

        self.stock_scroll = ctk.CTkScrollableFrame(left_card, corner_radius=8)
        self.stock_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        self.inv_page_bar = ctk.CTkFrame(left_card, fg_color="transparent", height=36)
        self.inv_page_bar.pack(fill="x", padx=15, pady=(0, 12))

        form_card = ctk.CTkFrame(content_split, corner_radius=12)
        form_card.grid(row=0, column=1, padx=(10, 0), sticky="nsew")

        ctk.CTkLabel(form_card, text="Stock Item Details", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=20, pady=(15, 2))
        ctk.CTkLabel(form_card, text="Use dropdown presets or type custom values", font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", padx=20, pady=(0, 10))

        self.image_preview_label = ctk.CTkLabel(form_card, text="No Image Attached", width=120, height=75, fg_color=("gray85", "gray25"), corner_radius=8)
        self.image_preview_label.pack(pady=4)

        btn_img = ctk.CTkButton(form_card, text="Attach Image 📷", height=26, fg_color="transparent", text_color=("gray10", "gray90"), border_width=1, command=self.select_image_file)
        btn_img.pack(pady=(0, 8))

        particulars_presets = self.fetch_presets('particulars') or ["Oil filter", "Fuel filter", "Brake pad"]
        self.inv_particulars_opt = ctk.CTkOptionMenu(form_card, values=particulars_presets, height=34, command=lambda v: self.set_input(self.inv_particulars, v))
        self.inv_particulars_opt.pack(fill="x", padx=20, pady=4)

        self.inv_particulars = ctk.CTkEntry(form_card, placeholder_text="Particulars / Category", height=34)
        self.inv_particulars.pack(fill="x", padx=20, pady=4)

        brand_presets = self.fetch_presets('brand') or ["Vic", "Baldwin", "Bosch"]
        self.inv_brand_opt = ctk.CTkOptionMenu(form_card, values=brand_presets, height=34, command=lambda v: self.set_input(self.inv_brand, v))
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

        ctk.CTkButton(btn_bar, text="Save / Update Item", fg_color="#2ba84a", hover_color="#1e7a35", height=38, font=ctk.CTkFont(weight="bold"), command=self.save_inventory_item).pack(fill="x", pady=4)
        ctk.CTkButton(btn_bar, text="Delete Selected", fg_color="#d9534f", hover_color="#b52b27", height=34, command=self.delete_inventory_item).pack(fill="x", pady=4)
        ctk.CTkButton(btn_bar, text="Clear Form", fg_color="transparent", text_color="gray", command=self.reset_inventory_form).pack(fill="x", pady=2)

    def set_input(self, widget, val):
        widget.delete(0, 'end')
        widget.insert(0, val)

    def reset_and_load_inventory(self):
        self.inv_page = 1
        self.load_inventory_table()

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
        for w in [self.inv_particulars, self.inv_brand, self.inv_qty, self.inv_desc, self.inv_cost]:
            w.delete(0, 'end')
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

        conn = self.db.get_connection()
        if conn:
            cursor = conn.cursor()
            if self.selected_item_id:
                cursor.execute("""
                    UPDATE inventory SET particulars=%s, brand=%s, description=%s, unit=%s, qty=%s, unit_cost=%s, image_path=%s WHERE item_id=%s
                """, (particulars, self.inv_brand.get().strip(), desc, unit, clean_qty, clean_cost, self.current_image_path, self.selected_item_id))
            else:
                cursor.execute("""
                    INSERT INTO inventory (particulars, brand, description, unit, qty, unit_cost, image_path) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (particulars, self.inv_brand.get().strip(), desc, unit, clean_qty, clean_cost, self.current_image_path))
            conn.commit()
            cursor.close()
            conn.close()
            self.reset_inventory_form()
            self.app.show_inventory_view()

    def delete_inventory_item(self):
        if not self.selected_item_id:
            messagebox.showwarning("Select Item", "Please select an item from the table to delete.")
            return
        conn = self.db.get_connection()
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
            self.app.show_inventory_view()

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

        conn = self.db.get_connection()
        if not conn:
            err_lbl = ctk.CTkLabel(self.stock_scroll, text="❌ Unable to connect to Database Pool.", text_color="#d9534f")
            err_lbl.pack(pady=20)
            return

        cursor = conn.cursor(dictionary=True)
        query_str = self.inv_search.get().strip() if hasattr(self, 'inv_search') else ""

        order_clause = "ORDER BY particulars ASC, description ASC"
        if self.sort_column and self.sort_direction:
            col_map = {
                "qty": "qty", "unit": "unit", "particulars": "particulars",
                "description": "description", "unit_cost": "unit_cost", "amount": "(qty * unit_cost)"
            }
            db_col = col_map.get(self.sort_column, "particulars")
            order_clause = f"ORDER BY {db_col} {self.sort_direction}, particulars ASC"

        base_where = "WHERE qty <= 5 AND" if self.app.filter_low_stock else "WHERE"
        cursor.execute(
            f"SELECT *, (qty * unit_cost) AS amount FROM inventory {base_where} (particulars LIKE %s OR description LIKE %s OR brand LIKE %s) {order_clause}",
            (f"%{query_str}%", f"%{query_str}%", f"%{query_str}%")
        )
        all_items = cursor.fetchall()
        cursor.close()
        conn.close()

        headers = [("Qty", "qty"), ("Unit", "unit"), ("Particulars", "particulars"), ("Description", "description"), ("Unit Cost", "unit_cost"), ("Amount", "amount")]
        header_frame = ctk.CTkFrame(self.stock_scroll, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 5))

        for label_text, col_key in headers:
            sort_arrow = " ↕"
            if self.sort_column == col_key:
                sort_arrow = " ▲" if self.sort_direction == "ASC" else " ▼"
            btn = ctk.CTkButton(header_frame, text=f"{label_text}{sort_arrow}", font=ctk.CTkFont(size=11, weight="bold"), fg_color="transparent", text_color="gray", hover_color=("gray85", "gray25"), height=24, command=lambda k=col_key: self.toggle_column_sort(k))
            btn.pack(side="left", expand=True, fill="x")

        grouped = {}
        for item in all_items:
            part = item["particulars"]
            grouped.setdefault(part, []).append(item)

        categories_list = list(grouped.keys())
        total_categories = len(categories_list)

        if self.inv_page_size == "All":
            displayed_categories = categories_list
            total_pages = 1
        else:
            p_size = int(self.inv_page_size)
            total_pages = max(1, (total_categories + p_size - 1) // p_size)
            self.inv_page = min(self.inv_page, total_pages)
            start_idx = (self.inv_page - 1) * p_size
            displayed_categories = categories_list[start_idx:start_idx + p_size]

        for part_name in displayed_categories:
            items = grouped[part_name]
            total_qty = sum(i["qty"] for i in items)
            total_val = sum(i["amount"] for i in items)
            is_expanded = part_name in self.expanded_categories or bool(query_str) or self.app.filter_low_stock

            cat_card = ctk.CTkFrame(self.stock_scroll, corner_radius=8, fg_color=("gray85", "gray25"))
            cat_card.pack(fill="x", pady=3)

            cat_header = ctk.CTkFrame(cat_card, fg_color="transparent")
            cat_header.pack(fill="x", padx=10, pady=8)

            arrow = "▼" if is_expanded else "►"
            btn_toggle = ctk.CTkButton(cat_header, text=f"{arrow}  {part_name} ({len(items)} variants)", font=ctk.CTkFont(size=13, weight="bold"), fg_color="transparent", anchor="w", command=lambda p=part_name: self.toggle_category_accordion(p))
            btn_toggle.pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(cat_header, text=f"Stock: {total_qty} pcs | ₱{total_val:,.2f}", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray").pack(side="right", padx=10)

            if is_expanded:
                body = ctk.CTkFrame(cat_card, fg_color="transparent")
                body.pack(fill="x", padx=15, pady=(0, 8))

                for item in items:
                    row = ctk.CTkFrame(body, fg_color=("gray90", "gray20"), corner_radius=6)
                    row.pack(fill="x", pady=2)

                    qty_color = "#d9534f" if item['qty'] <= 5 else ("gray10", "gray90")
                    ctk.CTkLabel(row, text=f"{item['qty']}", font=ctk.CTkFont(weight="bold"), text_color=qty_color, width=40).pack(side="left", padx=5)
                    ctk.CTkLabel(row, text=f"{item['unit']}", width=40).pack(side="left", padx=5)

                    brand_str = f"[{item['brand']}] " if item['brand'] else ""
                    btn_item = ctk.CTkButton(row, text=f"{brand_str}{item['description']}", font=ctk.CTkFont(weight="bold"), fg_color="transparent", anchor="w", command=lambda i=item: self.select_inventory_item(i))
                    btn_item.pack(side="left", fill="x", expand=True, padx=5)

                    ctk.CTkLabel(row, text=f"₱{item['unit_cost']:,.2f}", width=80).pack(side="left", padx=5)
                    ctk.CTkLabel(row, text=f"₱{item['amount']:,.2f}", font=ctk.CTkFont(weight="bold"), width=90).pack(side="right", padx=5)

        self.bind_mouse_wheel(self.stock_scroll)
        self.render_inventory_pagination(total_categories, total_pages)

    def render_inventory_pagination(self, total_categories, total_pages):
        for w in self.inv_page_bar.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.inv_page_bar, text=f"Total Categories: {total_categories}", font=ctk.CTkFont(size=11), text_color="gray").pack(side="left", padx=5)

        opt = ctk.CTkOptionMenu(self.inv_page_bar, values=["5", "10", "15", "All"], width=70, height=26, command=self.change_inv_page_size)
        opt.set(str(self.inv_page_size))
        opt.pack(side="left", padx=5)

        btn_prev = ctk.CTkButton(self.inv_page_bar, text="◄ Prev", width=65, height=26, state="normal" if self.inv_page > 1 else "disabled", command=self.prev_inv_page)
        btn_prev.pack(side="right", padx=2)

        ctk.CTkLabel(self.inv_page_bar, text=f"Page {self.inv_page} of {total_pages}", font=ctk.CTkFont(size=12, weight="bold")).pack(side="right", padx=8)

        btn_next = ctk.CTkButton(self.inv_page_bar, text="Next ►", width=65, height=26, state="normal" if self.inv_page < total_pages else "disabled", command=self.next_inv_page)
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
        self.set_input(self.inv_particulars, item["particulars"])
        self.set_input(self.inv_brand, item["brand"] or "")
        self.set_input(self.inv_qty, str(item["qty"]))
        self.set_input(self.inv_desc, item["description"] or "")
        self.set_input(self.inv_cost, str(item["unit_cost"]))
        self.display_image_preview(item["image_path"])

    def export_csv_dialog(self):
        f = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Document", "*.csv")], initialfile="Inventory_Export.csv")
        if not f:
            return

        conn = self.db.get_connection()
        if not conn:
            return

        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT qty AS Qty, unit AS Unit, particulars AS Particulars, description AS Description, unit_cost AS 'Unit Cost', (qty * unit_cost) AS Amount FROM inventory")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if rows:
            with open(f, mode='w', newline='', encoding='utf-8') as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=["Qty", "Unit", "Particulars", "Description", "Unit Cost", "Amount"])
                writer.writeheader()
                writer.writerows(rows)
            messagebox.showinfo("Export Successful", f"Inventory saved to {f}")

    def import_csv_dialog(self):
        f = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if not f:
            return
        threading.Thread(target=self._process_csv_import, args=(f,), daemon=True).start()

    def _process_csv_import(self, filepath):
        conn = self.db.get_connection()
        if not conn:
            self.import_queue.put(("error", "Could not get database connection."))
            return
        cursor = conn.cursor()
        imported_count = 0

        try:
            with open(filepath, mode='r', encoding='utf-8', errors='ignore') as csv_file:
                reader = csv.reader(csv_file)
                header = None
                for row in reader:
                    clean_row = [c.strip() for c in row if c.strip()]
                    if any('unit' in c.lower() or 'particular' in c.lower() or 'description' in c.lower() for c in clean_row):
                        header = [c.strip() for c in row]
                        break

                if not header:
                    self.import_queue.put(("error", "Could not find valid column headers in the CSV file."))
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
            self.import_queue.put(("success", f"Successfully imported {imported_count} items from CSV!"))
        except Exception as err:
            self.import_queue.put(("error", str(err)))
        finally:
            cursor.close()
            conn.close()
            self.after(100, self._check_import_queue)

    def _check_import_queue(self):
        try:
            status, msg = self.import_queue.get_nowait()
            if status == "success":
                messagebox.showinfo("Success", msg)
                self.app.show_inventory_view()
            else:
                messagebox.showerror("CSV Error", f"Failed to import CSV file:\n{msg}")
        except queue.Empty:
            self.after(100, self._check_import_queue)