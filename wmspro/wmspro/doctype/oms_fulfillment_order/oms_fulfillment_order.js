// Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
// For license information, please see license.txt

// frappe.ui.form.on("OMS Fulfillment Order", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on("OMS Fulfillment Order", {
    refresh(frm) {

        frm.remove_custom_button("Create Pick List");

        if (!frm.is_new()) {
            frm.add_custom_button("Create Pick List", () => {
                frappe.call({
                    method: "create_pick_list_button",
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: "Allocating stock & creating Pick List...",
                    callback(r) {
                        if (r.message) {
                            frappe.show_alert({
                                message: "Pick List " + r.message + " created",
                                indicator: "green"
                            });
                            frm.reload_doc();
                        }
                    }
                });
            }).addClass("btn-primary");
        }
    }
});