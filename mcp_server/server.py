"""Campus Customs MCP server.

The only way into the shop's books (data/campus_customs_new.db). Two kinds of
tools:

  * Read tools: lookups the agents use to work tickets. They open the
    database read-only.
  * Action tools: payments, vendor orders, price overrides, customer messages,
    ticket updates, and the reset. No agent is given these; the runner calls
    them only after a human approves, and every one requires `approved_by`.

Shop rules are enforced here, not just in prompts:
  * No revenue is modeled: no tool ever increases cash.
  * Cash can never go negative.
  * A vendor will not ship while it has any unpaid invoice.
  * A price override can never go below unit cost.
"""

import calendar
import os
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = Path(os.environ.get("CAMPUS_CUSTOMS_DB", DATA_DIR / "campus_customs_new.db"))
ORIGINAL_DB_PATH = Path(os.environ.get("CAMPUS_CUSTOMS_ORIGINAL_DB", DATA_DIR / "campus_customs.db"))

CASH_ACCOUNT = "checking"
REVENUE_NOTE = "No revenue is modeled: sales, quotes, and deposits never add cash."
# Rent counts as owed once it is due within this many days (or overdue). Next month's rent,
# which appears as soon as this month's is paid, isn't owed yet.
OBLIGATION_WINDOW_DAYS = 30

mcp = FastMCP("campus-customs")


def _connect(write: bool = False) -> sqlite3.Connection:
    mode = "rw" if write else "ro"
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode={mode}", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _today(conn: sqlite3.Connection) -> date:
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return date.fromisoformat(row["date_today"])


def _balance(conn: sqlite3.Connection) -> float:
    return conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (CASH_ACCOUNT,)).fetchone()["balance"]


def _open_invoices(conn: sqlite3.Connection, today: date, vendor_id: int | None = None) -> list[dict]:
    sql = "SELECT id FROM invoices WHERE status = 'open'"
    args: tuple = ()
    if vendor_id is not None:
        sql += " AND vendor_id = ?"
        args = (vendor_id,)
    return [_invoice(conn, r["id"], today) for r in conn.execute(sql + " ORDER BY due_date", args)]


def _upcoming_rent(conn: sqlite3.Connection, today: date) -> list[dict]:
    rows = conn.execute("SELECT id AS lease_id, space_name, landlord, monthly_rent, next_due FROM leases")
    result = []
    for r in rows:
        days = (date.fromisoformat(r["next_due"]) - today).days
        result.append({**dict(r), "days_until_due": days, "counted_as_owed": days <= OBLIGATION_WINDOW_DAYS})
    return result


def _committed(conn: sqlite3.Connection, today: date) -> float:
    return sum(i["amount"] for i in _open_invoices(conn, today)) + sum(
        r["monthly_rent"] for r in _upcoming_rent(conn, today) if r["counted_as_owed"]
    )


def _invoice(conn: sqlite3.Connection, invoice_id: int, today: date) -> dict | None:
    row = conn.execute(
        "SELECT i.*, v.name AS vendor_name, v.specialty AS vendor_specialty, v.lead_days "
        "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
        (invoice_id,),
    ).fetchone()
    if row is None:
        return None
    due = date.fromisoformat(row["due_date"])
    return {
        **dict(row),
        "overdue": row["status"] == "open" and due < today,
        "days_past_due": max(0, (today - due).days) if row["status"] == "open" else 0,
    }


