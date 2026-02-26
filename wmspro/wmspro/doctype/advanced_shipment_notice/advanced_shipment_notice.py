# Copyright (c) 2026
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now, today


class AdvancedShipmentNotice(Document):

    def on_submit(self):
        """Auto-create WMS Goods Receipt Note when ASN is submitted"""

        # ---- Mandatory Validations ----
        if not self.supplier:
            frappe.throw("Supplier is required to create GRN")

        if not self.company:
            frappe.throw("Company is required to create GRN")

        if not self.warehouse:
            frappe.throw("Warehouse is required to create GRN")

        if not self.advanced_shipment_notice_details:
            frappe.throw("No items found in ASN to create GRN")

        try:
            # ---- Create GRN Header ----
            grn = frappe.get_doc({
                "doctype": "WMS Goods Receipt Note",
                "asn_reference": self.name,
                "purchace_order": self.purchase_order,
                "supplier": self.supplier,
                "supplier_name": self.supplier_name,
                "company": self.company,
                "warehouse": self.warehouse,
                "posting_date": today(),
                "posting_time": now(),
                "receipt_type": "Standard"
            })

            # ---- Append Items ----
            for asn_item in self.advanced_shipment_notice_details:

                qty = asn_item.expected_qty or asn_item.ordered_qty

                if not qty or qty <= 0:
                    frappe.throw(f"Quantity must be greater than zero for Item {asn_item.item_code}")

                grn.append("wms_grn_item", {
                    "item_code": asn_item.item_code,
                    "item_name": asn_item.item_name,
                    "description": asn_item.description,

                    # 🔥 Mandatory fields for GRN
                    "batch_no": asn_item.batch_no,
                    "expiry_date": asn_item.expiry_date,
                    "mrp": asn_item.mrp,
                    "qty_expected": qty,

                    # Required for stock
                    "qty": qty,
                    "conversion_factor": 1,
                    "stock_uom": asn_item.stock_uom,
                    "warehouse": self.warehouse
                })

            # ---- Insert GRN ----
            grn.insert(ignore_permissions=True)

            # ---- Success Message ----
            frappe.msgprint(
                msg=f"WMS Goods Receipt Note <b>{grn.name}</b> created successfully.",
                title="GRN Created",
                indicator="green"
            )

        except Exception as e:
            # This will STOP ASN submission and rollback everything
            frappe.log_error(
                message=frappe.get_traceback(),
                title=f"GRN Creation Failed for ASN {self.name}"
            )
            frappe.throw(f"Failed to create GRN: {str(e)}")