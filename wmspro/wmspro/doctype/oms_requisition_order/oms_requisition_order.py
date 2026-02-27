# Copyright (c) 2026, Quantbit Technologies Private Limited  and contributors
# For license information, please see license.txt

# import frappe
# from frappe.model.document import Document
# from frappe.utils import today


# def get_warehouse_from_facility(facility):
#     if not facility:
#         return None
#     row = frappe.db.sql(
#         """
#         SELECT warehouse
#         FROM `tabFacility`
#         WHERE name = %s
#         LIMIT 1
#         """,
#         (facility,),
#         as_list=True
#     )
#     return row[0][0] if row and row[0][0] else None


# @frappe.whitelist()
# def get_delivery_address_from_facility(requesting_facility):
#     if not requesting_facility:
#         return ""
#     warehouse = get_warehouse_from_facility(requesting_facility)
#     if not warehouse:
#         return ""
#     row = frappe.db.sql(
#         """
#         SELECT parent
#         FROM `tabDynamic Link`
#         WHERE link_doctype = 'Warehouse'
#           AND link_name = %s
#           AND parenttype = 'Address'
#         LIMIT 1
#         """,
#         (warehouse,),
#         as_list=True
#     )
#     return row[0][0] if row else ""


# class OMSRequisitionOrder(Document):

#     def validate(self):
#         self.calculate_totals()

#     def on_submit(self):
#         self.calculate_totals()
#         self.create_fulfillment_order()
#         self.create_distribution_order()
#         self.create_material_request()
#         self.create_consumption_forecast()

#     def calculate_totals(self):
#         self.total_qty = sum(d.qty_requested or 0 for d in self.items)
#         self.total_value = sum(d.estimated_value or 0 for d in self.items)

#     def create_fulfillment_order(self):
#         if self.fulfillment_order:
#             return

#         source_wh = get_warehouse_from_facility(self.source_facility)
#         dest_wh = get_warehouse_from_facility(self.requesting_facility)
#         if not source_wh or not dest_wh:
#             frappe.throw("Warehouse missing for source or destination facility")

#         items = frappe.get_all(
#             "Item",
#             filters={"name": ["in", [d.item_code for d in self.items]]},
#             fields=["name", "item_name", "stock_uom"]
#         )
#         item_map = {i.name: i for i in items}

#         doc = frappe.new_doc("OMS Fulfillment Order")
#         doc.naming_series = "FUL-.YYYY.-.#####"
#         doc.company = self.company
#         doc.fulfillment_type = "Pull (Requisition)"
#         doc.requisition_order = self.name
#         doc.source_warehouse = source_wh
#         doc.destination_facility = dest_wh
#         doc.delivery_address = self.delivery_address
#         doc.required_by_date = self.required_by_date
#         doc.priority = self.priority
#         doc.status = "Draft"
#         doc.total_qty_required = self.total_qty

#         for r in self.items:
#             item = item_map.get(r.item_code)
#             uom = item.stock_uom if item else r.uom
#             if not uom:
#                 frappe.throw(f"UOM missing for Item {r.item_code}")
#             doc.append("items", {
#                 "item_code": r.item_code,
#                 "item_name": item.item_name if item else "",
#                 "qty_required": r.qty_requested,
#                 "uom": uom,
#                 "stock_uom": uom
#             })

#         doc.insert(ignore_permissions=True)
#         self.db_set("fulfillment_order", doc.name)

#     def create_distribution_order(self):
#         if self.distribution_order:
#             return

#         source_wh = get_warehouse_from_facility(self.source_facility)
#         dest_wh = get_warehouse_from_facility(self.requesting_facility)
#         if not source_wh or not dest_wh:
#             frappe.throw("Warehouse missing for source or destination facility")

#         items = frappe.get_all(
#             "Item",
#             filters={"name": ["in", [d.item_code for d in self.items]]},
#             fields=["name", "stock_uom"]
#         )
#         item_map = {i.name: i for i in items}

