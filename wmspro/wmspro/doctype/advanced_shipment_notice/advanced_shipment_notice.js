frappe.ui.form.on('Advanced Shipment Notice', {
    
    refresh: function(frm) {
        console.log("ASN Form Refreshed");
        console.log("Current doc status:", frm.doc.docstatus);
        console.log("Current doc name:", frm.doc.name);
    },
    
    before_submit: function(frm) {

        console.log("=== ASN SUBMISSION STARTED ===");

        if (!frm.doc.warehouse) {
            frappe.throw("Please select Warehouse before submitting ASN");
        }

        if (!frm.doc.advanced_shipment_notice_details || 
            frm.doc.advanced_shipment_notice_details.length === 0) {
            frappe.throw("Please add at least one item before submitting ASN");
        }

        console.log("ASN Name:", frm.doc.name);
        console.log("Supplier:", frm.doc.supplier);
        console.log("Company:", frm.doc.company);
        console.log("Warehouse:", frm.doc.warehouse);
        console.log("Purchase Order:", frm.doc.purchase_order);
    },
    
    after_save: function(frm) {
        console.log("=== ASN SAVED ===");
        console.log("Docstatus after save:", frm.doc.docstatus);
        console.log("Name after save:", frm.doc.name);
    },
    
    on_submit: function(frm) {
        console.log("=== ASN SUBMITTED SUCCESSFULLY ===");
        console.log("Final docstatus:", frm.doc.docstatus);
        console.log("Final name:", frm.doc.name);
    },

   
    supplier: function(frm) {

        if (!frm.doc.supplier) {
            frm.set_value("purchase_order", "");
            frm.set_value("supplier_name", "");
            frm.clear_table("advanced_shipment_notice_details");
            frm.refresh_field("advanced_shipment_notice_details");
            return;
        }

        // Auto-fetch supplier name
        if (frm.doc.supplier) {
            frappe.db.get_value("Supplier", frm.doc.supplier, "supplier_name", function(r) {
                // console.log("Supplier API response:", r);
                // console.log("Response keys:", Object.keys(r));
                
                // Check if supplier_name is directly in response or in message
                if (r.supplier_name) {
                    frm.set_value("supplier_name", r.supplier_name);
                    //console.log("Supplier name set from response:", r.supplier_name);
                } else if (r.message && r.message.supplier_name) {
                    frm.set_value("supplier_name", r.message.supplier_name);
                    //console.log("Supplier name set from message:", r.message.supplier_name);
                } else {
                    //console.log("No supplier name found for:", frm.doc.supplier);
                    //console.log("Full response:", r);
                }
            });
        }
      
        frm.set_query("purchase_order", function() {
            return {
                filters: {
                    supplier: frm.doc.supplier,
                    docstatus: 1
                }
            };
        });

       
        frm.set_value("purchase_order", "");
        frm.clear_table("advanced_shipment_notice_details");
        frm.refresh_field("advanced_shipment_notice_details");
    },


  
    purchase_order: function(frm) {

        if (!frm.doc.purchase_order) return;

        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Purchase Order",
                name: frm.doc.purchase_order
            },
            callback: function(r) {

                if (!r.message) return;

                let po = r.message;

                frm.clear_table("advanced_shipment_notice_details");

                po.items.forEach(item => {

                   
                    let pending_qty = item.qty - (item.received_qty || 0);

                    if (pending_qty > 0) {

                        let row = frm.add_child("advanced_shipment_notice_details");

                        row.item_code = item.item_code;
                        row.item_name = item.item_name;  // Add item_name
                        row.description = item.description;
                        row.rate = item.rate;  // Add rate from PO
                        row.ordered_qty = pending_qty;
                        row.expected_qty = pending_qty; 
                        row.stock_uom = item.stock_uom;      
                    }
                });

                frm.refresh_field("advanced_shipment_notice_details");
            }
        });
    }

});