def _quote(sku: str, qty: int, discount_pct: float) -> dict:
    if not 0 <= discount_pct < 100:
        return {"error": "discount_pct must be between 0 and 100"}
    if qty <= 0:
        return {"error": "qty must be positive"}
    with _connect() as conn:
        row = conn.execute(
            "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
    if row is None:
        return {"error": f"No pricing for sku={sku!r}"}
    list_total = row["list_price"] * qty
    unit_price = round(row["list_price"] * (1 - discount_pct / 100), 2)
    quoted_total = round(unit_price * qty, 2)
    cost_total = row["unit_cost"] * qty
    margin = round(quoted_total - cost_total, 2)
    return {
        "sku": row["sku"],
        "qty": qty,
        "list_price": row["list_price"],
        "unit_cost": row["unit_cost"],
        "discount_pct": discount_pct,
        "unit_price_quoted": unit_price,
        "list_total": list_total,
        "quoted_total": quoted_total,
        "discount_amount": round(list_total - quoted_total, 2),
        "cost_total": cost_total,
        "gross_margin": margin,
        "gross_margin_pct": round(100 * margin / quoted_total, 1) if quoted_total else None,
        "below_cost": unit_price < row["unit_cost"],
        "max_discount_pct_at_cost": round(100 * (1 - row["unit_cost"] / row["list_price"]), 1),
        "note": REVENUE_NOTE,
    }


def _require_approver(approved_by: str) -> dict | None:
    if not approved_by or not approved_by.strip():
        return {"ok": False, "error": "approved_by is required: a named human must approve this action."}
    return None


def _debit(conn: sqlite3.Connection, today: date, kind: str, ref_id: int, amount: float, approved_by: str) -> dict:
    """Take money out of checking. The only code path that changes cash."""
    if amount <= 0:
        raise ValueError("Payment amount must be positive (cash never goes in).")
    balance = _balance(conn)
    if amount > balance:
        raise ValueError(f"Refused: paying ${amount:,.2f} from ${balance:,.2f} would make cash negative.")
    conn.execute(
        "UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = ?",
        (amount, today.isoformat(), CASH_ACCOUNT),
    )
    cur = conn.execute(
        "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
        (kind, ref_id, amount, CASH_ACCOUNT, today.isoformat(), approved_by.strip()),
    )
    return {"payment_id": cur.lastrowid, "balance_before": balance, "balance_after": balance - amount}


def _add_ticket_note(conn: sqlite3.Connection, ticket_id: int, note: str) -> bool:
    row = conn.execute("SELECT notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        return False
    notes = f"{row['notes']}\n{note}" if row["notes"] else note
    conn.execute("UPDATE tickets SET notes = ? WHERE id = ?", (notes, ticket_id))
    return True


def _add_month(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return d.replace(year=year, month=month, day=min(d.day, calendar.monthrange(year, month)[1]))


# =============================================================================
# Read tools (given to agents)
# =============================================================================

# --- Tickets -----------------------------------------------------------------


@mcp.tool
def list_open_tickets() -> list[dict]:
    """List every open ticket (id, type, requester, subject, created_at)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, type, requester, subject, created_at FROM tickets "
            "WHERE status = 'open' ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


@mcp.tool
def list_payments() -> list[dict]:
    """List every payment out of checking since the last reset, oldest first.

    Each payment says what it paid (invoice, vendor order, or rent), which
    ticket it belongs to when the database links one, and who approved it.
    Cash only changes through payments, so the balance at the last reset is
    the current balance plus every payment listed here.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT p.id, p.kind, p.ref_id, p.amount, p.paid_at, p.approved_by, "
            "i.description AS invoice_description, v.name AS vendor_name, l.space_name, "
            "COALESCE(ti.id, tl.id) AS ticket_id "
            "FROM payments p "
            "LEFT JOIN invoices i ON p.kind IN ('invoice', 'purchase_order') AND i.id = p.ref_id "
            "LEFT JOIN vendors v ON v.id = i.vendor_id "
            "LEFT JOIN leases l ON p.kind = 'rent' AND l.id = p.ref_id "
            "LEFT JOIN tickets ti ON p.kind = 'invoice' AND ti.invoice_id = p.ref_id "
            "LEFT JOIN tickets tl ON p.kind = 'rent' AND tl.lease_id = p.ref_id "
            "ORDER BY p.id"
        ).fetchall()
    payments = []
    for r in rows:
        if r["kind"] == "rent":
            label = f"Rent · {r['space_name']}"
        elif r["kind"] == "invoice":
            label = f"Invoice {r['ref_id']} · {r['vendor_name']}"
        else:
            desc = (r["invoice_description"] or "").split(" (approved by")[0]
            label = desc.replace("Prepaid order", "Vendor order ·") if desc else f"Vendor order · invoice {r['ref_id']}"
        payments.append({
            "id": r["id"], "kind": r["kind"], "ref_id": r["ref_id"], "amount": r["amount"],
            "paid_at": r["paid_at"], "approved_by": r["approved_by"], "ticket_id": r["ticket_id"], "label": label,
        })
    return payments


@mcp.tool
def list_tickets() -> list[dict]:
    """List every ticket, whatever its status (open, waiting, resolved).

    `request` is the original request text: the ticket's notes before any
    approved message or status change was appended (those start "[date] ").
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, created_at, notes "
            "FROM tickets ORDER BY id"
        ).fetchall()
    tickets = []
    for r in rows:
        t = dict(r)
        t["request"] = _ORIGINAL_REQUEST.split(t.pop("notes") or "", maxsplit=1)[0].strip()
        tickets.append(t)
    return tickets


# Notes appended after a ticket is opened always start on a new line with "[YYYY-MM-DD] ".
_ORIGINAL_REQUEST = re.compile(r"\n\[\d{4}-\d{2}-\d{2}\] ")


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Get one ticket with everything it links to.

    Includes the ticket row, plus the linked lease, linked invoice (with vendor
    and overdue flag), and the inventory/pricing rows for its sku/size, when
    present. Use this first when triaging a ticket.
    """
    with _connect() as conn:
        today = _today(conn)
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            return {"error": f"No ticket with id={ticket_id}"}
        result = {"today": today.isoformat(), "ticket": dict(ticket)}
        if ticket["lease_id"] is not None:
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)).fetchone()
            result["lease"] = dict(lease) if lease else None
        if ticket["invoice_id"] is not None:
            result["invoice"] = _invoice(conn, ticket["invoice_id"], today)
        if ticket["sku"] is not None:
            inv = conn.execute(
                "SELECT * FROM inventory WHERE sku = ? AND size = ?", (ticket["sku"], ticket["size"])
            ).fetchone()
            price = conn.execute("SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],)).fetchone()
            result["inventory"] = dict(inv) if inv else None
            result["pricing"] = dict(price) if price else None
    return result


# --- Products and vendors ----------------------------------------------------


@mcp.tool
def get_product_details(sku: str) -> dict:
    """Describe a product: name, list price, unit cost, and stock by size.

    Use for product questions (what it is, which sizes exist, what it costs)
    rather than a single size/quantity check.
    """
    with _connect() as conn:
        sizes = conn.execute(
            "SELECT name, size, qty, location FROM inventory WHERE sku = ?", (sku,)
        ).fetchall()
        price = conn.execute("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)).fetchone()
    if not sizes and price is None:
        return {"error": f"No product with sku={sku!r}"}
    return {
        "sku": sku,
        "name": sizes[0]["name"] if sizes else None,
        "list_price": price["list_price"] if price else None,
        "unit_cost": price["unit_cost"] if price else None,
        "stock_by_size": [
            {"size": s["size"], "qty": s["qty"], "location": s["location"]} for s in sizes
        ],
        "total_on_hand": sum(s["qty"] for s in sizes),
    }


@mcp.tool
def check_stock(sku: str, size: str, qty_needed: int = 1) -> dict:
    """Check whether a SKU/size can be filled from shelf stock.

    Returns units on hand, shelf location, whether the requested quantity can
    ship now, and the shortfall (units that would need a reprint/reorder).
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
    if row is None:
        return {"error": f"No inventory row for sku={sku!r}, size={size!r}"}
    on_hand = row["qty"]
    return {
        "sku": row["sku"],
        "name": row["name"],
        "size": row["size"],
        "location": row["location"],
        "on_hand": on_hand,
        "qty_needed": qty_needed,
        "can_fill_now": on_hand >= qty_needed,
        "shortfall": max(0, qty_needed - on_hand),
    }


@mcp.tool
def list_vendors() -> list[dict]:
    """List vendors with their specialty and lead time in days (for restock/reprint planning)."""
    with _connect() as conn:
        rows = conn.execute("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@mcp.tool
def check_vendor_can_ship(vendor_id: int) -> dict:
    """Check whether a vendor will ship. Vendors never ship while they have an unpaid invoice.

    Returns the vendor, every unpaid invoice it holds, the balance owed, and
    `can_ship`. If `can_ship` is false, the unpaid invoices must be paid
    (with human approval) before any order or reprint from this vendor can
    ship, so no delivery date can be promised yet.
    """
    with _connect() as conn:
        today = _today(conn)
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            return {"error": f"No vendor with id={vendor_id}"}
        unpaid = _open_invoices(conn, today, vendor_id)
    owed = sum(i["amount"] for i in unpaid)
    return {
        "today": today.isoformat(),
        "vendor_id": vendor["id"],
        "vendor_name": vendor["name"],
        "specialty": vendor["specialty"],
        "lead_days": vendor["lead_days"],
        "unpaid_invoices": unpaid,
        "balance_owed": owed,
        "can_ship": not unpaid,
        "reason": "No unpaid invoices." if not unpaid else (
            f"Blocked: {len(unpaid)} unpaid invoice(s) totaling ${owed:,.2f}. "
            "The vendor will not ship until these are paid."
        ),
    }


# --- Finance -----------------------------------------------------------------


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """Get a vendor invoice with vendor name, status, and how many days overdue it is."""
    with _connect() as conn:
        result = _invoice(conn, invoice_id, _today(conn))
    return result or {"error": f"No invoice with id={invoice_id}"}


@mcp.tool
def get_cash_position() -> dict:
    """Get cash on hand and everything committed against it.

    Returns every cash account balance, all open vendor invoices (overdue
    flagged), the next rent on every lease, and the balance left once every
    obligation is paid: open invoices plus rent due within 30 days (or overdue).
    Cash only goes down: no revenue is modeled.
    """
    with _connect() as conn:
        today = _today(conn)
        accounts = [dict(r) for r in conn.execute("SELECT name, balance, date FROM cash_accounts")]
        invoices = _open_invoices(conn, today)
        rent = _upcoming_rent(conn, today)
    cash = sum(a["balance"] for a in accounts)
    committed = sum(i["amount"] for i in invoices) + sum(r["monthly_rent"] for r in rent if r["counted_as_owed"])
    return {
        "today": today.isoformat(),
        "accounts": accounts,
        "total_cash": cash,
        "open_invoices": invoices,
        "upcoming_rent": rent,
        "total_committed": committed,
        "cash_after_all_obligations": cash - committed,
        "can_cover_all_obligations": cash >= committed,
        "obligation_window_days": OBLIGATION_WINDOW_DAYS,
        "note": REVENUE_NOTE,
    }


@mcp.tool
def preview_payment(amount: float, covers_existing_obligation: bool = True) -> dict:
    """Dry-run a payment: would it be allowed, and what would be left?

    Args:
        amount: Dollars that would leave checking.
        covers_existing_obligation: True if this pays an open invoice or rent
            already counted in obligations; False for new spending (e.g. a
            new vendor order), which must not crowd out existing obligations.

    Cash can never go negative, and no revenue is modeled, so nothing will
    replenish it. Nothing is changed.
    """
    if amount <= 0:
        return {"error": "amount must be positive"}
    with _connect() as conn:
        today = _today(conn)
        balance = _balance(conn)
        committed = _committed(conn, today)
    after = balance - amount
    remaining_obligations = committed - amount if covers_existing_obligation else committed
    allowed = after >= 0 and (covers_existing_obligation or after >= committed)
    if after < 0:
        reason = f"Refused: would make cash negative by ${-after:,.2f}."
    elif not allowed:
        reason = (
            f"Refused: leaves ${after:,.2f}, which cannot cover the ${committed:,.2f} "
            "of open invoices and rent already owed."
        )
    else:
        reason = "Allowed."
    return {
        "today": today.isoformat(),
        "balance_before": balance,
        "amount": amount,
        "balance_after": after,
        "obligations_still_owed_after": max(0.0, remaining_obligations),
        "cash_after_all_remaining_obligations": after - max(0.0, remaining_obligations),
        "allowed": allowed,
        "reason": reason,
        "note": REVENUE_NOTE,
    }


@mcp.tool
def check_rent_affordability(lease_id: int) -> dict:
    """Check whether the shop can pay the next rent on a lease.

    Compares the rent due against the checking balance, and also shows open
    vendor invoices competing for the same cash, so the agent can see what is
    left after paying rent alone and after paying rent plus all open invoices.
    """
    with _connect() as conn:
        today = _today(conn)
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            return {"error": f"No lease with id={lease_id}"}
        cash = conn.execute(
            "SELECT name, balance, date FROM cash_accounts WHERE name = ?", (CASH_ACCOUNT,)
        ).fetchone()
        open_invoices = _open_invoices(conn, today)

    rent = lease["monthly_rent"]
    balance = cash["balance"]
    open_total = sum(inv["amount"] for inv in open_invoices)
    return {
        "today": today.isoformat(),
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "rent_due": rent,
        "due_date": lease["next_due"],
        "days_until_due": (date.fromisoformat(lease["next_due"]) - today).days,
        "checking_balance": balance,
        "balance_as_of": cash["date"],
        "can_pay_rent": balance >= rent,
        "balance_after_rent": balance - rent,
        "open_invoices": open_invoices,
        "open_invoices_total": open_total,
        "balance_after_rent_and_open_invoices": balance - rent - open_total,
        "note": REVENUE_NOTE,
    }


@mcp.tool
def quote_bulk_order(sku: str, qty: int, discount_pct: float = 0.0) -> dict:
    """Price a bulk order at an optional discount and show the resulting margin.

    Returns the list-price total, discounted total, total unit cost, and the
    gross margin in dollars and percent, so the agent can judge whether a
    requested discount still leaves the sale profitable. A quote is not cash:
    no revenue is modeled.
    """
    return _quote(sku, qty, discount_pct)


# --- Facilities --------------------------------------------------------------


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """Get a lease: space, landlord, monthly rent, next due date, and days until due."""
    with _connect() as conn:
        today = _today(conn)
        row = conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
    if row is None:
        return {"error": f"No lease with id={lease_id}"}
    return {
        **dict(row),
        "today": today.isoformat(),
        "days_until_due": (date.fromisoformat(row["next_due"]) - today).days,
    }


# =============================================================================
# Action tools (runner only, after human approval)
# =============================================================================


@mcp.tool
def pay_invoice(invoice_id: int, approved_by: str) -> dict:
    """Pay an open vendor invoice in full from checking. Requires human approval.

    Refused if the invoice isn't open or if paying it would make cash negative.
    """
    if err := _require_approver(approved_by):
        return err
    with _connect(write=True) as conn:
        today = _today(conn)
        inv = _invoice(conn, invoice_id, today)
        if inv is None:
            return {"ok": False, "error": f"No invoice with id={invoice_id}"}
        if inv["status"] != "open":
            return {"ok": False, "error": f"Invoice {invoice_id} is {inv['status']}, not open."}
        try:
            paid = _debit(conn, today, "invoice", invoice_id, inv["amount"], approved_by)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (invoice_id,))
        vendor_clear = not _open_invoices(conn, today, inv["vendor_id"])
    return {
        "ok": True,
        "invoice_id": invoice_id,
        "vendor": inv["vendor_name"],
        "amount": inv["amount"],
        **paid,
        "vendor_can_ship_now": vendor_clear,
    }


@mcp.tool
def pay_rent(lease_id: int, approved_by: str) -> dict:
    """Pay the next month's rent on a lease from checking. Requires human approval.

    Refused if paying would make cash negative. Advances the lease's next due
    date by one month.
    """
    if err := _require_approver(approved_by):
        return err
    with _connect(write=True) as conn:
        today = _today(conn)
        lease = conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
        if lease is None:
            return {"ok": False, "error": f"No lease with id={lease_id}"}
        try:
            paid = _debit(conn, today, "rent", lease_id, lease["monthly_rent"], approved_by)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        next_due = _add_month(date.fromisoformat(lease["next_due"])).isoformat()
        conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, lease_id))
    return {
        "ok": True,
        "lease_id": lease_id,
        "landlord": lease["landlord"],
        "amount": lease["monthly_rent"],
        "paid_for_due_date": lease["next_due"],
        "new_next_due": next_due,
        **paid,
    }


@mcp.tool
def place_vendor_order(vendor_id: int, sku: str, size: str, qty: int, approved_by: str) -> dict:
    """Place a prepaid restock/reprint order with a vendor. Requires human approval.

    Refused if the vendor has any unpaid invoice (it will not ship), if the
    cost would make cash negative, or if it would leave too little cash for
    open invoices and rent already owed. The order is prepaid at unit cost so
    the vendor holds no balance; stock arrives after the vendor's lead time.
    """
    if err := _require_approver(approved_by):
        return err
    if qty <= 0:
        return {"ok": False, "error": "qty must be positive"}
    with _connect(write=True) as conn:
        today = _today(conn)
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            return {"ok": False, "error": f"No vendor with id={vendor_id}"}
        unpaid = _open_invoices(conn, today, vendor_id)
        if unpaid:
            owed = sum(i["amount"] for i in unpaid)
            return {
                "ok": False,
                "error": f"Refused: {vendor['name']} has unpaid invoice(s) totaling ${owed:,.2f} "
                f"(ids {[i['id'] for i in unpaid]}) and will not ship until they are paid.",
            }
        if conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone() is None:
            return {"ok": False, "error": f"No inventory row for sku={sku!r}, size={size!r}"}
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if price is None:
            return {"ok": False, "error": f"No pricing for sku={sku!r}"}
        cost = round(price["unit_cost"] * qty, 2)
        balance, committed = _balance(conn), _committed(conn, today)
        if balance - cost < committed:
            return {
                "ok": False,
                "error": f"Refused: ${cost:,.2f} order would leave ${balance - cost:,.2f}, "
                f"less than the ${committed:,.2f} of open invoices and rent already owed.",
            }
        cur = conn.execute(
            "INSERT INTO invoices (vendor_id, amount, due_date, status, description) VALUES (?, ?, ?, 'open', ?)",
            (vendor_id, cost, today.isoformat(), f"Prepaid order {qty} x {sku} {size} (approved by {approved_by.strip()})"),
        )
        invoice_id = cur.lastrowid
        try:
            paid = _debit(conn, today, "purchase_order", invoice_id, cost, approved_by)
        except ValueError as e:
            conn.rollback()
            return {"ok": False, "error": str(e)}
        conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (invoice_id,))
    return {
        "ok": True,
        "invoice_id": invoice_id,
        "vendor": vendor["name"],
        "sku": sku,
        "size": size,
        "qty": qty,
        "cost": cost,
        **paid,
        "expected_arrival": (today + timedelta(days=vendor["lead_days"])).isoformat(),
    }


@mcp.tool
def approve_price_override(ticket_id: int, discount_pct: float, approved_by: str) -> dict:
    """Record an approved discount on a price-override ticket. Requires human approval.

    Refused if the discounted unit price would fall below unit cost. Records
    the approved terms on the ticket; does not change cash (no revenue modeled).
    """
    if err := _require_approver(approved_by):
        return err
    with _connect(write=True) as conn:
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None or ticket["sku"] is None or ticket["qty"] is None:
            return {"ok": False, "error": f"Ticket {ticket_id} has no sku/qty to price."}
        quote = _quote(ticket["sku"], ticket["qty"], discount_pct)
        if "error" in quote:
            return {"ok": False, **quote}
        if quote["below_cost"]:
            return {
                "ok": False,
                "error": f"Refused: {discount_pct}% puts the unit price (${quote['unit_price_quoted']:.2f}) "
                f"below unit cost (${quote['unit_cost']:.2f}). Max is {quote['max_discount_pct_at_cost']}%.",
            }
        today = _today(conn)
        _add_ticket_note(
            conn,
            ticket_id,
            f"[{today}] Price override approved by {approved_by.strip()}: {discount_pct}% off, "
            f"${quote['unit_price_quoted']:.2f}/unit, ${quote['quoted_total']:,.2f} total.",
        )
    return {"ok": True, "ticket_id": ticket_id, **quote}


@mcp.tool
def send_customer_message(ticket_id: int, to: str, subject: str, body: str, approved_by: str) -> dict:
    """Send (record) an approved customer-facing message on a ticket. Requires human approval."""
    if err := _require_approver(approved_by):
        return err
    with _connect(write=True) as conn:
        today = _today(conn)
        note = f"[{today}] Message sent to {to} (approved by {approved_by.strip()}). Subject: {subject}\n{body}"
        if not _add_ticket_note(conn, ticket_id, note):
            return {"ok": False, "error": f"No ticket with id={ticket_id}"}
    return {"ok": True, "ticket_id": ticket_id, "to": to, "subject": subject, "sent_on": today.isoformat()}


@mcp.tool
def update_ticket_status(ticket_id: int, status: str, note: str, approved_by: str) -> dict:
    """Change a ticket's status (open, waiting, resolved) with a note. Requires human approval."""
    if err := _require_approver(approved_by):
        return err
    if status not in {"open", "waiting", "resolved"}:
        return {"ok": False, "error": "status must be one of: open, waiting, resolved"}
    with _connect(write=True) as conn:
        today = _today(conn)
        if not _add_ticket_note(conn, ticket_id, f"[{today}] Status -> {status} (approved by {approved_by.strip()}): {note}"):
            return {"ok": False, "error": f"No ticket with id={ticket_id}"}
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
    return {"ok": True, "ticket_id": ticket_id, "status": status}


@mcp.tool
def reset_database() -> dict:
    """Restore the working database to the original values (runner only, before a full run)."""
    src = sqlite3.connect(f"file:{ORIGINAL_DB_PATH.as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(DB_PATH)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()
    with _connect() as conn:
        tickets = conn.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'").fetchone()[0]
        balance = _balance(conn)
    return {"ok": True, "restored_from": ORIGINAL_DB_PATH.name, "open_tickets": tickets, "checking_balance": balance}


if __name__ == "__main__":
    mcp.run(show_banner=False)
