# Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

class OMSDeliveryRoute(Document):
    def validate(self):
        # 1. Sync all child table data and calculations on Save
        # self.sync_stop_details()
        self.calculate_totals()
        self.check_vehicle_availability()
        self.calculate_route_metrics()

        # 2. Hard Validations
        if not self.driver:
            frappe.throw("Driver is mandatory before submitting Route")

        if flt(self.load_weight_pct) > 100:
            frappe.throw(f"Vehicle Overloaded! Weight is at {self.load_weight_pct}%")

        if flt(self.load_volume_pct) > 100:
            frappe.throw(f"Vehicle Overloaded! Volume is at {self.load_volume_pct}%")

    def sync_stop_details(self):
        """Fetches Lat/Long, Address, Weight, and Volume for every stop."""
        for stop in self.stops:
            if stop.fulfillment_order:
                details = self.get_stop_details(stop.fulfillment_order)
                stop.lattitude = details.get("latitude")
                stop.longitude = details.get("longitude")
                stop.delivery_address = details.get("delivery_address")
                stop.shipment_weight_kg = details.get("weight")
                stop.shipment_volume_cbm = details.get("volume")

    @frappe.whitelist()
    def get_stop_details(self, fulfillment_order):
        fo = frappe.get_doc("OMS Fulfillment Order", fulfillment_order)
        res = {
            "delivery_address": fo.delivery_address or "",
            "latitude": 0,
            "longitude": 0,
            "weight": 0,
            "volume": 0
        }

        # Coordinate Logic: Warehouse -> Facility -> Lat/Long
        warehouse = fo.get("source_warehouse")
        if warehouse:
            facility_data = frappe.db.get_value("Facility", {"warehouse": warehouse}, 
                ["latitude", "longitude"], as_dict=True)
            if facility_data:
                res["latitude"] = facility_data.latitude
                res["longitude"] = facility_data.longitude

        # Payload Logic: (L * W * H) / 1,000,000
        total_weight = 0.0
        total_volume = 0.0
        for item in fo.items:
            qty = flt(item.qty_required)
            if qty <= 0: continue
            pkg = frappe.db.get_all("Item Packaging Level Details", 
                filters={"parent": item.item_code, "parenttype": "Item"},
                fields=["gross_weight", "length", "width", "height"])
            
            if pkg:
                p = pkg[0]
                total_weight += flt(p.get("gross_weight", 0)) * qty
                l, w, h = flt(p.get("length", 0)), flt(p.get("width", 0)), flt(p.get("height", 0))
                total_volume += ((l * w * h) / 1000000) * qty
        
        res["weight"] = flt(total_weight, 3)
        res["volume"] = flt(total_volume, 6)
        return res

    def calculate_totals(self):
        self.total_stops = len(self.stops or [])
        tw = sum(flt(s.shipment_weight_kg) for s in self.stops)
        tv = sum(flt(s.shipment_volume_cbm) for s in self.stops)
        self.total_weight_kg = tw
        self.total_volume_cbm = tv

        if self.vehicle:
            v = frappe.db.get_value("OMS Vehicle Profile", self.vehicle, 
                ["max_weight_kg", "volume_capacity_cbm"], as_dict=True)
            if v:
                self.load_weight_pct = (tw / flt(v.max_weight_kg) * 100) if v.max_weight_kg else 0
                self.load_volume_pct = (tv / flt(v.volume_capacity_cbm) * 100) if v.volume_capacity_cbm else 0

    def check_vehicle_availability(self):
        if not self.route_date or not self.vehicle: return
        duplicate = frappe.db.exists("OMS Delivery Route", {
            "vehicle": self.vehicle,
            "route_date": self.route_date,
            "docstatus": 1,
            "name": ["!=", self.name]
        })
        if duplicate:
            frappe.throw(f"Vehicle {self.vehicle} is already assigned to {duplicate} on this date.")

    def calculate_route_metrics(self):
        if not self.estimated_distance_km: self.estimated_distance_km = 150.0
        if not self.estimated_duration_hrs: self.estimated_duration_hrs = 3.5

    def on_submit(self):
        # 1. Create and Link Transport Execution on Submit
        if not self.transport_execution:
            trx = frappe.new_doc("OMS Transport Execution")
            trx.delivery_route = self.name
            trx.vehicle = self.vehicle
            trx.driver = self.driver
            trx.planned_departure = self.planned_departure or now_datetime()
            trx.status = "Pending" 
            trx.insert(ignore_permissions=True)
            trx.submit()
            
            # Use db_set to update the field on a submitted document
            self.db_set("transport_execution", trx.name)

        # 2. Create ToDo Task for Driver
        frappe.get_doc({
            "doctype": "ToDo",
            "allocated_to": self.driver,
            "reference_type": "OMS Transport Execution",
            "reference_name": self.transport_execution,
            "description": f"New Delivery Manifest: {self.name}",
            "status": "Open"
        }).insert(ignore_permissions=True)

        # 3. Send Notification Log
        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"Route {self.name} assigned to you.",
            "for_user": self.driver,
            "type": "Alert",
            "document_type": "OMS Transport Execution",
            "document_name": self.transport_execution,
            "from_user": frappe.session.user
        }).insert(ignore_permissions=True)

    @frappe.whitelist()
    def optimize_route(self):
        for idx, stop in enumerate(self.stops):
            stop.sequence = idx + 1
        self.save()