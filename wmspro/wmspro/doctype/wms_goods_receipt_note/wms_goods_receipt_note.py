# Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import today,now
from frappe.model.document import Document


class WMSGoodsReceiptNote(Document):
	def before_save(self):
		doc = frappe.new_doc("Purchase Receipt")
		doc.company = self.company
		doc.posting_date = today()
		doc.posting_time = now()
		doc.supplier = self.supplier or ""
		doc.set_warehouse = self.warehouse or ""
		doc.custom_department = "Stores"
		doc.custom_invoice_no = f"AUTO-{frappe.utils.random_string(6)}"
		frappe.msgprint("GRN Created")
		for item in self.wms_grn_item:
			doc.append("items", {
				"barcode": item.barcode_scan,
				"item_code": item.item_code,
				"item_name": item.item_name,
				"custom_user_batch_no": item.batch_no,
				"custom_expiry_date": item.expiry_date,
				"conversion_factor": item.conversion_factor,
				"custom_order_qty": item.qty_expected,
				"qty": item.qty_accepted,
				"rejected_qty": item.qty_rejected,
				"stock_uom": item.stock_uom,
				"received_stock_qty": item.stock_qty_received,
				"stock_qty": item.stock_qty_accepted,
				"amount": item.amount,
				"base_rate": item.rate,
			})

		doc.insert(ignore_permissions=True)
		frappe.db.commit()

		frappe.msgprint(f"Purchase Receipt {doc.name} Created")
