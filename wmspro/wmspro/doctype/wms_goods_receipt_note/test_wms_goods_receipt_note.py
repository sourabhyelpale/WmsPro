# Copyright (c) 2026, Quantbit Technologies Private Limited  and Contributors
# See license.txt

import frappe
from frappe.utils import today,now
from frappe.tests.utils import FrappeTestCase


class TestWMSGoodsReceiptNote(FrappeTestCase):
	def before_save(self):
		items = self.wms_grn_item
		doc = frappe.new_doc("GRN")
		doc.posting_date = today()
		doc.posting_time = now()
		doc.supplier = self.supplier or ""
		doc.set_warehouse = self.warehouse or ""
		for item in items:
			doc.item_code = item.item_code
			doc.item_name = item.item_name