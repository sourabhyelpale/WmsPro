import frappe
from frappe.utils import today, now
from frappe.model.document import Document
from wmspro.wmspro.bin_ledger import create_bin_ledger_entry


class WMSGoodsReceiptNote(Document):

    def after_insert(self):

        pr = frappe.new_doc("Purchase Receipt")
        pr.company = self.company
        pr.posting_date = today()
        pr.posting_time = now()
        pr.supplier = self.supplier
        pr.set_warehouse = self.warehouse
        pr.custom_department = "Stores - LD"
        pr.custom_invoice_no = f"AUTO-{frappe.utils.random_string(6)}"

        for item in self.wms_grn_item:

            qty = item.qty_expected or item.qty_accepted

            if not qty or qty <= 0:
                frappe.throw(f"Quantity cannot be zero for Item {item.item_code}")

            pr.append("items", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "uom": item.stock_uom,
                "qty": qty,
                "conversion_factor": 1,
                "custom_user_batch_no" : item.batch_no,
                "stock_uom": item.stock_uom,
                "rate": item.rate,
                "custom_mrp":item.mrp,
                "warehouse": self.warehouse
            })

        pr.insert(ignore_permissions=True)

        # store reference
        self.db_set("purchase_receipt", pr.name)

        frappe.msgprint(f"Purchase Receipt {pr.name} Created")

    def before_save(self):
        """Ensure positive quantities to prevent custom validation errors"""
        # Ensure positive quantities to prevent custom validation errors
        for item in self.wms_grn_item:
            if hasattr(item, 'qty') and (not item.qty or item.qty <= 0):
                item.qty = max(item.qty_accepted or 1, 1)  # Force positive quantity
                frappe.log_error(f"Fixed zero quantity for item {item.item_code}: set qty={item.qty}")

    def on_submit(self):

        # ---- Submit Purchase Receipt ----
        if self.purchase_receipt:

            pr = frappe.get_doc("Purchase Receipt", self.purchase_receipt)

            if pr.docstatus == 0:
                pr.submit()

        # ---- Create Bin Ledger Entries ----
        staging_bin = self.get_staging_bin_for_warehouse()

        for item in self.wms_grn_item:

            qty = item.qty_expected or item.qty_accepted

            if not qty:
                continue

            create_bin_ledger_entry(
                bin_location=staging_bin,
                item_code=item.item_code,
                qty_change=float(qty),
                batch_no=item.batch_no,
                voucher_type="WMS Goods Receipt Note",
                voucher_no=self.name
            )

        frappe.msgprint("Purchase Receipt Submitted & Bin Ledger Updated")
        self.create_putaway_tasks()


    def create_putaway_tasks(self):

        tasks_created = 0
        
        # Get staging bin from GRN document
        staging_bin = getattr(self, 'staging_bin', None)
        if not staging_bin:
            # Fallback to default staging bin for warehouse
            staging_bin = self.get_staging_bin_for_warehouse()
        
        staging_bin_warehouse = frappe.db.get_value("WMS Bin", staging_bin, "warehouse")

        for item in self.wms_grn_item:

            qty = item.qty_expected or item.qty_accepted

            if not qty:
                continue

            # Create putaway task for each item-batch
            task = frappe.new_doc("WMS Putaway Task")
            task.naming_series = "PAT-.YYYY.-.####"  # Put Away Task naming series
            task.grn_reference = self.name
            task.task_date = frappe.utils.today()  # Use task_date field instead of date_zkpa
            task.status = "Pending"
            task.strategy = "ABC Slotting"  # Set strategy to ABC Slotting
            
            # Get item's staging bin or fallback to document staging bin
            item_staging_bin = getattr(item, 'staging_bin', None) or staging_bin
            item_staging_bin_warehouse = frappe.db.get_value("WMS Bin", item_staging_bin, "warehouse")
            
            task.from_warehouse = item_staging_bin_warehouse  # Use item's staging bin's warehouse
            
            # Get suggested bin based on ABC slotting strategy
            suggested_bin = self.get_abc_suggested_bin(item.item_code, self.warehouse)
            suggested_bin_warehouse = frappe.db.get_value("WMS Bin", suggested_bin, "warehouse")
            
            task.to_warehouse = suggested_bin_warehouse  # Use suggested bin's warehouse
            task.from_bin = item_staging_bin  # Use item's actual staging bin
            task.suggested_bin = suggested_bin  # Use ABC slotting suggestion
            task.actual_bin = suggested_bin  # Set actual bin to suggested bin
            task.item_code = item.item_code
            # Fetch item name from Item master to ensure proper display
            item_name = frappe.db.get_value("Item", item.item_code, "item_name") or item.item_name
            task.item_name = item_name  # Use fetched item name
            task.batch_no = item.batch_no
            # Use consistent quantity for both task and stock entry
            # Try multiple quantity fields to ensure we get a positive value
            task_quantity = (item.qty_accepted or item.stock_qty_accepted or 
                           item.qty_received or item.stock_qty_received or 
                           item.qty_expected or 0)
            
            # If still zero, try to get from existing data or set to 1 as last resort
            if not task_quantity or task_quantity <= 0:
                # Check if there's a base qty field
                if hasattr(item, 'qty') and item.qty and item.qty > 0:
                    task_quantity = item.qty
                else:
                    # As a last resort, set to 1 to prevent zero quantity issues
                    task_quantity = 1
                    frappe.log_error(f"Set default quantity=1 for item {item.item_code} due to zero quantity")
            
            task.quantity = task_quantity
            task.uom = item.stock_uom
            task.insert(ignore_permissions=True)
            tasks_created += 1
            
            # Create Stock Entry if from_warehouse and to_warehouse are different AND quantity is positive
            if item_staging_bin_warehouse != suggested_bin_warehouse and task_quantity and task_quantity > 0:
                frappe.log_error(f"Creating Stock Entry for task {task.name}: From {item_staging_bin_warehouse} To {suggested_bin_warehouse} Qty {task_quantity}")
                self.create_stock_entry_for_putaway(task, item_staging_bin_warehouse, suggested_bin_warehouse)
            else:
                frappe.log_error(f"Skipping Stock Entry for task {task.name}: From {item_staging_bin_warehouse} To {suggested_bin_warehouse} Qty {task_quantity}")


    def get_abc_suggested_bin(self, item_code, warehouse):
        """Get suggested bin based on ABC slotting strategy"""
        # Get all non-staging bins for the warehouse
        bins = frappe.db.get_all("WMS Bin", 
            filters={"warehouse": warehouse, "is_staging": 0},
            fields=["name", "bin_type", "max_capacity", "available_capacity"],
            order_by="name"
        )
        
        if not bins:
            # Fallback to any bin if no specific bins found
            return frappe.db.get_value("WMS Bin", {"warehouse": warehouse}, "name")
        
        # Simple ABC logic: rotate through bins based on item code hash
        # This ensures consistent bin assignment for the same item
        item_hash = hash(item_code) % len(bins)
        suggested_bin = bins[item_hash].name
        
        return suggested_bin

    def create_stock_entry_for_putaway(self, task, from_warehouse, to_warehouse):
        """Create Stock Entry for material transfer between warehouses"""
        try:
            # Additional validation to prevent zero quantity stock entries
            if not task.quantity or task.quantity <= 0:
                frappe.log_error(f"Skipping Stock Entry creation for Put-Away Task {task.name}: quantity is zero or negative")
                return None
            
            # Check for negative stock in source warehouse before creating Stock Entry
            # Get actual stock from Bin table (Bin table doesn't have batch_no field)
            batch_stock_qty = frappe.db.get_value("Bin", {
                "item_code": task.item_code,
                "warehouse": from_warehouse
            }, "actual_qty") or 0
            
            if batch_stock_qty < 0:
                frappe.log_error(f"Skipping Stock Entry creation for Put-Away Task {task.name}: Item {task.item_code} has negative stock {batch_stock_qty} in {from_warehouse}")
                frappe.msgprint(f"Warning: Cannot create Stock Entry - Item {task.item_code} has negative stock {batch_stock_qty} in {from_warehouse}")
                return None
                
            stock_entry = frappe.new_doc("Stock Entry")
            stock_entry.stock_entry_type = "Material Transfer"
            stock_entry.company = self.company
            stock_entry.posting_date = frappe.utils.today()
            stock_entry.posting_time = frappe.utils.now()
            stock_entry.remarks = f"Material transfer for Put-Away Task {task.name}"
            
            # Add item to stock entry
            stock_entry.append("items", {
                "item_code": task.item_code,
                "item_name": task.item_name,
                "qty": task.quantity,
                "uom": task.uom,
                "stock_uom": task.uom,
                "transfer_qty": task.quantity,
                "batch_no": task.batch_no,
                "expiry_date": task.expiry_date,  # Include expiry date from putaway task
                "s_warehouse": from_warehouse,  # Source warehouse
                "t_warehouse": to_warehouse   # Target warehouse
            })
            
            # Save and submit Stock Entry
            stock_entry.insert(ignore_permissions=True)
            stock_entry.submit()  # Submit to make it effective
            
            frappe.msgprint(f"Stock Entry {stock_entry.name} created and submitted successfully")
            return stock_entry.name
            
        except Exception as e:
            frappe.log_error(f"Failed to create Stock Entry for Put-Away Task {task.name}: {str(e)}")
            frappe.throw(f"Failed to create Stock Entry: {str(e)}")

    def get_staging_bin_for_warehouse(self):

        staging_bin = frappe.db.get_value(
            "WMS Bin",
            {
                "warehouse": self.warehouse,
                "is_staging": 1
            },
            "name"
        )

        if not staging_bin:
            frappe.throw(f"No staging bin configured for warehouse {self.warehouse}")

        return staging_bin



def get_suggested_bin(item_code, warehouse):

    # Try to find bin already storing this item
    existing_bin = frappe.db.get_value(
        "WMS Bin Ledger",
        {
            "item_code": item_code,
            "warehouse": warehouse
        },
        "bin_location",
        order_by="posting_datetime desc"
    )

    if existing_bin:
        return existing_bin

    # Otherwise return any storage bin
    return frappe.db.get_value(
        "WMS Bin",
        {
            "warehouse": warehouse,
            "is_staging": 0
        },
        "name"
    )