# Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
# For license information, please see license.txt

# import frappe
# from frappe.model.document import Document
# from frappe.utils import nowdate


# class WMSOutboundShipment(Document):

#     def validate(self):
#         if not self.items:
#             frappe.throw("Shipment must have at least one item")

#         if not self.from_warehouse:
#             frappe.throw("From Warehouse is required")

#     def on_submit(self):
#         # FORCE shipment into Packing stage
#         self.status = "Packing"

#     # ---------------------------------------------------------
#     # CREATE PACKING LIST (AUTO)
#     # ---------------------------------------------------------
#     @frappe.whitelist()
#     def create_packing_list(self):

#         if self.docstatus != 1:
#             frappe.throw("Shipment must be submitted")

#         if self.status != "Packing":
#             frappe.throw("Packing List can be created only in Packing stage")

#         if self.packing_list:
#             frappe.throw("Packing List already created")

#         packing = frappe.get_doc({
#             "doctype": "WMS Packing List",
#             "company": frappe.defaults.get_global_default("company"),
#             "packing_date": nowdate(),
#             "outbound_shipment": self.name,
#             "warehouse": self.from_warehouse,
#             "packing_station": "PS-01",
#             "status": "Packing",
#             "items": [],
#             "packages": []
#         })

#         has_qty = False

#         for row in self.items:
#             qty_to_pack = row.qty_picked or 0

#             if qty_to_pack <= 0:
#                 continue

#             has_qty = True

#             packing.append("items", {
#                 "item_code": row.item_code,
#                 "qty_to_pack": qty_to_pack,
#                 "qty_packed": qty_to_pack,
#                 "uom": row.uom,
#                 "package_no": 1
#             })

#         if not has_qty:
#             frappe.throw("No picked quantity available to pack")

#         # Default package
#         packing.append("packages", {
#             "package_no": 1,
#             "package_type": "Carton",
#             "lengh_cm": 40,
#             "width_cm": 30,
#             "height_cm": 25,
#             "gross_weight_kg": 12.5
#         })

#         packing.insert(ignore_permissions=True)

#         self.packing_list = packing.name
#         self.save(ignore_permissions=True)

#         return packing.name


import frappe
from frappe.model.document import Document
from frappe.utils import nowdate


class WMSOutboundShipment(Document):

    def validate(self):
        if not self.items:
            frappe.throw("Shipment must have at least one item")

        if not self.from_warehouse:
            frappe.throw("From Warehouse is required")

    def on_submit(self):
        if self.status == "Draft":
            self.status = "Packing"

    @frappe.whitelist()
    def create_packing_list(self):    
 
        if self.docstatus != 1:
            frappe.throw("Shipment must be submitted")

        if self.status != "Packing":
            frappe.throw("Packing List can be created only in Packing stage")

        if self.packing_list:
            frappe.throw("Packing List already created")

        packing = frappe.get_doc({
            "doctype": "WMS Packing List",
            "company": frappe.defaults.get_global_default("company"),
            "packing_date": nowdate(),
            "outbound_shipment": self.name,
            "warehouse": self.from_warehouse,
            "packing_station": "PS-01",
            "status": "Packing",
            "items": [],
            "packages": []
        })

        has_qty = False

        for row in self.items:
            qty_to_pack = row.qty_picked or 0
            if qty_to_pack <= 0:
                continue

            has_qty = True

            packing.append("items", {
                "item_code": row.item_code,
                "qty_to_pack": qty_to_pack,
                "qty_packed": qty_to_pack,
                "uom": row.uom,
                "package_no": 1
            })

        if not has_qty:
            frappe.throw("No picked quantity available to pack")

        packing.append("packages", {
            "package_no": 1,
            "package_type": "Carton",
            "lengh_cm": 40,
            "width_cm": 30,
            "height_cm": 25,
            "gross_weight_kg": 12.5
        })

        packing.insert(ignore_permissions=True)

        self.db_set("packing_list", packing.name)

        return packing.name