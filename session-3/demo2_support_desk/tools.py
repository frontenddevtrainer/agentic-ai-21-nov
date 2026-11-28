from langchain_core.tools import tool
from langgraph.types import interrupt

from common.db import as_json, fetch


@tool
def lookup_customer(email: str) -> str:
    """Find a customer by email address. Returns id, name and plan."""
    rows = fetch("SELECT id, email, name, plan FROM support.customers WHERE lower(email)=lower(?)", (email,))
    return as_json(rows[0]) if rows else "No customer with that email."


@tool
def list_orders(customer_id: int) -> str:
    """List all orders for a customer id."""
    return as_json(
        fetch(
            "SELECT id, item, total, status, placed_at, tracking FROM support.orders "
            "WHERE customer_id=? ORDER BY placed_at DESC",
            (customer_id,),
        )
    )


@tool
def get_order(order_id: int) -> str:
    """Details for one order, including how much has already been refunded."""
    rows = fetch(
        "SELECT o.id, o.customer_id, o.item, o.total, o.status, o.placed_at, o.tracking, "
        "COALESCE((SELECT sum(amount) FROM support.refunds r WHERE r.order_id=o.id),0) AS refunded "
        "FROM support.orders o WHERE o.id=?",
        (order_id,),
    )
    return as_json(rows[0]) if rows else "No such order."


@tool
def create_ticket(customer_id: int, category: str, summary: str, priority: str = "normal") -> str:
    """Open a support ticket. category: billing|orders|other. priority: normal|high."""
    row = fetch(
        "INSERT INTO support.tickets (customer_id, category, priority, summary) "
        "VALUES (?,?,?,?) RETURNING id",
        (customer_id, category, priority, summary),
    )[0]
    return f"Ticket #{row['id']} created ({priority})."


@tool
def issue_refund(order_id: int, amount: float, reason: str) -> str:
    """Refund part or all of an order. A human must approve every refund first;
    this tool pauses the whole graph until they answer."""
    rows = fetch(
        "SELECT total, COALESCE((SELECT sum(amount) FROM support.refunds WHERE order_id=?),0) AS refunded "
        "FROM support.orders WHERE id=?",
        (order_id, order_id),
    )
    if not rows:
        return "No such order."
    remaining = float(rows[0]["total"]) - float(rows[0]["refunded"])
    if amount <= 0 or amount > remaining + 1e-9:
        return f"Refund rejected: amount must be between 0 and the remaining {remaining:.2f}."

    # ---- Human-in-the-loop -------------------------------------------------
    # interrupt() saves the graph to the SQLite checkpointer and stops. When the
    # caller resumes with Command(resume=...), this tool re-runs and interrupt()
    # returns the human's answer. Everything above is read-only, so re-running is safe.
    decision = interrupt(
        {"action": "refund", "order_id": order_id, "amount": amount, "reason": reason, "remaining": remaining}
    )
    if not decision.get("approved"):
        return f"Refund NOT approved by {decision.get('by', 'a human')}. Tell the customer and offer a ticket."

    fetch(
        "INSERT INTO support.refunds (order_id, amount, reason, approved_by) VALUES (?,?,?,?)",
        (order_id, amount, reason, decision.get("by", "human")),
    )
    if abs(amount - remaining) < 1e-9:
        fetch("UPDATE support.orders SET status='refunded' WHERE id=?", (order_id,))
    return f"Refund of {amount:.2f} for order {order_id} approved and recorded."


ORDER_TOOLS = [lookup_customer, list_orders, get_order, create_ticket]
BILLING_TOOLS = [lookup_customer, list_orders, get_order, issue_refund]
ESCALATION_TOOLS = [lookup_customer, create_ticket]