#         doc = frappe.new_doc("OMS Distribution Order")
#         doc.naming_series = "DST-.YYYY.-.#####"
#         doc.company = self.company
#         doc.distribution_type = "Emergency Deployment"
#         doc.source_warehouse = source_wh
#         doc.distribution_date = today()
#         doc.status = "Draft"

#         for r in self.items:
#             item = item_map.get(r.item_code)
#             uom = item.stock_uom if item else r.uom
#             if not uom:
#                 frappe.throw(f"UOM missing for Item {r.item_code}")
#             doc.append("items", {
#                 "item_code": r.item_code,
#                 "facility": dest_wh,
#                 "qty_to_distribute": r.qty_requested,
#                 "uom": uom,
#                 "stock_uom": uom
#             })

#         doc.insert(ignore_permissions=True)
#         self.db_set("distribution_order", doc.name)

#     def create_material_request(self):
#         if self.material_request:
#             return

#         from_wh = get_warehouse_from_facility(self.source_facility)
#         to_wh = get_warehouse_from_facility(self.requesting_facility)
#         if not from_wh or not to_wh:
#             frappe.throw("Warehouse missing for source or destination facility")

#         department = frappe.db.get_value(
#             "Department",
#             {"company": self.company},
#             "name"
#         )
#         if not department:
#             frappe.throw("No Department found for company")

#         mr = frappe.new_doc("Material Request")
#         mr.material_request_type = "Material Transfer"
#         mr.company = self.company
#         mr.schedule_date = self.required_by_date
#         mr.from_warehouse = from_wh
#         mr.to_warehouse = to_wh
#         mr.set_warehouse = to_wh
#         mr.custom_for_department = department

#         for r in self.items:
#             mr.append("items", {
#                 "item_code": r.item_code,
#                 "qty": r.qty_requested,
#                 "schedule_date": self.required_by_date
#             })

#         mr.insert(ignore_permissions=True)
#         self.db_set("material_request", mr.name)

#     def create_consumption_forecast(self):
#         if self.consumption_reference:
#             return

#         r = self.items[0]

#         doc = frappe.new_doc("OMS Consumption Forecast")
#         doc.naming_series = "FCT-.YYYY.-.#####"
#         doc.facility = self.requesting_facility
#         doc.item_code = r.item_code
#         doc.forecast_date = today()
#         doc.forecast_horizon_days = 30
#         doc.forecast_method = "Manual"
#         doc.forecast_qty = r.qty_requested
#         doc.reorder_point = r.qty_requested
#         doc.requisition_generated = self.name

#         doc.insert(ignore_permissions=True)
#         doc.submit()
#         self.db_set("consumption_reference", doc.name)





# import frappe
# from frappe.model.document import Document
# from frappe.utils import today


# def get_warehouse_from_facility(facility):
#     if not facility:
#         return None
#     row = frappe.db.sql(
#         """
#         SELECT warehouse
#         FROM `tabFacility`
#         WHERE name = %s
#         LIMIT 1
#         """,
#         (facility,),
#         as_list=True
#     )
#     return row[0][0] if row and row[0][0] else None


# @frappe.whitelist()
# def get_delivery_address_from_facility(requesting_facility):
#     if not requesting_facility:
#         return ""
#     warehouse = get_warehouse_from_facility(requesting_facility)
#     if not warehouse:
#         return ""
#     row = frappe.db.sql(
#         """
#         SELECT parent
#         FROM `tabDynamic Link`
#         WHERE link_doctype = 'Warehouse'
#           AND link_name = %s
#           AND parenttype = 'Address'
#         LIMIT 1
#         """,
#         (warehouse,),
#         as_list=True
#     )
#     return row[0][0] if row else ""


# class OMSRequisitionOrder(Document):

#     def validate(self):
#         self.calculate_totals()

