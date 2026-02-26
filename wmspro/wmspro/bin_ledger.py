import frappe


def get_bin_balance(bin_location, item_code, batch_no=None):

    filters = {
        "bin_location": bin_location,
        "item_code": item_code,
        "is_cancelled": 0
    }

    if batch_no:
        filters["batch_no"] = batch_no

    latest = frappe.db.get_value(
        "WMS Bin Ledger",
        filters,
        ["balance_qty", "reserved_qty", "available_qty"],
        order_by="posting_datetime desc"
    )

    if not latest:
        return {"balance": 0, "reserved": 0, "available": 0}

    return {
        "balance": latest[0] or 0,
        "reserved": latest[1] or 0,
        "available": latest[2] or 0
    }


def create_bin_ledger_entry(
    bin_location,
    item_code,
    qty_change,
    warehouse=None,
    batch_no=None,
    voucher_type=None,
    voucher_no=None,
    is_reservation=0
):

    if not qty_change:
        return

    bin_doc = frappe.get_doc("WMS Bin", bin_location)

    current = get_bin_balance(bin_location, item_code, batch_no)

    new_balance = current["balance"] + qty_change

    if new_balance < 0:
        frappe.throw(f"Insufficient stock in {bin_location}")

    entry = frappe.get_doc({
        "doctype": "WMS Bin Ledger",
        "posting_date": frappe.utils.today(),
        "posting_time": frappe.utils.nowtime(),
        "warehouse": warehouse or bin_doc.warehouse,
        "bin_location": bin_location,
        "zone": bin_doc.zone,
        "item_code": item_code,
        "batch_no": batch_no,
        "quantity_change": qty_change,
        "balance_qty": new_balance,
        "reserved_qty": current["reserved"],
        "available_qty": new_balance - current["reserved"],
        "stock_uom": frappe.db.get_value("Item", item_code, "stock_uom"),
        "voucher_type": voucher_type,
        "voucher_no": voucher_no,
        "is_reservation": is_reservation,
    })

    entry.insert(ignore_permissions=True)


def reserve_stock(bin_location, item_code, qty_to_reserve,
                  batch_no=None, voucher_type=None, voucher_no=None):

    current = get_bin_balance(bin_location, item_code, batch_no)

    if current["available"] < qty_to_reserve:
        frappe.throw("Insufficient available stock")

    entry = frappe.get_doc({
        "doctype": "WMS Bin Ledger",
        "bin_location": bin_location,
        "item_code": item_code,
        "batch_no": batch_no,
        "qty_change": 0,
        "balance_qty": current["balance"],
        "reserved_qty": current["reserved"] + qty_to_reserve,
        "is_reservation": 1,
        "voucher_type": voucher_type,
        "voucher_no": voucher_no,
    })

    entry.insert(ignore_permissions=True)