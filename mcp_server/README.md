# Campus Customs MCP Server

A [FastMCP](https://gofastmcp.com) server that is the **only** way into the Campus Customs shop database. The agent team in `backend/` uses its read tools to work the open tickets: a customer order, a rent notice, and a bulk-discount request. After a human approves an action, the runner (`backend/main.py`) uses its action tools to carry it out.

## Database

- **Working copy:** `data/campus_customs_new.db`. This is the file every tool reads and writes. Override with `CAMPUS_CUSTOMS_DB`.
- **Original:** `data/campus_customs.db`. Never modified. `reset_database` restores the working copy from it. Override with `CAMPUS_CUSTOMS_ORIGINAL_DB`.

Read tools open the database in read-only mode. Only action tools open it for writing.

## Shop rules enforced in code

These hold no matter what an agent or prompt says:

1. **No cash ever comes in.** No revenue is modeled, and no tool increases a cash balance.
2. **Cash can never go negative.** Every payment is refused if it would overdraw checking. New spending (vendor orders) is also refused if it would leave less than the open invoices and rent already owed.
3. **Vendors never ship while they have an unpaid invoice.** `place_vendor_order` is refused until that vendor's open invoices are paid.
4. **Prices never go below unit cost.** `approve_price_override` refuses those discounts.
5. **Every action names a human.** Action tools require `approved_by` and record it.

## Read tools (given to agents through allowlists; `list_tickets` and `list_payments` are runner-only)

| Tool | Reads | Returns |
|---|---|---|
| `list_open_tickets()` | `tickets` | Every open ticket's id, type, requester, subject, and creation time. |
| `list_tickets()` | `tickets` | Every ticket with its status (`open`, `waiting`, `resolved`) and its original request text (`request`). Used by the board's `GET /tickets` route rather than by agents. |
| `list_payments()` | `payments`, `invoices`, `vendors`, `leases`, `tickets` | Every payment since the last reset (what it paid, its ticket when linked, who approved it). Used by the board's `GET /cash` route rather than by agents. |
| `get_ticket(ticket_id)` | `tickets`, `leases`, `invoices`, `vendors`, `inventory`, `pricing`, `desk` | The ticket plus every linked record: lease, invoice (with overdue flag), and stock and price for its SKU and size. |
| `get_product_details(sku)` | `inventory`, `pricing` | Name, list price, unit cost, and stock and location for every size. |
| `check_stock(sku, size, qty_needed=1)` | `inventory` | On hand, location, can-fill-now, and shortfall. |
| `list_vendors()` | `vendors` | Specialty and lead time in days. |
| `check_vendor_can_ship(vendor_id)` | `vendors`, `invoices`, `desk` | The vendor's unpaid invoices, balance owed, and `can_ship`. |
| `get_invoice(invoice_id)` | `invoices`, `vendors`, `desk` | Invoice details, overdue flag, and days past due. |
| `get_cash_position()` | `cash_accounts`, `invoices`, `vendors`, `leases`, `desk` | Balances, open invoices, the next rent on each lease, and cash left after all obligations (open invoices plus rent due within 30 days or overdue). |
| `preview_payment(amount, covers_existing_obligation=True)` | `cash_accounts`, `invoices`, `vendors`, `leases`, `desk` | Dry run: balance after, obligations still owed, `allowed`, and the reason. |
| `check_rent_affordability(lease_id)` | `leases`, `cash_accounts`, `invoices`, `vendors`, `desk` | Rent against the balance, competing invoices, and cash left after rent alone and after rent plus open invoices. |
| `quote_bulk_order(sku, qty, discount_pct=0)` | `pricing` | List and discounted totals, margin, `below_cost`, and `max_discount_pct_at_cost`. |
| `get_lease(lease_id)` | `leases`, `desk` | Space, landlord, rent, next due date, and days until due. |

## Action tools (runner only, after human approval)

| Tool | Writes | Refused when |
|---|---|---|
| `pay_invoice(invoice_id, approved_by)` | `cash_accounts`, `payments`, `invoices` | The invoice isn't open, or cash would go negative. |
| `pay_rent(lease_id, approved_by)` | `cash_accounts`, `payments`, `leases` | Cash would go negative. On success, `next_due` moves forward one month. |
| `place_vendor_order(vendor_id, sku, size, qty, approved_by)` | `invoices`, `cash_accounts`, `payments` | The vendor has an unpaid invoice, or the prepaid cost would leave existing obligations uncovered. |
| `approve_price_override(ticket_id, discount_pct, approved_by)` | `tickets` (notes) | The unit price would fall below unit cost. |
| `send_customer_message(ticket_id, to, subject, body, approved_by)` | `tickets` (notes) | The ticket doesn't exist. |
| `update_ticket_status(ticket_id, status, note, approved_by)` | `tickets` | The status isn't `open`, `waiting`, or `resolved`. |
| `reset_database()` | all tables | Never refused. Restores the original; the runner calls it before a full run. |

No agent is ever given an action tool. `backend/team.py` raises an error if one appears in an agent's allowlist.

## Run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python mcp_server/server.py
```

The server uses the stdio transport. `.mcp.json` at the project root registers it with Claude Code using the project venv's Python (`.venv/bin/python`; on Windows that is `.venv\Scripts\python`), and `backend/team.py` launches it for the agent team with the same interpreter that runs the backend.