#     def on_submit(self):
#         self.calculate_totals()
#         fulfillment = self.create_fulfillment_order()
#         distribution = self.create_distribution_order()
#         self.link_distribution_to_fulfillment(fulfillment, distribution)
#         self.create_material_request()
#         self.create_consumption_forecast()

#     def calculate_totals(self):
#         self.total_qty = sum(d.qty_requested or 0 for d in self.items)
#         self.total_value = sum(d.estimated_value or 0 for d in self.items)

#     def create_fulfillment_order(self):
#         if self.fulfillment_order:
#             return frappe.get_doc("OMS Fulfillment Order", self.fulfillment_order)

#         source_wh = get_warehouse_from_facility(self.source_facility)
#         dest_wh = get_warehouse_from_facility(self.requesting_facility)

#         items = frappe.get_all(
#             "Item",
#             filters={"name": ["in", [d.item_code for d in self.items]]},
#             fields=["name", "item_name", "stock_uom"]
#         )
#         item_map = {i.name: i for i in items}

#         doc = frappe.new_doc("OMS Fulfillment Order")
#         doc.naming_series = "FUL-.YYYY.-.#####"
#         doc.company = self.company
#         doc.fulfillment_type = "Pull (Requisition)"
#         doc.requisition_order = self.name
#         doc.source_warehouse = source_wh
#         doc.destination_facility = dest_wh
#         doc.delivery_address = self.delivery_address
#         doc.required_by_date = self.required_by_date
#         doc.priority = self.priority
#         doc.status = "Draft"
#         doc.total_qty_required = self.total_qty

#         for r in self.items:
#             item = item_map.get(r.item_code)
#             uom = item.stock_uom
#             doc.append("items", {
#                 "item_code": r.item_code,
#                 "item_name": item.item_name,
#                 "qty_required": r.qty_requested,
#                 "uom": uom,
#                 "stock_uom": uom
#             })

#         doc.insert(ignore_permissions=True)
#         self.db_set("fulfillment_order", doc.name)
#         return doc

#     def create_distribution_order(self):
#         if self.distribution_order:
#             return frappe.get_doc("OMS Distribution Order", self.distribution_order)

#         source_wh = get_warehouse_from_facility(self.source_facility)
#         dest_wh = get_warehouse_from_facility(self.requesting_facility)

#         items = frappe.get_all(
#             "Item",
#             filters={"name": ["in", [d.item_code for d in self.items]]},
#             fields=["name", "item_name", "stock_uom"]
#         )
#         item_map = {i.name: i for i in items}

#         doc = frappe.new_doc("OMS Distribution Order")
#         doc.naming_series = "DST-.YYYY.-.#####"
#         doc.company = self.company
#         doc.distribution_type = "Emergency Deployment"
#         doc.source_warehouse = source_wh
#         doc.distribution_date = today()
#         doc.status = "Draft"

#         for r in self.items:
#             item = item_map.get(r.item_code)
#             uom = item.stock_uom
#             doc.append("items", {
#                 "item_code": r.item_code,
#                 "item_name": item.item_name,
#                 "facility": dest_wh,
#                 "qty_to_distribute": r.qty_requested,
#                 "qty_dispatched": 0,
#                 "qty_received": 0,
#                 "uom": uom,
#                 "stock_uom": uom,
#                 "status": "Pending"
#             })

#         doc.insert(ignore_permissions=True)
#         self.db_set("distribution_order", doc.name)
#         return doc

#     def link_distribution_to_fulfillment(self, fulfillment, distribution):
#         if not fulfillment or not distribution:
#             return
#         fulfillment.db_set("distribution_order", distribution.name)

#     def create_material_request(self):
#         if self.material_request:
#             return

#         from_wh = get_warehouse_from_facility(self.source_facility)
#         to_wh = get_warehouse_from_facility(self.requesting_facility)

#         department = frappe.db.get_value("Department", {"company": self.company}, "name")

