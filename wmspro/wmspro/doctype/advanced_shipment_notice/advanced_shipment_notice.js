frappe.ui.form.on('Advanced Shipment Notice', {

   
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
                console.log("Supplier API response:", r);
                console.log("Type of r.message:", typeof r.message);
                console.log("r.message keys:", r.message ? Object.keys(r.message) : 'No message');
                
                if (r.message && r.message.supplier_name !== undefined && r.message.supplier_name !== null) {
                    frm.set_value("supplier_name", r.message.supplier_name);
                    console.log("Supplier name set:", r.message.supplier_name);
                } else {
                    console.log("No supplier name found for:", frm.doc.supplier);
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
                        row.description = item.description;
                        row.ordered_qty = pending_qty;
                    }
                });

                frm.refresh_field("advanced_shipment_notice_details");
            }
        });
    }

});