// // Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
// // For license information, please see license.txt





frappe.ui.form.on('OMS Delivery Route', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 0 && frm.doc.stops && frm.doc.stops.length > 0) {
            frm.add_custom_button(__('Optimize Route'), function() {
                frm.call('optimize_route').then(() => frm.refresh());
            }).addClass("btn-primary");
        }
    },

    vehicle: function(frm) {
        if (frm.doc.vehicle) {
            frappe.db.get_value('OMS Vehicle Profile', frm.doc.vehicle, 'driver', (r) => {
                if (r && r.driver) {
                    frm.set_value('driver', r.driver);
                }
            });
        }
    }
});


frappe.ui.form.on('OMS Route Stop', {
    fulfillment_order: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.fulfillment_order) return;

        frm.call({
            doc: frm.doc,
            method: 'get_stop_details',
            args: { fulfillment_order: row.fulfillment_order },
            callback: function(r) {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, 'delivery_address', r.message.delivery_address);
                    frappe.model.set_value(cdt, cdn, 'lattitude', r.message.latitude);
                    frappe.model.set_value(cdt, cdn, 'longitude', r.message.longitude);
                    frappe.model.set_value(cdt, cdn, 'shipment_weight_kg', r.message.weight);
                    frappe.model.set_value(cdt, cdn, 'shipment_volume_cbm', r.message.volume);
                    
                    frm.refresh_field('stops');
                }
            }
        });
    }
});