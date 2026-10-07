// Shapes returned by the FastAPI desk API (backend/main.py).

export type Role = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string // open | waiting | resolved
  created_at: string
  request: string // the original request text, before any approved notes were appended
  resolved: boolean
  run: string // not_run | running | awaiting_approval | awaiting_resolution | resolving | resolved | finished_* | error | stopped_usage_limit
}

export interface ActionItem {
  id: string
  ticket_id: number
  owner: Role
  kind: string
  description: string
  amount: number | null
  rationale: string
  tool: string | null
  arguments: Record<string, string | number>
  status: string // pending | executing | executed | refused_by_server | rejected | blocked_other_ticket | superseded | ...
  decided_by: string | null
  decided_at: string | null
  result: Record<string, unknown> | null
}

export interface Plan {
  ticket_id: number
  summary: string
  cash_check: string
  open_questions: string[]
  risks: string[]
  delegations: { role: Role; request: string; finding: string }[]
  customer_message_draft: { to: string; subject: string; body: string } | null
}

export interface RunView {
  status: string
  run_no?: number
  started_at?: string
  finished_at?: string
  resolved_at?: string
  plan?: Plan
  usage?: { requests: number; total_tokens: number }
  error?: string | null
  actions?: ActionItem[]
}

export interface AgentEvent {
  id: number
  timestamp: string
  ticket_id: number | null
  actor: string
  event: string
  summary: string
  tool?: string
  to?: string
  request?: string
  answer?: string
  decision?: string
  [key: string]: unknown
}

export interface Payment {
  id: number
  kind: string // invoice | purchase_order | rent
  ref_id: number
  amount: number
  paid_at: string
  approved_by: string
  ticket_id: number | null
  label: string
}

export interface Cash {
  account: string
  balance: number
  starting_balance: number // balance at the last reset: current balance plus every payment since
  payments: Payment[] // oldest first
  as_of: string
  total_committed: number
  cash_after_all_obligations: number
}
