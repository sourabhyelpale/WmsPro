// Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
// For license information, please see license.txt

// frappe.ui.form.on("WMS Outbound Shipment", {
// 	refresh(frm) {

// 	},
// });


// Copyright (c) 2026, Quantbit Technologies
// License: see license.txt

frappe.ui.form.on("WMS Outbound Shipment", {
    refresh(frm) {

        // REMOVE OLD BUTTONS TO AVOID DUPLICATES
        frm.clear_custom_buttons();

        // CREATE PACKING LIST
        if (
            frm.doc.docstatus === 1 &&
            frm.doc.status === "Packing" &&
            !frm.doc.packing_list
        ) {
            frm.add_custom_button(
                "Create Packing List",
                () => {
                    frappe.call({
                        method: "create_packing_list",
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: "Creating Packing List...",
                        callback: (r) => {
                            if (r.message) {
                                frappe.show_alert({
                                    message: "Packing List Created",
                                    indicator: "green"
                                });

                                frappe.set_route(
                                    "Form",
                                    "WMS Packing List",
                                    r.message
                                );
                            }
                        }
                    });
                },
                "Actions"
            );
        }

        // VIEW PACKING LIST
        if (frm.doc.packing_list) {
            frm.add_custom_button(
                "View Packing List",
                () => {
                    frappe.set_route(
                        "Form",
                        "WMS Packing List",
                        frm.doc.packing_list
                    );
                },
                "Actions"
            );
        }
    }
});