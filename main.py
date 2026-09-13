import datetime
import re
import customtkinter as ctk
from tkinter import messagebox

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

        # --- ROLE & AUTHENTICATION STATE ---
        self.current_role = None  # Options: "cashier", "owner", or None
        self.owner_password = "owner_1234"      # Default preset password
        self.cashier_password = "cashier_1234"    # Default cashier password

        self.cart = []
        self.filter_low_stock = False
        self.current_view = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()

        self.main_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=25, pady=25, sticky="nsew")

        # Launch into the role selection / login page
        self.show_login_page()

    def _build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")

        brand_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        brand_frame.pack(fill="x", padx=20, pady=(25, 10))

        ctk.CTkLabel(brand_frame, text="⚡ AUTO PARTS", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(brand_frame, text="Enterprise ERP System", font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

        # Active Role Status Badge
        self.lbl_role_status = ctk.CTkLabel(
            self.sidebar_frame, text="Status: Not Logged In",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#d9534f"
        )
        self.lbl_role_status.pack(anchor="w", padx=20, pady=(0, 15))

        self.btn_nav_pos = self.create_nav_button("🛒  POS Terminal", self.show_pos_view)
        self.btn_nav_inv = self.create_nav_button("📦  Inventory System", self.show_inventory_view)
        self.btn_nav_presets = self.create_nav_button("⚙️  Presets & Configs", self.show_presets_view)
        self.btn_nav_est = self.create_nav_button("🧮  Job Estimator", self.show_estimator_view)
        self.btn_nav_sales = self.create_nav_button("🧾  Sales Analytics", self.show_sales_view)

        # Owner Access & Settings Button
        self.btn_owner_access = ctk.CTkButton(
            self.sidebar_frame, text="👑  Owner Access", font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1f6aa5", hover_color="#144870", height=38, corner_radius=8,
            command=self.handle_owner_access_click
        )
        self.btn_owner_access.pack(fill="x", padx=15, pady=(15, 5))

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

    def update_role_badge(self):
        if self.current_role == "owner":
            self.lbl_role_status.configure(text="Role: Owner (Full Control)", text_color="#2ba84a")
        elif self.current_role == "cashier":
            self.lbl_role_status.configure(text="Role: Cashier (Restricted)", text_color="#e0a96d")
        else:
            self.lbl_role_status.configure(text="Status: Not Logged In", text_color="#d9534f")

    # --- REUSABLE PASSWORD FIELD WITH REVEAL BUTTON ---
    def create_password_field(self, parent, placeholder_text, width=280, height=36):
        """Creates a masked entry field with a toggle button to show or hide the password."""
        container = ctk.CTkFrame(parent, fg_color="transparent")
        
        entry = ctk.CTkEntry(
            container, show="*",
            placeholder_text=placeholder_text,
            width=width - 45, height=height
        )
        entry.pack(side="left", padx=(0, 5))

        def toggle_reveal():
            if entry.cget("show") == "*":
                entry.configure(show="")
                reveal_btn.configure(text="👁️")
            else:
                entry.configure(show="*")
                reveal_btn.configure(text="🔒")

        reveal_btn = ctk.CTkButton(
            container, text="🔒", width=40, height=height,
            fg_color=("gray75", "gray30"), hover_color=("gray65", "gray40"),
            command=toggle_reveal
        )
        reveal_btn.pack(side="left")

        return container, entry

    # --- PASSWORD VALIDATION LOGIC ---
    def validate_owner_password_rules(self, password):
        """Ensures password has at least 8 chars, 1 number, and 1 special char (@, *, _, -)."""
        if len(password) < 8:
            return False, "Owner password must be at least 8 characters long."
        if not re.search(r'\d', password):
            return False, "Owner password must contain at least 1 number."
        if not re.search(r'[@*_\-]', password):
            return False, "Owner password must contain at least 1 special character (@, *, _, -)."
        return True, ""

    # --- LOGIN PAGE VIEW ---
    def show_login_page(self):
        self.clear_main_frame()
        login_container = ctk.CTkFrame(self.main_frame, corner_radius=15)
        login_container.pack(expand=True, fill="both", padx=40, pady=40)
        self.current_view = login_container

        ctk.CTkLabel(login_container, text="🔑 ERP Gateway Login", font=ctk.CTkFont(size=26, weight="bold")).pack(pady=(40, 10))
        ctk.CTkLabel(login_container, text="Select your access role to continue", font=ctk.CTkFont(size=14), text_color="gray").pack(pady=(0, 25))

        box_frame = ctk.CTkFrame(login_container, fg_color="transparent")
        box_frame.pack(pady=10)

        # Cashier Login Box
        cashier_card = ctk.CTkFrame(box_frame, width=300, height=250, corner_radius=12)
        cashier_card.pack(side="left", padx=20, pady=10)
        cashier_card.pack_propagate(False)

        ctk.CTkLabel(cashier_card, text="🛒 Cashier", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(cashier_card, text="POS & View-Only Inventory", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(0, 10))
        
        c_frame, c_pwd = self.create_password_field(cashier_card, "Enter Cashier Password", width=250)
        c_frame.pack(pady=10)

        def login_as_cashier():
            if c_pwd.get() == self.cashier_password:
                self.current_role = "cashier"
                self.update_role_badge()
                self.show_pos_view()
            else:
                messagebox.showerror("Access Denied", "Incorrect Cashier password.")

        ctk.CTkButton(cashier_card, text="Login as Cashier", fg_color="#2ba84a", command=login_as_cashier).pack(pady=10)

        # Owner Login Box
        owner_card = ctk.CTkFrame(box_frame, width=300, height=250, corner_radius=12)
        owner_card.pack(side="left", padx=20, pady=10)
        owner_card.pack_propagate(False)

        ctk.CTkLabel(owner_card, text="👑 Owner", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(owner_card, text="Full Administrative Privileges", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(0, 10))
        
        o_frame, o_pwd = self.create_password_field(owner_card, "Enter Owner Password", width=260)
        o_frame.pack(pady=10)

        def login_as_owner():
            if o_pwd.get() == self.owner_password:
                self.current_role = "owner"
                self.update_role_badge()
                self.show_pos_view()
            else:
                messagebox.showerror("Access Denied", "Incorrect Owner password.")

        ctk.CTkButton(owner_card, text="Login as Owner", fg_color="#1f6aa5", command=login_as_owner).pack(pady=10)

    # --- OWNER ACCESS HANDLER & MODALS ---
    def handle_owner_access_click(self):
        if self.current_role == "owner":
            self.show_owner_settings_modal()
        else:
            self.show_owner_login_modal()

    def show_owner_login_modal(self, pending_view_callback=None):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Owner Authentication Required")
        dialog.geometry("420x270")
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.transient(self)

        ctk.CTkLabel(dialog, text="🔒 Owner Access Login", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(25, 5))
        ctk.CTkLabel(dialog, text="Enter owner password to unlock admin privileges.", font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(0, 15))

        pwd_frame, pwd_entry = self.create_password_field(dialog, "e.g. owner_1234 (min 8 chars, 1 num, 1 spec @,*,_,-)", width=350)
        pwd_frame.pack(pady=5)
        pwd_entry.focus()

        def attempt_login():
            if pwd_entry.get() == self.owner_password:
                self.current_role = "owner"
                self.update_role_badge()
                dialog.destroy()
                messagebox.showinfo("Success", "Owner privileges granted!")
                if pending_view_callback:
                    pending_view_callback()
            else:
                messagebox.showerror("Access Denied", "Incorrect owner password.")

        pwd_entry.bind("<Return>", lambda e: attempt_login())
        ctk.CTkButton(dialog, text="Authenticate 🔓", fg_color="#1f6aa5", height=36, width=340, font=ctk.CTkFont(weight="bold"), command=attempt_login).pack(pady=15)

    def show_owner_settings_modal(self):
        """Modal with tabs allowing the owner to update owner & cashier passwords after verifying the current password."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Owner Settings & Password Management")
        dialog.geometry("460x420")
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.transient(self)

        tabview = ctk.CTkTabview(dialog, width=420, height=360)
        tabview.pack(padx=20, pady=15)

        tab_owner = tabview.add("Owner Password")
        tab_cashier = tabview.add("Cashier Password")

        # --- Tab 1: Owner Password Change ---
        ctk.CTkLabel(tab_owner, text="Update Owner Access Password", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(10, 5))
        
        ctk.CTkLabel(tab_owner, text="Current Owner Password:", font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", padx=30, pady=(5, 2))
        curr_o_frame, curr_o_pwd = self.create_password_field(tab_owner, "Enter current owner password", width=340)
        curr_o_frame.pack(pady=(0, 8))

        ctk.CTkLabel(tab_owner, text="New Owner Password:", font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", padx=30, pady=(5, 2))
        new_o_frame, new_o_pwd = self.create_password_field(tab_owner, "e.g. owner_1234 (min 8 chars, 1 num, 1 spec @,*,_,-)", width=340)
        new_o_frame.pack(pady=(0, 10))

        def update_owner_pwd():
            # Verify Current Password
            if curr_o_pwd.get() != self.owner_password:
                messagebox.showerror("Verification Failed", "Incorrect current owner password.")
                return

            # Validate New Password
            pwd = new_o_pwd.get()
            valid, msg = self.validate_owner_password_rules(pwd)
            if not valid:
                messagebox.showwarning("Invalid Password Format", msg)
                return

            self.owner_password = pwd
            messagebox.showinfo("Success", "Owner password updated successfully!")
            curr_o_pwd.delete(0, 'end')
            new_o_pwd.delete(0, 'end')

        ctk.CTkButton(tab_owner, text="Save New Owner Password", fg_color="#1f6aa5", command=update_owner_pwd).pack(pady=12)

        # --- Tab 2: Cashier Password Change ---
        ctk.CTkLabel(tab_cashier, text="Update Cashier Login Password", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(10, 5))
        
        ctk.CTkLabel(tab_cashier, text="Current Cashier Password:", font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", padx=30, pady=(5, 2))
        curr_c_frame, curr_c_pwd = self.create_password_field(tab_cashier, "Enter current cashier password", width=340)
        curr_c_frame.pack(pady=(0, 8))

        ctk.CTkLabel(tab_cashier, text="New Cashier Password:", font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", padx=30, pady=(5, 2))
        new_c_frame, new_c_pwd = self.create_password_field(tab_cashier, "Enter new cashier password", width=340)
        new_c_frame.pack(pady=(0, 10))

        def update_cashier_pwd():
            # Verify Current Password
            if curr_c_pwd.get() != self.cashier_password:
                messagebox.showerror("Verification Failed", "Incorrect current cashier password.")
                return

            # Validate New Password
            pwd = new_c_pwd.get().strip()
            if not pwd:
                messagebox.showwarning("Warning", "New cashier password cannot be blank.")
                return

            self.cashier_password = pwd
            messagebox.showinfo("Success", "Cashier password updated successfully!")
            curr_c_pwd.delete(0, 'end')
            new_c_pwd.delete(0, 'end')

        ctk.CTkButton(tab_cashier, text="Save New Cashier Password", fg_color="#2ba84a", command=update_cashier_pwd).pack(pady=12)

    # --- ROUTING WITH ROLE-BASED ACCESS CONTROL ---
    def show_pos_view(self):
        if not self.current_role:
            self.show_login_page()
            return
        self.clear_main_frame()
        self.current_view = POSView(self.main_frame, self.db, self)
        self.current_view.pack(fill="both", expand=True)

    def show_inventory_view(self):
        if not self.current_role:
            self.show_login_page()
            return
        self.clear_main_frame()
        self.current_view = InventoryView(self.main_frame, self.db, self)
        self.current_view.pack(fill="both", expand=True)

        # Restrict Cashier privileges: disable edit/add capabilities if present
        if self.current_role == "cashier":
            self.apply_cashier_inventory_restrictions(self.current_view)

    def apply_cashier_inventory_restrictions(self, view_obj):
        """Recursively disables action buttons (Add, Edit, Delete, Save) for Cashier read-only mode."""
        for widget in view_obj.winfo_children():
            if isinstance(widget, ctk.CTkButton):
                text = str(widget.cget("text")).lower()
                if any(k in text for k in ["add", "edit", "delete", "save", "update", "clear"]):
                    widget.configure(state="disabled")
            elif hasattr(widget, "winfo_children"):
                self.apply_cashier_inventory_restrictions(widget)

    def show_presets_view(self):
        if self.current_role != "owner":
            self.show_owner_login_modal(self.show_presets_view)
            return
        self.clear_main_frame()
        self.current_view = PresetsView(self.main_frame, self.db, self)
        self.current_view.pack(fill="both", expand=True)

    def show_estimator_view(self):
        if self.current_role != "owner":
            self.show_owner_login_modal(self.show_estimator_view)
            return
        self.clear_main_frame()
        self.current_view = EstimatorView(self.main_frame, self.db, self)
        self.current_view.pack(fill="both", expand=True)

    def show_sales_view(self):
        if self.current_role != "owner":
            self.show_owner_login_modal(self.show_sales_view)
            return
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