import frappe
from frappe.model.document import Document
from frappe.utils import today, now
from wmspro.wmspro.bin_ledger import create_bin_ledger_entry


class WMSPutawayTask(Document):

    def validate(self):
        self.set_warehouses_from_bins()


    def set_warehouses_from_bins(self):

        if self.from_bin:
            self.from_warehouse = frappe.db.get_value(
                "WMS Bin", self.from_bin, "warehouse"
            )

        if self.actual_bin:
            self.to_warehouse = frappe.db.get_value(
                "WMS Bin", self.actual_bin, "warehouse"
            )


    @frappe.whitelist()
    def complete_task(self):

        if self.status == "Completed":
            frappe.throw("Task already completed")

        self.set_warehouses_from_bins()

        if not self.from_warehouse or not self.to_warehouse:
            frappe.throw("Warehouses not properly set")

        if self.from_warehouse != self.to_warehouse:

            se = frappe.new_doc("Stock Entry")
            se.stock_entry_type = "Material Transfer"
            se.posting_date = today()
            se.posting_time = now()

            se.append("items", {
                "item_code": self.item_code,
                "item_name": frappe.db.get_value("Item", self.item_code, "item_name"),
                "qty": self.quantity,
                "s_warehouse": self.from_warehouse,
                "t_warehouse": self.to_warehouse,
                "batch_no": self.batch_no
            })

            se.insert(ignore_permissions=True)
            se.submit()

            self.stock_entry_reference = se.name



        # Remove from source bin
        create_bin_ledger_entry(
            bin_location=self.from_bin,
            item_code=self.item_code,
            qty_change=-float(self.quantity),
            batch_no=self.batch_no,
            voucher_type="WMS Putaway Task",
            voucher_no=self.name
        )

        # Add to destination bin
        create_bin_ledger_entry(
            bin_location=self.actual_bin,
            item_code=self.item_code,
            qty_change=float(self.quantity),
            batch_no=self.batch_no,
            voucher_type="WMS Putaway Task",
            voucher_no=self.name
        )

        self.status = "Completed"
        self.completed_at = now()
        self.save(ignore_permissions=True)

        frappe.msgprint("Put Away Completed Successfully")