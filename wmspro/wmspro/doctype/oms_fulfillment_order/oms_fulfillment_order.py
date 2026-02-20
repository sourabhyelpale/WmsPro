# Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
# For license information, please see license.txt



import frappe
from frappe.model.document import Document
from frappe.utils import nowdate


class OMSFulfillmentOrder(Document):

    def allocate_inventory(self):

        if self.allocation_complete:
            frappe.throw("Inventory already allocated.")

        if not self.source_warehouse:
            frappe.throw("Source Warehouse is required.")

        for item in self.items:

            required_qty = item.qty_required
            allocated_qty = 0

            # Fetch bins sorted by FEFO (expiry date ascending)
            bins = frappe.db.sql("""
                SELECT
                    name,
                    bin,
                    item_code,
                    batch_no,
                    warehouse, 
                    expiry_date,
                    SUM(qty_change) as balance_qty
                FROM `tabWMS Bin Ledger`
                WHERE
                    warehouse = %s
                    AND item_code = %s
                GROUP BY bin, batch_no
                HAVING balance_qty > 0
                ORDER BY expiry_date ASC
            """, (self.source_warehouse, item.item_code), as_dict=True)

            if not bins:
                frappe.throw(f"No stock available for Item {item.item_code}")

            for bin_row in bins:

                available = bin_row.balance_qty
                if available <= 0:
                    continue

                qty_to_allocate = min(required_qty - allocated_qty, available)

                if qty_to_allocate <= 0:
                    break

                # Write Reservation Entry in WMS Bin Ledger
                reservation = frappe.get_doc({
                    "doctype": "WMS Bin Ledger",
                    "bin": bin_row.bin,
                    "item_code": item.item_code,
                    "batch_no": bin_row.batch_no,
                    "warehouse": self.source_warehouse,
                    "expiry_date": bin_row.expiry_date,
                    "qty_change": -qty_to_allocate,
                    "voucher_type": "OMS Fulfillment Order",
                    "voucher_no": self.name
                })
                reservation.insert(ignore_permissions=True)

                # Update Child Table Allocation Fields
                item.qty_allocated += qty_to_allocate 
                item.batch_no = bin_row.batch_no
                item.bin_location = bin_row.bin

                allocated_qty += qty_to_allocate

                if allocated_qty >= required_qty:
                    break

            if allocated_qty < required_qty:
                frappe.throw(
                    f"Insufficient stock for {item.item_code}. "
                    f"Required: {required_qty}, Allocated: {allocated_qty}"
                )

        self.allocation_complete = 1
        self.status = "Allocated"

        frappe.msgprint("Inventory Allocation Completed Successfully.")