#         mr = frappe.new_doc("Material Request")
#         mr.material_request_type = "Material Transfer"
#         mr.company = self.company
#         mr.schedule_date = self.required_by_date
#         mr.from_warehouse = from_wh
#         mr.to_warehouse = to_wh
#         mr.set_warehouse = to_wh
#         mr.custom_for_department = department

#         for r in self.items:
#             mr.append("items", {
#                 "item_code": r.item_code,
#                 "qty": r.qty_requested,
#                 "schedule_date": self.required_by_date
#             })

#         mr.insert(ignore_permissions=True)
#         self.db_set("material_request", mr.name)

#     def create_consumption_forecast(self):
#         if self.consumption_reference:
#             return

#         r = self.items[0]

#         doc = frappe.new_doc("OMS Consumption Forecast")
#         doc.naming_series = "FCT-.YYYY.-.#####"
#         doc.facility = self.requesting_facility
#         doc.item_code = r.item_code
#         doc.forecast_date = today()
#         doc.forecast_horizon_days = 30
#         doc.forecast_method = "Manual"
#         doc.forecast_qty = r.qty_requested
#         doc.reorder_point = r.qty_requested
#         doc.requisition_generated = self.name

#         doc.insert(ignore_permissions=True)
#         doc.submit()
#         self.db_set("consumption_reference", doc.name)





import frappe
from frappe.model.document import Document
from frappe.utils import today


def get_warehouse_from_facility(facility):
    if not facility:
        return None
    row = frappe.db.sql(
        """
        SELECT warehouse
        FROM `tabFacility`
        WHERE name = %s
        LIMIT 1
        """,
        (facility,),
        as_list=True
    )
    return row[0][0] if row and row[0][0] else None


@frappe.whitelist()
def get_delivery_address_from_facility(requesting_facility):
    if not requesting_facility:
        return ""
    warehouse = get_warehouse_from_facility(requesting_facility)
    if not warehouse:
        return ""
    row = frappe.db.sql(
        """
        SELECT parent
        FROM `tabDynamic Link`
        WHERE link_doctype = 'Warehouse'
          AND link_name = %s
          AND parenttype = 'Address'
        LIMIT 1
        """,
        (warehouse,),
        as_list=True
    )
    return row[0][0] if row else ""


