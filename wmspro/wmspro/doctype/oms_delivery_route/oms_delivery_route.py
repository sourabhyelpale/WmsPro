# Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class OMSDeliveryRoute(Document):

    def validate(self):
        self.calculate_totals()

        # Driver mandatory
        if not self.driver:
            frappe.throw("Driver is mandatory before submitting Route")

        # Overload checks
        if self.load_weight_pct and self.load_weight_pct > 100:
            frappe.throw("Vehicle Overloaded (Weight exceeds capacity)")

        if self.load_volume_pct and self.load_volume_pct > 100:
            frappe.throw("Vehicle Overloaded (Volume exceeds capacity)")


    def on_submit(self):
        trx = self.create_transport_execution()
        self.assign_to_driver(trx)


    def create_transport_execution(self):

        existing = frappe.db.exists(
            "OMS Transport Execution",
            {"delivery_route": self.name}
        )

        if existing:
            frappe.throw("Transport Execution already exists for this Route")

        trx = frappe.new_doc("OMS Transport Execution")
        trx.delivery_route = self.name
        trx.vehicle = self.vehicle
        trx.driver = self.driver
        trx.planned_departure = self.planned_departure
        trx.status = "Pending"

        trx.insert(ignore_permissions=True)
        trx.submit()

        return trx


    def assign_to_driver(self, trx):

        if not self.driver:
            return

        frappe.get_doc({
            "doctype": "ToDo",
            "allocated_to": self.driver,
            "reference_type": "OMS Transport Execution",
            "reference_name": trx.name,
            "description": f"New Route Assigned: {self.name}",
            "status": "Open"
        }).insert(ignore_permissions=True)

        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": "New Delivery Route Assigned",
            "for_user": self.driver,
            "type": "Alert",
            "document_type": "OMS Transport Execution",
            "document_name": trx.name,
            "from_user": frappe.session.user
        }).insert(ignore_permissions=True)

        frappe.publish_realtime(
            event="msgprint",
            message=f"New Route {self.name} assigned to you.",
            user=self.driver
        )


    def calculate_totals(self):

        total_stops = len(self.stops or [])
        total_weight = 0
        total_volume = 0

        for row in self.stops:
            total_weight += row.shipment_weight_kg or 0
            total_volume += row.shipment_volume_cbm or 0

        self.total_stops = total_stops
        self.total_weight_kg = total_weight
        self.total_volume_cbm = total_volume

        if self.vehicle:
            vehicle = frappe.get_doc("OMS Vehicle Profile", self.vehicle)

            self.load_weight_pct = (
                (total_weight / vehicle.max_weight_kg) * 100
                if vehicle.max_weight_kg else 0
            )

            self.load_volume_pct = (
                (total_volume / vehicle.volume_capacity_cbm) * 100
                if vehicle.volume_capacity_cbm else 0
            )
        else:
            self.load_weight_pct = 0
            self.load_volume_pct = 0

