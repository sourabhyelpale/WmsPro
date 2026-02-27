// Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
// For license information, please see license.txt

// frappe.ui.form.on("OMS Requisition Order", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on("OMS Requisition Order", {
    requesting_facility(frm) {
        if (!frm.doc.requesting_facility) {
            frm.set_value("delivery_address", "");
            return;
        }

        frappe.call({
            method: "wmspro.wmspro.doctype.oms_requisition_order.oms_requisition_order.get_delivery_address_from_facility",
            args: {
                requesting_facility: frm.doc.requesting_facility
            },
            callback(r) {
                if (r.message) {
                    frm.set_value("delivery_address", r.message);
                } else {
                    frm.set_value("delivery_address", "");
                }
            }
        });
    }
});
