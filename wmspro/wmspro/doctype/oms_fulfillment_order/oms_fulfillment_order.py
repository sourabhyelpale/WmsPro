# Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, nowtime


class OMSFulfillmentOrder(Document):

    @frappe.whitelist()
    def create_pick_list_button(self):

        if self.pick_list:
            frappe.throw("Pick List already created")

        allocations = self.allocate_inventory()

        if not allocations:
            frappe.throw("No stock available to create Pick List")

        pick_list = self.create_pick_list_from_allocations(allocations)

        self.db_set("pick_list", pick_list.name)
        self.db_set("status", "Pick List Created")

        return pick_list.name

    # ---------------------------------------------------------
    # STEP 1: Allocate inventory BIN-WISE
    # ---------------------------------------------------------
    def allocate_inventory(self):

        if not self.source_warehouse:
            frappe.throw("Source Warehouse is required")

        allocations = []

        for item in self.items:
            qty_needed = item.qty_required or 0
            qty_allocated = 0

            bins = frappe.db.sql(
                """
                SELECT
                    bin_location,
                    balance_qty,
                    IFNULL(reserved_qty, 0) AS reserved_qty,
                    available_qty
                FROM `tabWMS Bin Ledger`
                WHERE item_code = %s
                  AND warehouse = %s
                  AND available_qty > 0
                  AND is_cancelled = 0
                ORDER BY posting_datetime ASC
                """,
                (item.item_code, self.source_warehouse),
                as_dict=True
            )

            for row in bins:
                if qty_needed <= 0:
                    break

                qty = min(row.available_qty, qty_needed)

                self.create_reservation_entry(
                    row=row,
                    item_code=item.item_code,
                    qty=qty
                )

                allocations.append({
                    "item_code": item.item_code,
                    "bin_location": row.bin_location,
                    "qty": qty
                })

                qty_needed -= qty
                qty_allocated += qty

            item.db_set("qty_allocated", qty_allocated)

        return allocations

    # ---------------------------------------------------------
    # STEP 2: Create reservation entry
    # ---------------------------------------------------------
    def create_reservation_entry(self, row, item_code, qty):

        frappe.get_doc({
            "doctype": "WMS Bin Ledger",
            "posting_date": nowdate(),
            "posting_time": nowtime(),
            "posting_datetime": frappe.utils.now_datetime(),
            "warehouse": self.source_warehouse,
            "bin_location": row.bin_location,
            "item_code": item_code,
            "quantity_change": 0,
            "balance_qty": row.balance_qty,
            "reserved_qty": row.reserved_qty + qty,
            "available_qty": row.available_qty - qty,
            "stock_uom": frappe.db.get_value("Item", item_code, "stock_uom"),
            "voucher_type": "OMS Fulfillment Order",
            "voucher_no": self.name,
            "is_reservation": 1,
            "is_cancelled": 0
        }).insert(ignore_permissions=True)

    # ---------------------------------------------------------
    # STEP 3: CREATE PICK LIST (ONE ROW PER ITEM)
    # ---------------------------------------------------------
    def create_pick_list_from_allocations(self, allocations):

        first_bin = allocations[0]["bin_location"]

        zone = frappe.db.get_value("WMS Bin", first_bin, "zone")
        if not zone:
            zone = frappe.db.get_value("WMS Zone", {"is_active": 1}, "name")

        if not zone:
            frappe.throw("No active WMS Zone found")

        pick_list = frappe.get_doc({
            "doctype": "WMS Pick List",
            "pick_date": nowdate(),
            "warehouse": self.source_warehouse,
            "zone": zone,
            "status": "Released",
            "items": []
        })

        # 🔥 AGGREGATE allocations by item
        item_qty_map = {}
        bin_map = {}

        for row in allocations:
            item_qty_map.setdefault(row["item_code"], 0)
            item_qty_map[row["item_code"]] += row["qty"]

            bin_map.setdefault(row["item_code"], [])
            bin_map[row["item_code"]].append(row["bin_location"])

        seq = 1
        for item_code, total_qty in item_qty_map.items():
            item_name, stock_uom = frappe.db.get_value(
                "Item",
                item_code,
                ["item_name", "stock_uom"]
            )

            pick_list.append("items", {
                "sequence": seq,
                "item_code": item_code,
                "item_name": item_name,
                "warehouse": self.source_warehouse,
                "qty_ordered": total_qty,
                "uom": stock_uom,
                "bin_location": ", ".join(set(bin_map[item_code]))
            })

            seq += 1

        pick_list.insert(ignore_permissions=True)
        return pick_list