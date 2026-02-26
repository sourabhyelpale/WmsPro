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

        self.calculate_totals()

        item_codes = [d.item_code for d in self.items if d.item_code]

        item_details = frappe.get_all(
            "Item",
            filters={"name": ["in", item_codes]},
            fields=["name", "item_name", "stock_uom"]
        )

        item_map = {d.name: d for d in item_details}

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
        fulfillment.total_qty_required = self.total_qty

        for row in self.items:
            item = item_map.get(row.item_code)

            fulfillment.append("items", {
                "item_code": row.item_code,
                "item_name": item.item_name if item else "",
                "qty_required": row.qty_requested,
                "uom": row.uom or (item.stock_uom if item else ""),
                "stock_uom": item.stock_uom if item else ""
            })

        fulfillment.insert(ignore_permissions=True)
        self.db_set("fulfillment_order", fulfillment.name)




    def create_distribution_order(self):
        if self.distribution_order:
            return

        item_codes = [d.item_code for d in self.items if d.item_code]

        item_details = frappe.get_all(
            "Item",
            filters={"name": ["in", item_codes]},
            fields=["name", "item_name", "stock_uom"]
        )

        item_map = {d.name: d for d in item_details}


        distribution = frappe.new_doc("OMS Distribution Order")
        distribution.naming_series = "DST-.YYYY.-.#####"
        distribution.company = self.company
        distribution.distribution_type = "Emergency Deployment"
        distribution.source_warehouse = self.source_facility
        distribution.distribution_date = today()
        distribution.status = "Draft"

        for row in self.items:
            item = item_map.get(row.item_code)

            distribution.append("items", {
                "item_code": row.item_code,
                "item_name": item.item_name if item else "",
                "facility": self.requesting_facility,
                "qty_to_distribute": row.qty_requested,
                "uom": row.uom or (item.stock_uom if item else ""),
                "stock_uom": item.stock_uom if item else ""
            })

        distribution.insert(ignore_permissions=True)
        self.db_set("distribution_order", distribution.name)




    def create_material_request(self):
        if self.material_request:
            return

        item_codes = [d.item_code for d in self.items if d.item_code]

        item_details = frappe.get_all(
            "Item",
            filters={"name": ["in", item_codes]},
            fields=["name", "item_name", "stock_uom"]
        )

        item_map = {d.name: d for d in item_details}

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
            item = item_map.get(row.item_code)

            mr.append("items", {
                "item_code": row.item_code,
                "item_name": item.item_name if item else "",
                "qty": row.qty_requested,
                "uom": row.uom or (item.stock_uom if item else ""),
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