# Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, nowdate, nowtime


class WMSPickList(Document):

    @frappe.whitelist()
    def assign_to_picker(self, picker_user):

        if self.status not in ["Released", "Draft"]:
            frappe.throw("Pick List cannot be assigned in current status")

        if not picker_user:
            frappe.throw("Picker user is required")

        self.assigned_to = picker_user
        self.status = "Assigned"
        self.save(ignore_permissions=True)

        frappe.get_doc({
            "doctype": "ToDo",
            "owner": picker_user,
            "assigned_by": frappe.session.user,
            "reference_type": "WMS Pick List",
            "reference_name": self.name,
            "description": f"Pick List {self.name} assigned for picking",
            "status": "Open",
            "priority": "High"
        }).insert(ignore_permissions=True)

        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": "Pick List Assigned",
            "email_content": f"You have been assigned Pick List {self.name} for picking.",
            "for_user": picker_user,
            "document_type": "WMS Pick List",
            "document_name": self.name,
            "type": "Alert"
        }).insert(ignore_permissions=True)

        frappe.publish_realtime(
            event="msgprint",
            message=f"You have been assigned Pick List {self.name}",
            user=picker_user
        )

        return True

    @frappe.whitelist()
    def start_picking(self):

        if self.status != "Assigned":
            frappe.throw("Pick List must be Assigned to start picking")

        self.status = "Picking"
        self.started_at = now_datetime()
        self.save(ignore_permissions=True)

        return True

    @frappe.whitelist()
    def complete_picking(self):

        if self.status != "Picking":
            frappe.throw("Pick List is not in Picking state")

        total_picked = 0
        total_short = 0

        for row in self.items:
            ordered = row.qty_ordered or 0
            picked = row.qty_picked or 0

            if picked > ordered:
                frappe.throw(f"Picked qty cannot exceed ordered qty for item {row.item_code}")

            row.qty_short = ordered - picked
            total_picked += picked
            total_short += row.qty_short
            row.warehouse = self._get_leaf_warehouse(row.bin_location)

        self.stock_entry = self._create_stock_entry() 
        
        for row in self.items:
            self._apply_stock_movement(row)
            self._update_bin_occupancy(row)

        self.total_qty_picked = total_picked
        self.total_short_qty = total_short
        self.pick_completion_pct = (
            (total_picked / (total_picked + total_short)) * 100
            if (total_picked + total_short) > 0 else 100
        )

        self.outbound_shipment = self._create_outbound_shipment()
        self._update_fulfillment_status(total_picked, total_short)

        self.status = "Completed"
        self.completed_at = now_datetime()
        self.save(ignore_permissions=True)

        return True

    def _get_leaf_warehouse(self, bin_location):

        warehouse = frappe.db.get_value("WMS Bin", bin_location, "warehouse")

        if not warehouse:
            frappe.throw(f"Warehouse not mapped for bin {bin_location}")

        return warehouse

    def _create_stock_entry(self):

        se = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Issue",
            "posting_date": nowdate(),
            "items": []
        })

        has_items = False

        for row in self.items:
            if row.qty_picked and row.qty_picked > 0:
                se.append("items", {
                    "item_code": row.item_code,
                    "qty": row.qty_picked,
                    "s_warehouse": row.warehouse,
                    "uom": row.uom,
                    "batch_no": row.batch_no
                })
                has_items = True

        if not has_items:
            frappe.throw("No picked quantity found to create Stock Entry")

        se.insert(ignore_permissions=True)
        se.submit()

        return se.name

    def _apply_stock_movement(self, row):

        if not row.qty_picked or row.qty_picked <= 0:
            return

        ledger = frappe.db.sql("""
            SELECT *
            FROM `tabWMS Bin Ledger`
            WHERE bin_location = %s
              AND item_code = %s
            ORDER BY creation DESC
            LIMIT 1
        """, (row.bin_location, row.item_code), as_dict=True)

        if not ledger:
            frappe.throw(f"No bin ledger found for item {row.item_code}")

        ledger = ledger[0]

        new_balance = ledger.balance_qty - row.qty_picked
        new_reserved = max((ledger.reserved_qty or 0) - row.qty_picked, 0)
        new_available = new_balance - new_reserved

        frappe.get_doc({
            "doctype": "WMS Bin Ledger",
            "posting_date": nowdate(),
            "posting_time": nowtime(),
            "warehouse": row.warehouse,
            "bin_location": row.bin_location,
            "item_code": row.item_code,
            "quantity_change": -row.qty_picked,
            "balance_qty": new_balance,
            "reserved_qty": new_reserved,
            "available_qty": new_available,
            "stock_uom": row.uom,
            "voucher_type": "WMS Pick List",
            "voucher_no": self.name,
            "is_reservation": 0
        }).insert(ignore_permissions=True)

    def _update_bin_occupancy(self, row):

        bin_doc = frappe.get_doc("WMS Bin", row.bin_location)

        current = bin_doc.current_occupancy or 0
        new_value = current - row.qty_picked

        bin_doc.current_occupancy = max(new_value, 0)
        bin_doc.save(ignore_permissions=True)

    def _create_outbound_shipment(self):

        shipment = frappe.get_doc({
            "doctype": "WMS Outbound Shipment",
            "shipmenr_date": nowdate(),
            "required_delivery_date": nowdate(),
            "from_warehouse": self.warehouse,
            "pick_list": self.name,
            "status": "Packing",
            "items": []
        })

        for row in self.items:
            if row.qty_picked and row.qty_picked > 0:
                shipment.append("items", {
                    "item_code": row.item_code,
                    "qty_ordered": row.qty_picked,
                    "qty": row.qty_picked,
                    "warehouse": row.warehouse,
                    "uom": row.uom,
                    "batch_no": row.batch_no
                })

        if not shipment.items:
            frappe.throw("No items to ship")

        shipment.insert(ignore_permissions=True)
        return shipment.name

    def _update_fulfillment_status(self, total_picked, total_short):

        fulfillment = frappe.db.get_value(
            "OMS Fulfillment Order",
            {"pick_list": self.name},
            "name"
        )

        if not fulfillment:
            return

        doc = frappe.get_doc("OMS Fulfillment Order", fulfillment)

        doc.total_qty_picked = total_picked
        doc.total_qty_short = total_short

        if total_short > 0:
            doc.fulfillment_result = "Partially Fulfilled"
        else:
            doc.fulfillment_result = "Fully Fulfilled"

        doc.status = "Packed"
        doc.save(ignore_permissions=True)



