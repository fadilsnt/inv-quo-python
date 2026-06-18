import os
import tkinter as tk
from tkinter import ttk, messagebox
from db_connect import connect_db
from invoice_generator import generate_pdf, save_invoice_to_db


def fetch_all_invoices():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT invoice_id, invoice_number, customer_name, date, invoice_type,
               status, gross_amount
        FROM invoices
        ORDER BY date DESC, invoice_id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def fetch_invoice_detail(invoice_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT invoice_id, customer_name, phone_number, address, date,
               invoice_number, invoice_type, status, subtotal, discount,
               tax, gross_amount, notes, pdf_path
        FROM invoices WHERE invoice_id = %s
    """, (invoice_id,))
    invoice = cursor.fetchone()
    if not invoice:
        conn.close()
        return None, []

    cursor.execute("""
        SELECT description, quantity, unit_price, total
        FROM invoice_items WHERE invoice_id = %s
    """, (invoice_id,))
    items = cursor.fetchall()
    conn.close()
    return invoice, items


def delete_invoice_from_db(invoice_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT pdf_path FROM invoices WHERE invoice_id = %s", (invoice_id,))
    row = cursor.fetchone()
    pdf_path = row[0] if row else None

    cursor.execute("DELETE FROM invoice_items WHERE invoice_id = %s", (invoice_id,))
    cursor.execute("DELETE FROM invoices WHERE invoice_id = %s", (invoice_id,))
    conn.commit()
    conn.close()

    if pdf_path and os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
        except OSError:
            pass


def update_invoice_in_db(invoice_id, customer, items, subtotal, discount, tax, gross, notes, pdf_path):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE invoices SET
            customer_name = %s, phone_number = %s, address = %s, date = %s,
            invoice_number = %s, invoice_type = %s, status = %s,
            subtotal = %s, discount = %s, tax = %s, gross_amount = %s,
            notes = %s, pdf_path = %s
        WHERE invoice_id = %s
    """, (
        customer['name'], customer['phone'], customer['address'], customer['date'],
        customer['invoice_number'], customer['invoice_type'], customer['status'],
        subtotal, discount, tax, gross, notes, pdf_path, invoice_id
    ))
    cursor.execute("DELETE FROM invoice_items WHERE invoice_id = %s", (invoice_id,))
    for item in items:
        cursor.execute("""
            INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total)
            VALUES (%s, %s, %s, %s, %s)
        """, (invoice_id, item['desc'], item['qty'], item['unit_price'], item['total']))
    conn.commit()
    conn.close()


