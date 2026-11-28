from langchain_core.tools import tool

from common.db import as_json, fetch

AUTO_APPROVE_LIMIT = 5000.0  # POs above this total need a human


@tool
def low_stock_report() -> str:
    """Products whose available stock (on hand + on order) is at or below their reorder point."""
    return as_json(
        fetch(
            "SELECT p.id, p.sku, p.name, p.stock_on_hand, p.on_order, p.reorder_point, p.unit_cost, "
            "s.id AS supplier_id, s.name AS supplier "
            "FROM inventory.products p JOIN inventory.suppliers s ON s.id=p.supplier_id "
            "WHERE p.stock_on_hand + p.on_order <= p.reorder_point ORDER BY p.id"
        )
    )


@tool
def get_stock(sku: str) -> str:
    """Stock levels for a single SKU."""
    rows = fetch("SELECT sku, name, stock_on_hand, on_order, reorder_point FROM inventory.products WHERE sku=?", (sku,))
    return as_json(rows[0]) if rows else "Unknown SKU."


@tool
def forecast_demand(product_id: int, weeks_ahead: int = 6) -> str:
    """Forecast units needed over the next N weeks: linear trend over the last 12 weeks of
    history (least squares), never below zero. Also returns the recent weekly average."""
    rows = fetch(
        "SELECT week_start, units FROM inventory.demand_history WHERE product_id=? ORDER BY week_start",
        (product_id,),
    )
    if len(rows) < 4:
        return "Not enough history to forecast."
    ys = [r["units"] for r in rows]
    n = len(ys)
    xs = list(range(n))
    mx, my = sum(xs) / n, sum(ys) / n
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    intercept = my - slope * mx
    future = [max(0.0, intercept + slope * (n + k)) for k in range(weeks_ahead)]
    return as_json(
        {"product_id": product_id, "weekly_avg_last_12": round(my, 1), "trend_per_week": round(slope, 2),
         "forecast_units_total": round(sum(future)), "weeks": weeks_ahead}
    )


@tool
def get_supplier(supplier_id: int) -> str:
    """Supplier lead time and minimum order value."""
    rows = fetch("SELECT id, name, lead_time_days, min_order_value FROM inventory.suppliers WHERE id=?", (supplier_id,))
    return as_json(rows[0]) if rows else "Unknown supplier."


@tool
def create_purchase_order(supplier_id: int, lines: list[dict]) -> str:
    """Create a DRAFT purchase order (status pending_approval) for ONE supplier.
    lines: [{"product_id": int, "qty": int}, ...]. Unit cost comes from the catalogue.
    The order is not sent to the supplier until the approver signs it off."""
    if not lines:
        return "No lines given."
    total, priced = 0.0, []
    for ln in lines:
        p = fetch("SELECT id, unit_cost, supplier_id FROM inventory.products WHERE id=?", (ln["product_id"],))
        if not p or p[0]["supplier_id"] != supplier_id:
            return f"Product {ln['product_id']} does not belong to supplier {supplier_id}."
        if int(ln["qty"]) <= 0:
            return "Quantities must be positive."
        total += float(p[0]["unit_cost"]) * int(ln["qty"])
        priced.append((ln["product_id"], int(ln["qty"]), p[0]["unit_cost"]))
    sup = fetch("SELECT min_order_value FROM inventory.suppliers WHERE id=?", (supplier_id,))[0]
    if total < float(sup["min_order_value"]):
        return f"Order total {total:.2f} is below the supplier minimum {float(sup['min_order_value']):.2f}. Increase quantities."
    po = fetch("INSERT INTO inventory.purchase_orders (supplier_id, total) VALUES (?,?) RETURNING id", (supplier_id, total))[0]
    for pid, qty, cost in priced:
        fetch("INSERT INTO inventory.po_lines (po_id, product_id, qty, unit_cost) VALUES (?,?,?,?)", (po["id"], pid, qty, cost))
    return f"Draft PO #{po['id']} created, total {total:.2f}."


CHECKER_TOOLS = [low_stock_report, get_stock]
FORECASTER_TOOLS = [forecast_demand]
BUYER_TOOLS = [get_supplier, create_purchase_order]