#//////////////////////////////////////  new  //////////////////////////////////////////////


# import frappe
# from frappe.model.document import Document
# from frappe.utils import now_datetime, nowdate, nowtime


# class WMSPickList(Document):

#     # =====================================================
#     # ASSIGN PICKER
#     # =====================================================
#     @frappe.whitelist()
#     def assign_to_picker(self, picker_user):

#         if self.status not in ["Released", "Draft"]:
#             frappe.throw("Pick List cannot be assigned in current status")

#         if not picker_user:
#             frappe.throw("Picker user is required")

#         self.assigned_to = picker_user
#         self.status = "Assigned"
#         self.save(ignore_permissions=True)

#         return True


#     # =====================================================
#     # START PICKING
#     # =====================================================
#     @frappe.whitelist()
#     def start_picking(self):

#         if self.status != "Assigned":
#             frappe.throw("Pick List must be Assigned to start picking")

#         self.status = "Picking"
#         self.started_at = now_datetime()
#         self.save(ignore_permissions=True)

#         return True


#     # =====================================================
#     # COMPLETE PICKING
#     # =====================================================
#     @frappe.whitelist()
#     def complete_picking(self):

#         if self.status != "Picking":
#             frappe.throw("Pick List is not in Picking state")

#         total_picked = 0
#         total_short = 0

#         for row in self.items:

#             ordered = row.qty_ordered or 0
#             picked = row.qty_picked or 0

#             if picked > ordered:
#                 frappe.throw(
#                     f"Picked qty cannot exceed ordered qty for item {row.item_code}"
#                 )

#             row.qty_short = ordered - picked
#             total_picked += picked
#             total_short += row.qty_short

#             row.warehouse = self._get_leaf_warehouse(row.bin_location)

#         # 1️⃣ Create Stock Entry
#         self.stock_entry = self._create_stock_entry()

#         # 2️⃣ Apply Bin Movement
#         for row in self.items:
#             self._apply_stock_movement(row)
#             self._update_bin_occupancy(row)

#         # 3️⃣ Completion %
#         self.total_qty_picked = total_picked
#         self.total_short_qty = total_short

#         self.pick_completion_pct = (
#             (total_picked / (total_picked + total_short)) * 100
#             if (total_picked + total_short) > 0 else 100
#         )

#         # 4️⃣ Create Outbound Shipment
#         outbound_name = self._create_outbound_shipment()
#         self.outbound_shipment = outbound_name

#         # 5️⃣ Update Fulfillment Order
#         self._update_fulfillment_status(
#             total_picked,
#             total_short,
#             outbound_name
#         )

#         self.status = "Completed"
#         self.completed_at = now_datetime()
#         self.save(ignore_permissions=True)

#         frappe.msgprint(f"Outbound Shipment {outbound_name} created successfully")

#         return True


#     # =====================================================
#     # GET WAREHOUSE FROM BIN
#     # =====================================================
#     def _get_leaf_warehouse(self, bin_location):

#         warehouse = frappe.db.get_value(
#             "WMS Bin",
#             bin_location,
#             "warehouse"
#         )

