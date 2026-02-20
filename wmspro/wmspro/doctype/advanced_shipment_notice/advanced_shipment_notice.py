# Copyright (c) 2026
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AdvancedShipmentNotice(Document):
	
	def on_submit(self):
		"""Auto-create WMS Goods Receipt Note when ASN is submitted"""
		try:
			frappe.msgprint(f"DEBUG: on_submit method triggered for ASN: {self.name}")
			frappe.log_error(f"Starting GRN creation for ASN: {self.name}", "ASN Submit Debug")
			
			# Check if required fields exist
			frappe.msgprint(f"DEBUG: Supplier: {self.supplier}")
			frappe.msgprint(f"DEBUG: Company: {self.company}")
			frappe.msgprint(f"DEBUG: Warehouse: {self.warehouse}")
			frappe.msgprint(f"DEBUG: Purchase Order: {self.purchase_order}")
			
			if not self.supplier:
				frappe.throw("Supplier is required to create GRN")
			if not self.company:
				frappe.throw("Company is required to create GRN")
			
			frappe.msgprint("DEBUG: Creating GRN document...")
			try:
				# Create WMS Goods Receipt Note
				grn = frappe.get_doc({
					"doctype": "WMS Goods Receipt Note",
					"asn_reference": self.name,
					"purchace_order": self.purchase_order,
					"supplier": self.supplier,
					"supplier_name": self.supplier_name,
					"company": self.company,
					"warehouse": self.warehouse if self.warehouse else None,  # Handle None warehouse
					"posting_date": frappe.utils.today(),
					"posting_time": frappe.utils.now(),
					"receipt_type": "Standard",
					"status": "Draft"  # Create in Draft state
				})
				
				frappe.msgprint("DEBUG: GRN document created successfully")
			except Exception as doc_error:
				frappe.msgprint(f"DEBUG: Error creating GRN document: {str(doc_error)}")
				frappe.log_error(f"Error creating GRN document: {str(doc_error)}", "ASN Submit Error")
				raise
			frappe.log_error(f"GRN doc created with basic fields", "ASN Submit Debug")
			
			# Insert items from ASN to GRN
			frappe.msgprint(f"DEBUG: Checking ASN items...")
			if not self.advanced_shipment_notice_details:
				frappe.throw("No items found in ASN to create GRN")
			
			frappe.msgprint(f"DEBUG: Found {len(self.advanced_shipment_notice_details)} items in ASN")
			
			for i, asn_item in enumerate(self.advanced_shipment_notice_details):
				frappe.msgprint(f"DEBUG: Processing item {i+1}: {asn_item.item_code}")
				grn.append("wms_grn_item", {
					"item_code": asn_item.item_code,
					"item_name": asn_item.item_name,
					"description": asn_item.description,
					"ordered_qty": asn_item.ordered_qty,
					"expected_qty": asn_item.ordered_qty,
					"uom": asn_item.uom
				})
				frappe.msgprint(f"DEBUG: Item {i+1} appended to GRN")
			
			frappe.msgprint(f"DEBUG: All {len(self.advanced_shipment_notice_details)} items appended to GRN")
			frappe.log_error(f"Items added to GRN: {len(self.advanced_shipment_notice_details)}", "ASN Submit Debug")
			
			# Insert and save GRN
			try:
				grn.insert(ignore_permissions=True)
				grn.save()
				
				frappe.log_error(f"GRN created successfully: {grn.name}", "ASN Submit Debug")
				
				frappe.msgprint({
					"title": "WMS Goods Receipt Note Created",
					"message": f"WMS Goods Receipt Note {grn.name} has been created automatically from ASN {self.name}",
					"indicator": "green"
				})
				
			except Exception as save_error:
				frappe.log_error(f"Error saving GRN: {str(save_error)}", "ASN Submit Error")
				frappe.msgprint({
					"title": "Error Creating GRN",
					"message": f"Failed to save WMS Goods Receipt Note: {str(save_error)}",
					"indicator": "red"
				})
			
		except Exception as e:
			frappe.log_error(f"Error creating GRN for ASN {self.name}: {str(e)}", "ASN Submit Error")
			frappe.msgprint({
				"title": "Error Creating GRN",
				"message": f"Failed to create WMS Goods Receipt Note: {str(e)}",
				"indicator": "red"
			})

   