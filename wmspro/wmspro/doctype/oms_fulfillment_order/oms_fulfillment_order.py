# Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
# For license information, please see license.txt

# import frappe
# from frappe.model.document import Document
# from frappe.utils import nowdate


# class OMSFulfillmentOrder(Document):

#     def allocate_inventory(self):

#         if self.allocation_complete:
#             frappe.throw("Inventory already allocated.")

#         if not self.source_warehouse:
#             frappe.throw("Source Warehouse is required.")

#         for item in self.items:

#             required_qty = item.qty_required
#             allocated_qty = 0

#             # Fetch bins sorted by FEFO (expiry date ascending)
#             bins = frappe.db.sql("""
#                 SELECT
#                     name,
#                     bin,
#                     item_code,
#                     batch_no,
#                     warehouse, 
#                     expiry_date,
#                     SUM(qty_change) as balance_qty
#                 FROM `tabWMS Bin Ledger`
#                 WHERE
#                     warehouse = %s
#                     AND item_code = %s
#                 GROUP BY bin, batch_no
#                 HAVING balance_qty > 0
#                 ORDER BY expiry_date ASC
#             """, (self.source_warehouse, item.item_code), as_dict=True)

#             if not bins:
#                 frappe.throw(f"No stock available for Item {item.item_code}")

#             for bin_row in bins:

#                 available = bin_row.balance_qty
#                 if available <= 0:
#                     continue

#                 qty_to_allocate = min(required_qty - allocated_qty, available)

#                 if qty_to_allocate <= 0:
#                     break

#                 # Write Reservation Entry in WMS Bin Ledger
#                 reservation = frappe.get_doc({
#                     "doctype": "WMS Bin Ledger",
#                     "bin": bin_row.bin,
#                     "item_code": item.item_code,
#                     "batch_no": bin_row.batch_no,
#                     "warehouse": self.source_warehouse,
#                     "expiry_date": bin_row.expiry_date,
#                     "qty_change": -qty_to_allocate,
#                     "voucher_type": "OMS Fulfillment Order",
#                     "voucher_no": self.name
#                 })
#                 reservation.insert(ignore_permissions=True)

#                 # Update Child Table Allocation Fields
#                 item.qty_allocated += qty_to_allocate 
#                 item.batch_no = bin_row.batch_no
#                 item.bin_location = bin_row.bin

#                 allocated_qty += qty_to_allocate

#                 if allocated_qty >= required_qty:
#                     break

#             if allocated_qty < required_qty:
#                 frappe.throw(
#                     f"Insufficient stock for {item.item_code}. "
#                     f"Required: {required_qty}, Allocated: {allocated_qty}"
#                 )

#         self.allocation_complete = 1
#         self.status = "Allocated"

#         frappe.msgprint("Inventory Allocation Completed Successfully.")



import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, nowtime


class OMSFulfillmentOrder(Document):

    def on_submit(self):
        self.allocate_inventory()
        self.create_pick_list()

    def allocate_inventory(self):
        if self.allocation_complete:
            return

        for item in self.items:
            qty_needed = item.qty_required

            bins = frappe.db.sql(
                """
                SELECT
                    bl.bin_location,
                    bl.balance_qty,
                    bl.reserved_qty,
                    bl.available_qty
                FROM `tabWMS Bin Ledger` bl
                WHERE bl.item_code = %s
                  AND bl.warehouse = %s
                  AND bl.available_qty > 0
                  AND bl.creation = (
                        SELECT MAX(creation)
                        FROM `tabWMS Bin Ledger`
                        WHERE bin_location = bl.bin_location
                          AND item_code = bl.item_code
                  )
                ORDER BY bl.creation ASC
                """,
                (item.item_code, self.source_warehouse),
                as_dict=True
            )

            if not bins:
                frappe.throw(
                    f"No stock available for item {item.item_code} "
                    f"in warehouse {self.source_warehouse}"
                )

            for row in bins:
                if qty_needed <= 0:
                    break

                qty_to_reserve = min(row.available_qty, qty_needed)

                self._reserve_stock(
                    bin_location=row.bin_location,
                    item_code=item.item_code,
                    balance_qty=row.balance_qty,
                    reserved_qty=row.reserved_qty,
                    qty_to_reserve=qty_to_reserve
                )

                qty_needed -= qty_to_reserve

            if qty_needed > 0:
                frappe.throw(
                    f"Insufficient stock for item {item.item_code}. Short by {qty_needed}"
                )

        self.allocation_complete = 1
        self.status = "Allocated"

    def _reserve_stock(
        self,
        bin_location,
        item_code,
        balance_qty,
        reserved_qty,
        qty_to_reserve
    ):
        frappe.get_doc({
            "doctype": "WMS Bin Ledger",
            "posting_date": nowdate(),
            "posting_time": nowtime(),
            "warehouse": self.source_warehouse,
            "bin_location": bin_location,
            "item_code": item_code,
            "quantity_change": 0,
            "balance_qty": balance_qty,
            "reserved_qty": reserved_qty + qty_to_reserve,
            "available_qty": balance_qty - (reserved_qty + qty_to_reserve),
            "stock_uom": frappe.db.get_value("Item", item_code, "stock_uom"),
            "voucher_type": "OMS Fulfillment Order",
            "voucher_no": self.name,
            "is_reservation": 1
        }).insert(ignore_permissions=True)

    def create_pick_list(self):
        if not self.allocation_complete:
            frappe.throw("Inventory not allocated yet")

        if self.pick_list:
            return

        reservations = frappe.db.sql(
            """
            SELECT
                bin_location,
                item_code,
                batch_no,
                reserved_qty
            FROM `tabWMS Bin Ledger`
            WHERE voucher_type = 'OMS Fulfillment Order'
              AND voucher_no = %s
              AND is_reservation = 1
              AND reserved_qty > 0
            """,
            self.name,
            as_dict=True
        )

        if not reservations:
            frappe.throw("No reserved stock found for Pick List")

        zone = frappe.db.get_value(
            "WMS Bin",
            reservations[0].bin_location,
            "zone"
        )

        if zone and not frappe.db.exists("WMS Zone", zone):
            zone = None

        if not zone:
            zone = frappe.db.get_value(
                "WMS Zone",
                {"is_active": 1},
                "name"
            )

        if not zone:
            frappe.throw(
                "No valid WMS Zone found. Please create a WMS Zone and assign it to bins."
            )

        pick_list = frappe.get_doc({
            "doctype": "WMS Pick List",
            "pick_date": nowdate(),
            "warehouse": self.source_warehouse,
            "zone": zone,
            "picking_strategy": "FEFO",
            "path_optimization": "Serpentine",
            "status": "Released",
            "items": []
        })

        sequence = 1

        for row in reservations:
            stock_uom = frappe.db.get_value(
                "Item",
                row.item_code,
                "stock_uom"
            )

            pick_list.append("items", {
                "sequence": sequence,
                "item_code": row.item_code,
                "bin_location": row.bin_location,
                "batch_no": row.batch_no,
                "warehouse": self.source_warehouse,
                "qty_ordered": row.reserved_qty,
                "uom": stock_uom
            })

            sequence += 1

        pick_list.insert(ignore_permissions=True)
        self.pick_list = pick_list.name
        self.status = "Pick List Created"