#         if not warehouse:
#             frappe.throw(f"Warehouse not mapped for bin {bin_location}")

#         return warehouse


#     # =====================================================
#     # CREATE STOCK ENTRY
#     # =====================================================
#     def _create_stock_entry(self):

#         se = frappe.get_doc({
#             "doctype": "Stock Entry",
#             "stock_entry_type": "Material Issue",
#             "posting_date": nowdate(),
#             "items": []
#         })

#         has_items = False

#         for row in self.items:
#             if row.qty_picked and row.qty_picked > 0:
#                 se.append("items", {
#                     "item_code": row.item_code,
#                     "qty": row.qty_picked,
#                     "s_warehouse": row.warehouse,
#                     "uom": row.uom,
#                     "batch_no": row.batch_no
#                 })
#                 has_items = True

#         if not has_items:
#             frappe.throw("No picked quantity found")

#         se.insert(ignore_permissions=True)
#         se.submit()

#         return se.name


#     # =====================================================
#     # BIN LEDGER UPDATE
#     # =====================================================
#     def _apply_stock_movement(self, row):

#         if not row.qty_picked or row.qty_picked <= 0:
#             return

#         ledger = frappe.db.sql("""
#             SELECT *
#             FROM `tabWMS Bin Ledger`
#             WHERE bin_location = %s
#               AND item_code = %s
#             ORDER BY creation DESC
#             LIMIT 1
#         """, (row.bin_location, row.item_code), as_dict=True)

#         if not ledger:
#             frappe.throw(f"No bin ledger found for item {row.item_code}")

#         ledger = ledger[0]

#         new_balance = ledger.balance_qty - row.qty_picked
#         new_reserved = max((ledger.reserved_qty or 0) - row.qty_picked, 0)
#         new_available = new_balance - new_reserved

#         frappe.get_doc({
#             "doctype": "WMS Bin Ledger",
#             "posting_date": nowdate(),
#             "posting_time": nowtime(),
#             "warehouse": row.warehouse,
#             "bin_location": row.bin_location,
#             "item_code": row.item_code,
#             "quantity_change": -row.qty_picked,
#             "balance_qty": new_balance,
#             "reserved_qty": new_reserved,
#             "available_qty": new_available,
#             "stock_uom": row.uom,
#             "voucher_type": "WMS Pick List",
#             "voucher_no": self.name,
#             "is_reservation": 0
#         }).insert(ignore_permissions=True)


#     # =====================================================
#     # UPDATE BIN OCCUPANCY
#     # =====================================================
#     def _update_bin_occupancy(self, row):

#         bin_doc = frappe.get_doc("WMS Bin", row.bin_location)

#         current = bin_doc.current_occupancy or 0
#         new_value = current - (row.qty_picked or 0)

#         bin_doc.current_occupancy = max(new_value, 0)
#         bin_doc.save(ignore_permissions=True)


#     # =====================================================
#     # CREATE OUTBOUND SHIPMENT
#     # =====================================================
#     def _create_outbound_shipment(self):

#         shipment = frappe.get_doc({
#             "doctype": "WMS Outbound Shipment",

#             # ⚠️ YOUR ACTUAL FIELDNAME (from error)
#             "shipmenr_date": nowdate(),

#             "required_delivery_date": nowdate(),
#             "from_warehouse": self.warehouse,
#             "pick_list": self.name,
#             "status": "Packing",
#             "items": []
#         })

#         for row in self.items:
#             if row.qty_picked and row.qty_picked > 0:
#                 shipment.append("items", {
#                     "item_code": row.item_code,
#                     "qty_ordered": row.qty_picked,
#                     "qty": row.qty_picked,
#                     "warehouse": row.warehouse,
#                     "uom": row.uom,
#                     "batch_no": row.batch_no
#                 })

#         if not shipment.items:
#             frappe.throw("No items to ship")

#         shipment.insert(ignore_permissions=True)

#         return shipment.name


#     # =====================================================
#     # UPDATE FULFILLMENT ORDER
#     # =====================================================
#     def _update_fulfillment_status(
#         self,
#         total_picked,
#         total_short,
#         outbound_name
#     ):

#         fulfillment = frappe.db.get_value(
#             "OMS Fulfillment Order",
#             {"pick_list": self.name},
#             "name"
#         )

#         if not fulfillment:
#             return

#         doc = frappe.get_doc("OMS Fulfillment Order", fulfillment)

#         doc.total_qty_picked = total_picked
#         doc.total_qty_short = total_short
#         doc.outbound_shipment = outbound_name

#         if total_short > 0:
#             doc.fulfillment_result = "Partially Fulfilled"
#         else:
#             doc.fulfillment_result = "Fully Fulfilled"

#         doc.status = "Packed"
#         doc.save(ignore_permissions=True)
