# Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from wmspro.wmspro.bin_ledger import create_bin_ledger_entry


class WMSPutawayTask(Document):
    def on_update(self):

        if self.status != "Completed" or self.completed_at:
            return

        self.completed_at = frappe.utils.now()

        # Remove from staging
        create_bin_ledger_entry(
            bin_location=self.from_bin,
            item_code=self.item_code,
            qty_change=-float(self.qty),
            batch_no=self.batch_no,
            voucher_type="WMS Putaway Task",
            voucher_no=self.name
        )

        # Add to storage
        create_bin_ledger_entry(
            bin_location=self.actual_bin or self.suggested_bin,
            item_code=self.item_code,
            qty_change=float(self.qty),
            batch_no=self.batch_no,
            voucher_type="WMS Putaway Task",
            voucher_no=self.name
        )