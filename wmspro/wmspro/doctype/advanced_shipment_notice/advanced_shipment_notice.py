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
            for row in self.advanced_shipment_notice_details:

                qty = (
                    row.received_qty
                    or row.shipped_qty
                    or row.expected_qty
                    or row.ordered_qty
                )

                if not qty or qty <= 0:
                    frappe.throw(f"Quantity must be greater than zero for Item {row.item_code}")

                # Debug: Check item name values
                frappe.log_error(f"DEBUG ASN: row.item_code={row.item_code}, row.item_name={getattr(row, 'item_name', 'NOT_SET')}, row.item_name from DB={frappe.db.get_value('Item', row.item_code, 'item_name')}")

                # Get item_code and item_name from Purchase Order item table
                po_item = frappe.db.get_value("Purchase Order Item", 
                    {"parent": self.purchase_order, "item_code": row.item_code}, 
                    ["item_code", "item_name"], as_dict=True)

                item_code = po_item.item_code if po_item else row.item_code
                item_name = po_item.item_name if po_item else getattr(row, 'item_name', '')  # Use row.item_name if available

                # Get MRP from ASN row, fallback to rate if MRP is null or zero
                mrp = getattr(row, 'mrp', None) or row.rate
                if not mrp or mrp <= 0:
                    mrp = row.rate
                if not mrp or mrp <= 0:
                    mrp = 1  # Default fallback to ensure MRP > 0

                # Get rate and amount from ASN row
                rate = getattr(row, 'rate', 0)
                amount = rate * qty if rate else 0
                
                # Debug: Check rate and amount values
                frappe.log_error(f"DEBUG ASN Rate/Amount: item_code={item_code}, rate={rate}, amount={amount}, row.rate={getattr(row, 'rate', 'NOT_SET')}")

                # Handle batch number - create if doesn't exist
                batch_no = row.batch_no
                if batch_no:
                    # Check if batch exists
                    batch_exists = frappe.db.exists("Batch", batch_no)
                    if not batch_exists:
                        # Create batch if it doesn't exist
                        try:
                            batch_doc = frappe.new_doc("Batch")
                            batch_doc.batch_id = batch_no
                            batch_doc.item = item_code
                            batch_doc.save(ignore_permissions=True)
                            frappe.msgprint(f"Created new Batch: {batch_no}")
                        except Exception as batch_error:
                            frappe.log_error(f"Failed to create batch {batch_no}: {str(batch_error)}")
                            batch_no = None  # Set to None if batch creation fails

                grn.append("wms_grn_item", {
                    "item_code": item_code,
                    "item_name": item_name,
                    "description": row.description,

                    # 🔥 Mandatory fields for GRN
                    "batch_no": batch_no,  # Use validated batch_no (None if doesn't exist)
                    "expiry_date": row.expiry_date,
                    "mrp": mrp,
                    "rate": rate,  # Add rate from ASN
                    "amount": amount,  # Add calculated amount
                    "qty_expected": qty,

                    # Required for stock
                    "qty": qty,
                    "conversion_factor": 1,
                    "stock_uom": row.stock_uom,  # Use row.stock_uom instead of asn_item.stock_uom
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