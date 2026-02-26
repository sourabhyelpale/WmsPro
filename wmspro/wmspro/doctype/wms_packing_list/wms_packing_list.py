# Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
# For license information, please see license.txt

# import frappe
# from frappe.model.document import Document
# from frappe.utils import now_datetime
# import uuid


# class WMSPackingList(Document):

#     def before_insert(self):
#         self.packed_by = frappe.session.user
#         self.packing_date = frappe.utils.nowdate()

#         if self.outbound_shipment:
#             shipment = frappe.get_doc("WMS Outbound Shipment", self.outbound_shipment)

#             # Auto warehouse
#             if not self.warehouse:
#                 self.warehouse = shipment.from_warehouse

#             # Auto packing station (default)
#             if not self.packing_station:
#                 self.packing_station = "PS-01"

#             # Auto pick list if exists
#             if not self.pick_list and hasattr(shipment, "pick_list"):
#                 self.pick_list = shipment.pick_list


#     def validate(self):

#         if not self.outbound_shipment:
#             frappe.throw("Outbound Shipment is required")

#         if not self.items:
#             frappe.throw("Packing List Items are required")

#         if not self.packages:
#             self.append("packages", {
#                 "package_no": 1,
#                 "package_type": "Carton"
#             })

#         # Ensure each item has package_no
#         for row in self.items:
#             if not row.package_no:
#                 row.package_no = 1


#     def on_submit(self):

#         total_weight = 0
#         total_volume = 0

#         for pkg in self.packages:

#             # Handle typo-safe length field
#             length = (
#                 getattr(pkg, "length_cm", None)
#                 or getattr(pkg, "lengh_cm", 0)
#             ) or 0

#             width = pkg.width_cm or 0
#             height = pkg.height_cm or 0

#             volume_cbm = (length * width * height) / 1_000_000
#             pkg.volume_cbm = volume_cbm

#             total_volume += volume_cbm
#             total_weight += pkg.gross_weight_kg or 0

#             if not pkg.sscc_barcode:
#                 pkg.sscc_barcode = self._generate_sscc()

#         self.total_weight_kg = total_weight
#         self.total_volume_cbm = total_volume

#         self._print_shipping_labels()
#         self._update_outbound_shipment(total_weight, total_volume)


#     def _generate_sscc(self):
#         raw = uuid.uuid4().int
#         return f"(00){str(raw)[:18]}"


#     def _print_shipping_labels(self):
#         for pkg in self.packages:
#             frappe.log_error(
#                 title="ZPL PRINT (Stub)",
#                 message=f"SSCC {pkg.sscc_barcode} sent to label printer"
#             )


#     def _update_outbound_shipment(self, weight, volume):

#         shipment = frappe.get_doc(
#             "WMS Outbound Shipment",
#             self.outbound_shipment
#         )

#         shipment.total_weight_kg = weight
#         shipment.total_volume_cbm = volume

#         shipment.status = "Packed"

#         shipment.packing_list = self.name

#         shipment.save(ignore_permissions=True)




import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime
import uuid


class WMSPackingList(Document):

    def before_insert(self):
        self.packed_at = now_datetime()
        self.packed_by = frappe.session.user

    def validate(self):

        if not self.outbound_shipment:
            frappe.throw("Outbound Shipment is required")

        if not self.items:
            frappe.throw("Packing List Items are required")

        if not self.packages:
            self.append("packages", {
                "package_no": 1,
                "package_type": "Carton"
            })

        for row in self.items:
            if not row.package_no:
                row.package_no = 1

    def on_submit(self):

        total_weight = 0
        total_volume = 0

        for pkg in self.packages:
            length = getattr(pkg, "lengh_cm", 0) or 0
            width = pkg.width_cm or 0
            height = pkg.height_cm or 0

            volume_cbm = (length * width * height) / 1_000_000
            pkg.volume_cbm = volume_cbm

            total_volume += volume_cbm
            total_weight += pkg.gross_weight_kg or 0

            if not pkg.sscc_barcode:
                pkg.sscc_barcode = self._generate_sscc()

        self.total_weight_kg = total_weight
        self.total_volume_cbm = total_volume

        self._print_shipping_labels()
        self._update_outbound_shipment(total_weight, total_volume)

    def _generate_sscc(self):
        raw = uuid.uuid4().int
        return f"(00){str(raw)[:18]}"

    def _print_shipping_labels(self):
        for pkg in self.packages:
            frappe.log_error(
                title="ZPL Print Stub",
                message=f"SSCC {pkg.sscc_barcode} sent to printer"
            )

    def _update_outbound_shipment(self, weight, volume):

        shipment = frappe.get_doc("WMS Outbound Shipment", self.outbound_shipment)

        shipment.db_set("total_weight_kg", weight)
        shipment.db_set("total_volume_cbm", volume)
        shipment.db_set("status", "Packed")