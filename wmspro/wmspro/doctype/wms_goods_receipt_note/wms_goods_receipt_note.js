// Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
// For license information, please see license.txt

frappe.ui.form.on("WMS Goods Receipt Note", {
    refresh(frm) {
        // Enable inline editing for child table
        frm.fields_dict['wms_grn_item'].grid.set_df_property('item_code', 'allow_in_quick_entry', 1);
        frm.fields_dict['wms_grn_item'].grid.set_df_property('item_name', 'allow_in_quick_entry', 1);
        frm.fields_dict['wms_grn_item'].grid.set_df_property('mrp', 'allow_in_quick_entry', 1);
        frm.fields_dict['wms_grn_item'].grid.set_df_property('rate', 'allow_in_quick_entry', 1);
        frm.fields_dict['wms_grn_item'].grid.set_df_property('amount', 'allow_in_quick_entry', 1);
        frm.fields_dict['wms_grn_item'].grid.set_df_property('qty_expected', 'allow_in_quick_entry', 1);
        frm.fields_dict['wms_grn_item'].grid.set_df_property('qty_accepted', 'allow_in_quick_entry', 1);
        frm.fields_dict['wms_grn_item'].grid.set_df_property('batch_no', 'allow_in_quick_entry', 1);
        frm.fields_dict['wms_grn_item'].grid.set_df_property('expiry_date', 'allow_in_quick_entry', 1);
    }
});

// Auto-fill item name when item code is selected
frappe.ui.form.on("WMS Inbound Task", {
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.item_code) {
            frappe.db.get_value("Item", row.item_code, ["item_name", "stock_uom"])
                .then(r => {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, "item_name", r.message.item_name);
                        frappe.model.set_value(cdt, cdn, "stock_uom", r.message.stock_uom);
                    }
                });
        } else {
            frappe.model.set_value(cdt, cdn, "item_name", "");
            frappe.model.set_value(cdt, cdn, "stock_uom", "");
        }
    }
});
