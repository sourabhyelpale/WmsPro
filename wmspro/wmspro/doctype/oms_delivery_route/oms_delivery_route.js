// Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
// For license information, please see license.txt

// frappe.ui.form.on("OMS Delivery Route", {
// 	refresh(frm) {

// 	},
// });



frappe.ui.form.on('OMS Delivery Route', {

    // -----------------------------
    // Vehicle → Auto Fetch Driver
    // -----------------------------
    vehicle: function(frm) {

        if (!frm.doc.vehicle) {
            frm.set_value('driver', '');
            return;
        }

        frappe.db.get_value(
            'OMS Vehicle Profile',
            frm.doc.vehicle,
            'driver'
        ).then(r => {

            if (r.message && r.message.driver) {
                frm.set_value('driver', r.message.driver);
            } else {
                frm.set_value('driver', '');
                frappe.msgprint("No driver assigned in selected Vehicle Profile.");
            }

        });

    }

});


// ==============================================
// Child Table: OMS Route Stop
// Fulfillment Order → Auto Delivery Address
// ==============================================

frappe.ui.form.on('OMS Route Stop', {

    fulfillment_order: function(frm, cdt, cdn) {

        let row = locals[cdt][cdn];

        if (!row.fulfillment_order) {
            frappe.model.set_value(cdt, cdn, 'delivery_address', '');
            return;
        }

        frappe.db.get_value(
            'OMS Fulfillment Order',
            row.fulfillment_order,
            'delivery_address'
        ).then(r => {

            if (r.message && r.message.delivery_address) {
                frappe.model.set_value(
                    cdt,
                    cdn,
                    'delivery_address',
                    r.message.delivery_address
                );
            } else {
                frappe.msgprint("No Delivery Address found in selected Fulfillment Order.");
            }

        });

    }

});




// ==============================================
// PARENT: OMS Delivery Route
// ==============================================

frappe.ui.form.on('OMS Delivery Route', {

    vehicle: function(frm) {
        calculate_totals(frm);
    },

    refresh: function(frm) {
        calculate_totals(frm);
    }

});


// ==============================================
// CHILD TABLE: OMS Route Stop
// ==============================================

frappe.ui.form.on('OMS Route Stop', {

    sequence: function(frm) {
        calculate_totals(frm);
    },

    shipment_weight_kg: function(frm) {
        calculate_totals(frm);
    },

    shipment_volume_cbm: function(frm) {
        calculate_totals(frm);
    },

    stops_remove: function(frm) {
        calculate_totals(frm);
    }

});


// ==============================================
// COMMON CALCULATION FUNCTION
// ==============================================

function calculate_totals(frm) {

    let total_stops = 0;
    let total_weight = 0;
    let total_volume = 0;

    if (frm.doc.stops) {

        total_stops = frm.doc.stops.length;

        frm.doc.stops.forEach(row => {
            total_weight += flt(row.shipment_weight_kg);
            total_volume += flt(row.shipment_volume_cbm);
        });
    }

    frm.set_value('total_stops', total_stops);
    frm.set_value('total_weight_kg', total_weight);
    frm.set_value('total_volume_cbm', total_volume);

    // Calculate Load %
    if (frm.doc.vehicle) {

        frappe.db.get_value(
            'OMS Vehicle Profile',
            frm.doc.vehicle,
            ['max_weight_kg', 'volume_capacity_cbm']
        ).then(r => {

            if (r.message) {

                let max_weight = flt(r.message.max_weight_kg);
                let max_volume = flt(r.message.volume_capacity_cbm);

                let load_weight_pct = 0;
                let load_volume_pct = 0;

                if (max_weight > 0) {
                    load_weight_pct = (total_weight / max_weight) * 100;
                }

                if (max_volume > 0) {
                    load_volume_pct = (total_volume / max_volume) * 100;
                }

                frm.set_value('load_weight_pct', load_weight_pct);
                frm.set_value('load_volume_pct', load_volume_pct);

            }

        });
    }
}