class InvoiceManagerWindow:
    COLUMNS = ('select', 'invoice_number', 'customer_name', 'date', 'invoice_type', 'status', 'gross_amount', 'action')

    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("Manage Invoice Data")
        self.window.geometry("850x450")
        self.window.minsize(600, 300)
        self.window.resizable(True, True)

        self._build_ui()
        self.refresh_list()

    def _build_ui(self):
        frame = ttk.Frame(self.window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Invoices", font=('Segoe UI', 11, 'bold')).pack(anchor=tk.W, pady=(0, 8))

        search_frame = ttk.Frame(frame)
        search_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(search_frame, text="Pencarian:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.bind('<KeyRelease>', lambda e: self.refresh_list())
        self.search_entry.bind('<Return>', lambda e: self.refresh_list())
        ttk.Button(search_frame, text="Search", command=self.refresh_list).pack(side=tk.LEFT, padx=5)

        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        headings = {
            'select': ('Pilih', 50),
            'invoice_number': ('Invoice No.', 120),
            'customer_name': ('Customer', 180),
            'date': ('Date', 90),
            'invoice_type': ('Type', 90),
            'status': ('Status', 70),
            'gross_amount': ('Total', 120),
            'action': ('Aksi', 80),
        }

        self.tree = ttk.Treeview(
            tree_frame,
            columns=self.COLUMNS,
            show='headings',
            height=15
        )
        for col, (text, width) in headings.items():
            self.tree.heading(col, text=text)
            if col == 'gross_amount':
                anchor = tk.E
            elif col in ('select', 'action'):
                anchor = tk.CENTER
            else:
                anchor = tk.W
            self.tree.column(col, width=width, anchor=anchor)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind('<Double-1>', lambda e: self.edit_selected())
        self.tree.bind('<ButtonRelease-1>', self.on_click)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(btn_frame, text="Refresh", command=self.refresh_list).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Edit", command=self.edit_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Delete", command=self.delete_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=2)

    def refresh_list(self):
        self.tree.delete(*self.tree.get_children())
        query = self.search_entry.get().strip().lower() if hasattr(self, 'search_entry') else ""
        try:
            for row in fetch_all_invoices():
                invoice_id, inv_no, customer, date, inv_type, status, gross = row
                date_str = date.strftime("%Y-%m-%d") if hasattr(date, 'strftime') else str(date)
                
                if query:
                    inv_no_str = str(inv_no).lower()
                    customer_str = str(customer).lower()
                    date_str_lower = date_str.lower()
                    inv_type_str = str(inv_type).lower()
                    status_str = str(status).lower()
                    
                    if (query not in inv_no_str and 
                        query not in customer_str and 
                        query not in date_str_lower and 
                        query not in inv_type_str and 
                        query not in status_str):
                        continue

                gross_str = f"Rp {float(gross):,.0f}"
                self.tree.insert('', 'end', iid=str(invoice_id), values=(
                    "☐", inv_no, customer, date_str, inv_type, status, gross_str, "Hapus"
                ))
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load invoices:\n{e}", parent=self.window)

    def _get_selected_id(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select an invoice first.", parent=self.window)
            return None
        return int(selected[0])

    def delete_selected(self):
        # 1. Check if there are checked checkboxes
        checked_ids = []
        for item_id in self.tree.get_children():
            if self.tree.set(item_id, 'select') == "☑":
                checked_ids.append(int(item_id))

        if checked_ids:
            if not messagebox.askyesno(
                "Confirm Delete",
                f"Delete {len(checked_ids)} selected invoice(s)?\nThis action cannot be undone.",
                parent=self.window
            ):
                return

            try:
                for inv_id in checked_ids:
                    delete_invoice_from_db(inv_id)
                    if self.app.editing_invoice_id == inv_id:
                        self.app.editing_invoice_id = None
                self.refresh_list()
                messagebox.showinfo("Deleted", f"{len(checked_ids)} invoice(s) have been deleted.", parent=self.window)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete invoices:\n{e}", parent=self.window)
            return

        # 2. Fallback to single selection
        invoice_id = self._get_selected_id()
        if invoice_id is None:
            return

        inv_no = self.tree.item(str(invoice_id), 'values')[1]
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete invoice '{inv_no}'?\nThis action cannot be undone.",
            parent=self.window
        ):
            return

        try:
            delete_invoice_from_db(invoice_id)
            if self.app.editing_invoice_id == invoice_id:
                self.app.editing_invoice_id = None
            self.refresh_list()
            messagebox.showinfo("Deleted", f"Invoice '{inv_no}' has been deleted.", parent=self.window)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete invoice:\n{e}", parent=self.window)

    def edit_selected(self):
        invoice_id = self._get_selected_id()
        if invoice_id is None:
            return

        try:
            invoice, items = fetch_invoice_detail(invoice_id)
            if not invoice:
                messagebox.showerror("Error", "Invoice not found.", parent=self.window)
                return
            self.app.load_invoice_for_edit(invoice, items)
            self.window.destroy()
            messagebox.showinfo(
                "Edit Mode",
                "Invoice loaded into the form.\nModify the data and click 'Update Invoice' to save changes.",
                parent=self.app.root
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load invoice:\n{e}", parent=self.window)

    def on_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            item_id = self.tree.identify_row(event.y)
            if item_id:
                if column == "#1":
                    current_val = self.tree.set(item_id, 'select')
                    new_val = "☑" if current_val == "☐" else "☐"
                    self.tree.set(item_id, 'select', new_val)
                elif column == "#8":
                    self.tree.selection_set(item_id)
                    self.delete_selected()
