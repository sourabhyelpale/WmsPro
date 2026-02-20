# Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today


class OMSRequisitionOrder(Document):

    def validate(self):
        self.calculate_totals()

    def on_submit(self):
        self.calculate_totals()
        self.create_fulfillment_order()
        self.create_distribution_order()
        self.create_material_request()
        self.create_consumption_forecast()

    def calculate_totals(self):

        total_qty = 0
        total_value = 0

        for row in self.items:
            total_qty += row.qty_requested or 0
            total_value += row.estimated_value or 0

        self.total_qty = total_qty
        self.total_value = total_value

    def create_fulfillment_order(self):

        if self.fulfillment_order:
            return

        fulfillment = frappe.new_doc("OMS Fulfillment Order")
        fulfillment.naming_series = "FUL-.YYYY.-.#####"
        fulfillment.company = self.company
        fulfillment.fulfillment_type = "Pull (Requisition)"
        fulfillment.requisition_order = self.name
        fulfillment.source_warehouse = self.source_facility
        fulfillment.destination_facility = self.requesting_facility
        fulfillment.delivery_address = self.delivery_address
        fulfillment.required_by_date = self.required_by_date
        fulfillment.priority = self.priority
        fulfillment.status = "Draft"

        for row in self.items:
            fulfillment.append("items", {
                "item_code": row.item_code,
                "qty_required": row.qty_requested,
                "uom": row.uom,
                "stock_uom": row.stock_uom
            })

        fulfillment.insert(ignore_permissions=True)
        self.db_set("fulfillment_order", fulfillment.name)

    def create_distribution_order(self):

        if self.distribution_order:
            return

        distribution = frappe.new_doc("OMS Distribution Order")
        distribution.naming_series = "DST-.YYYY.-.#####"
        distribution.company = self.company
        distribution.distribution_type = "Emergency Deployment"
        distribution.source_warehouse = self.source_facility
        distribution.distribution_date = today()
        distribution.status = "Draft"

        for row in self.items:
            distribution.append("items", {
                "item_code": row.item_code,
                "facility": self.requesting_facility,
                "qty_to_distribute": row.qty_requested,
                "uom": row.uom,
                "stock_uom": row.stock_uom
            })

        distribution.insert(ignore_permissions=True)
        self.db_set("distribution_order", distribution.name)

    def create_material_request(self):

        if self.material_request:
            return

        mr = frappe.new_doc("Material Request")
        mr.material_request_type = "Material Transfer"
        mr.company = self.company
        mr.schedule_date = self.required_by_date
        mr.from_warehouse = self.source_facility
        mr.to_warehouse = self.requesting_facility

        default_department = frappe.db.get_value(
            "Department",
            {"company": self.company},
            "name"
        )

        if default_department:
            mr.custom_for_department = default_department

        default_cost_center = frappe.db.get_value(
            "Cost Center",
            {"company": self.company, "is_group": 0},
            "name"
        )

        if default_cost_center:
            mr.cost_center = default_cost_center

        for row in self.items:
            mr.append("items", {
                "item_code": row.item_code,
                "qty": row.qty_requested,
                "uom": row.uom,
                "conversion_factor": 1,
                "schedule_date": self.required_by_date
            })

        mr.insert(ignore_permissions=True)
        self.db_set("material_request", mr.name)

    def create_consumption_forecast(self):

        if self.consumption_reference:
            return

        for row in self.items:
            forecast = frappe.new_doc("OMS Consumption Forecast")
            forecast.naming_series = "FCT-.YYYY.-.#####"
            forecast.facility = self.requesting_facility
            forecast.item_code = row.item_code
            forecast.forecast_date = today()
            forecast.forecast_horizon_days = 30
            forecast.forecast_method = "Manual"
            forecast.forecast_qty = row.qty_requested
            forecast.reorder_point = row.qty_requested
            forecast.requisition_generated = self.name
            forecast.insert(ignore_permissions=True)
            forecast.submit()
            self.db_set("consumption_reference", forecast.name)
            break
