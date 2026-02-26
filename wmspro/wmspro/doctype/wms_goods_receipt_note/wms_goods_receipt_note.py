import frappe
from frappe.utils import today, now
from frappe.model.document import Document
from wmspro.wmspro.bin_ledger import create_bin_ledger_entry


class WMSGoodsReceiptNote(Document):

    # ----------------------------------------
    # 1️⃣ When GRN is Created → Create PR Draft
    # ----------------------------------------
    def after_insert(self):

        pr = frappe.new_doc("Purchase Receipt")
        pr.company = self.company
        pr.posting_date = today()
        pr.posting_time = now()
        pr.supplier = self.supplier
        pr.set_warehouse = self.warehouse
        pr.custom_department = "Stores - LD"
        pr.custom_invoice_no = f"AUTO-{frappe.utils.random_string(6)}"

        for item in self.wms_grn_item:

            qty = item.qty_expected or item.qty_accepted

            if not qty or qty <= 0:
                frappe.throw(f"Quantity cannot be zero for Item {item.item_code}")

            pr.append("items", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": qty,
                "conversion_factor": 1,
                "stock_uom": item.stock_uom,
                "rate": item.rate,
                "warehouse": self.warehouse
            })

        pr.insert(ignore_permissions=True)

        # store reference
        self.db_set("purchase_receipt", pr.name)

        frappe.msgprint(f"Purchase Receipt {pr.name} Created")


    # ----------------------------------------
    # 2️⃣ When GRN is Submitted
    #    → Submit PR
    #    → Create Bin Ledger
    # ----------------------------------------
    def on_submit(self):

        # ---- Submit Purchase Receipt ----
        if self.purchase_receipt:

            pr = frappe.get_doc("Purchase Receipt", self.purchase_receipt)

            if pr.docstatus == 0:
                pr.submit()

        # ---- Create Bin Ledger Entries ----
        staging_bin = self.get_staging_bin_for_warehouse()

        for item in self.wms_grn_item:

            qty = item.qty_expected or item.qty_accepted

            if not qty:
                continue

            create_bin_ledger_entry(
                bin_location=staging_bin,
                item_code=item.item_code,
                qty_change=float(qty),
                batch_no=item.batch_no,
                voucher_type="WMS Goods Receipt Note",
                voucher_no=self.name
            )

        frappe.msgprint("Purchase Receipt Submitted & Bin Ledger Updated")
        self.create_putaway_tasks(staging_bin)


    def create_putaway_tasks(self, staging_bin):

        for item in self.wms_grn_item:

            qty = item.qty_expected or item.qty_accepted

            if not qty:
                continue

            task = frappe.get_doc({
                "doctype": "WMS Putaway Task",
                "grn_reference": self.name,
                "warehouse": self.warehouse,
                "from_warehouse": self.warehouse,
                "to_warehouse": self.warehouse,
                "item_code": item.item_code,
                "batch_no": item.batch_no,
                "quantity": qty,
                "uom": item.stock_uom,
                "from_bin": staging_bin,
                "suggested_bin": get_suggested_bin(item.item_code, self.warehouse),
                "task_date": frappe.utils.today(),
                "priority": "Medium",
                "status": "Pending"
            })

            task.insert(ignore_permissions=True)


    def get_staging_bin_for_warehouse(self):

        staging_bin = frappe.db.get_value(
            "WMS Bin",
            {
                "warehouse": self.warehouse,
                "is_staging": 1
            },
            "name"
        )

        if not staging_bin:
            frappe.throw(f"No staging bin configured for warehouse {self.warehouse}")

        return staging_bin


def get_suggested_bin(item_code, warehouse):

    bin_name = frappe.db.get_value(
        "WMS Bin",
        {
            "warehouse": warehouse,
            "is_staging": 0
        },
        "name"
    )

    if not bin_name:
        frappe.throw("No storage bin configured")

    return bin_name