class OMSRequisitionOrder(Document):

    def validate(self):
        self.calculate_totals()

    def on_submit(self):
        self.calculate_totals()
        fulfillment = self.create_fulfillment_order()
        distribution = self.create_distribution_order()
        self.link_distribution_to_fulfillment(fulfillment, distribution)
        self.create_material_request()
        self.create_consumption_forecast()

    def calculate_totals(self):
        self.total_qty = sum(d.qty_requested or 0 for d in self.items)
        self.total_value = sum(d.estimated_value or 0 for d in self.items)

    def create_fulfillment_order(self):
        if self.fulfillment_order:
            return frappe.get_doc("OMS Fulfillment Order", self.fulfillment_order)

        source_wh = get_warehouse_from_facility(self.source_facility)
        dest_wh = get_warehouse_from_facility(self.requesting_facility)

        items = frappe.get_all(
            "Item",
            filters={"name": ["in", [d.item_code for d in self.items]]},
            fields=["name", "item_name", "stock_uom"]
        )
        item_map = {i.name: i for i in items}

        doc = frappe.new_doc("OMS Fulfillment Order")
        doc.naming_series = "FUL-.YYYY.-.#####"
        doc.company = self.company
        doc.fulfillment_type = "Pull (Requisition)"
        doc.requisition_order = self.name
        doc.source_warehouse = source_wh
        doc.destination_facility = dest_wh
        doc.delivery_address = self.delivery_address
        doc.required_by_date = self.required_by_date
        doc.priority = self.priority
        doc.status = "Draft"
        doc.total_qty_required = self.total_qty

        for r in self.items:
            item = item_map[r.item_code]
            doc.append("items", {
                "item_code": r.item_code,
                "item_name": item.item_name,
                "qty_required": r.qty_requested,
                "uom": item.stock_uom,
                "stock_uom": item.stock_uom
            })

        doc.insert(ignore_permissions=True)
        self.db_set("fulfillment_order", doc.name)
        return doc

    def create_distribution_order(self):
        if self.distribution_order:
            return frappe.get_doc("OMS Distribution Order", self.distribution_order)

        source_wh = get_warehouse_from_facility(self.source_facility)
        dest_wh = get_warehouse_from_facility(self.requesting_facility)

        items = frappe.get_all(
            "Item",
            filters={"name": ["in", [d.item_code for d in self.items]]},
            fields=["name", "item_name", "stock_uom", "valuation_rate"]
        )
        item_map = {i.name: i for i in items}

        total_qty = 0
        total_value = 0

        doc = frappe.new_doc("OMS Distribution Order")
        doc.naming_series = "DST-.YYYY.-.#####"
        doc.company = self.company
        doc.distribution_type = "Emergency Deployment"
        doc.source_warehouse = source_wh
        doc.distribution_date = today()
        doc.status = "Draft"
        doc.total_facilities = 1

        for r in self.items:
            item = item_map[r.item_code]
            qty = r.qty_requested
            rate = item.valuation_rate or 0

            total_qty += qty
            total_value += qty * rate

            doc.append("items", {
                "item_code": r.item_code,
                "item_name": item.item_name,
                "facility": dest_wh,
                "qty_to_distribute": qty,
                "qty_dispatched": 0,
                "qty_received": 0,
                "uom": item.stock_uom,
                "stock_uom": item.stock_uom,
                "status": "Pending"
            })

        doc.total_qty = total_qty
        doc.total_value = total_value

        doc.insert(ignore_permissions=True)
        self.db_set("distribution_order", doc.name)
        return doc

    def link_distribution_to_fulfillment(self, fulfillment, distribution):
        if fulfillment and distribution:
            fulfillment.db_set("distribution_order", distribution.name)

    def create_material_request(self):
        if self.material_request:
            return

        from_wh = get_warehouse_from_facility(self.source_facility)
        to_wh = get_warehouse_from_facility(self.requesting_facility)

        department = frappe.db.get_value(
            "Department",
            {"company": self.company},
            "name"
        )

        items = frappe.get_all(
            "Item",
            filters={"name": ["in", [d.item_code for d in self.items]]},
            fields=["name", "item_name", "stock_uom"]
        )
        item_map = {i.name: i for i in items}

        mr = frappe.new_doc("Material Request")
        mr.material_request_type = "Material Transfer"
        mr.company = self.company
        mr.schedule_date = self.required_by_date
        mr.from_warehouse = from_wh
        mr.to_warehouse = to_wh
        mr.set_warehouse = to_wh
        mr.custom_for_department = department

        for r in self.items:
            item = item_map[r.item_code]

            mr.append("items", {
                "item_code": r.item_code,
                "qty": r.qty_requested,
                "schedule_date": self.required_by_date
            })

            mr.append("custom_material_transfer_items", {
                "item_code": r.item_code,
                "item_name": item.item_name,
                "uom": item.stock_uom,
                "req_qty": r.qty_requested
            })

        mr.insert(ignore_permissions=True)
        self.db_set("material_request", mr.name)

    def create_consumption_forecast(self):
        if self.consumption_reference:
            return

        r = self.items[0]

        doc = frappe.new_doc("OMS Consumption Forecast")
        doc.naming_series = "FCT-.YYYY.-.#####"
        doc.facility = self.requesting_facility
        doc.item_code = r.item_code
        doc.forecast_date = today()
        doc.forecast_horizon_days = 30
        doc.forecast_method = "Manual"
        doc.forecast_qty = r.qty_requested
        doc.reorder_point = r.qty_requested
        doc.requisition_generated = self.name

        doc.insert(ignore_permissions=True)
        doc.submit()
        self.db_set("consumption_reference", doc.name)