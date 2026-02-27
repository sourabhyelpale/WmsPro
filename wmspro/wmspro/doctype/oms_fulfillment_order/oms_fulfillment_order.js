// Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
// For license information, please see license.txt

// frappe.ui.form.on("OMS Fulfillment Order", {
// 	refresh(frm) {

// 	},
// });


frappe.ui.form.on("OMS Fulfillment Order", {
    refresh(frm) {

        if (frm.doc.docstatus === 0 
            && frm.doc.allocation_complete 
            && !frm.doc.pick_list) {

            frm.add_custom_button("Create Pick List", function () {

                frappe.call({
                    method: "create_pick_list_button",
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: "Creating Pick List...",
                    callback: function (r) {

                        if (r.message) {

                            frappe.msgprint({
                                title: "Success",
                                message: "Pick List Created Successfully",
                                indicator: "green"
                            });

                            // Just reload form to show pick_list link
                            frm.reload_doc();
                        }
                    }
                });

            }).addClass("btn-primary");
        }
    }
});