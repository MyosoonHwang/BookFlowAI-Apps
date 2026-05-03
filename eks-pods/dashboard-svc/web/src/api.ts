// Same-origin (FastAPI serves SPA + API + WS).
import { token, type Role } from './auth';

export type { Role } from './auth';

async function getJson<T>(path: string, role: Role): Promise<T> {
  const r = await fetch(path, { headers: { Authorization: token(role) } });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function postJson<T>(path: string, role: Role, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: 'POST',
    headers: { Authorization: token(role), 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const text = await r.text().catch(() => '');
    throw new Error(`${r.status} ${r.statusText}: ${text}`);
  }
  return r.json();
}

// ─── Overview / fan-in ──────────────────────────────────────────────
export type Overview = {
  wh_id: number;
  inventory: { items: { isbn13: string; on_hand: number; reserved_qty: number; available: number }[] } | null;
  forecast: { items: unknown[] } | null;
  pending_orders: { items: PendingOrder[] } | null;
  interventions: { items: unknown[] } | null;
  notifications: { items: unknown[] } | null;
  _partial_failures: string[];
};

// ─── Pending orders (decision-svc) ──────────────────────────────────
export type PendingOrder = {
  order_id: string;
  order_type: string;
  isbn13: string;
  source_location_id: number | null;
  target_location_id: number | null;
  qty: number;
  urgency_level: string;
  status: string;
  created_at: string;
};

export const fetchOverview = (whId: number, role: Role) =>
  getJson<Overview>(`/dashboard/overview/${whId}`, role);

export const fetchPending = (role: Role, limit = 100) =>
  getJson<{ items: PendingOrder[] }>(`/dashboard/pending?limit=${limit}`, role);

// ─── Recent POS sales (direct RDS) ──────────────────────────────────
export type SaleRow = {
  txn_id: string;
  event_ts: string;
  isbn13: string;
  store_id: number;
  channel: string;
  qty: number;
  revenue: number;
};
export const fetchRecentSales = (role: Role, limit = 20) =>
  getJson<{ items: SaleRow[] }>(`/dashboard/recent-sales?limit=${limit}`, role);

export type SalesSummary = {
  window: string;
  transactions: number;
  total_revenue: number;
  online_count: number;
  offline_count: number;
};
export const fetchSalesSummary = (role: Role) =>
  getJson<SalesSummary>('/dashboard/sales-summary', role);

export type StoreSales = { store_id: number; transactions: number; revenue: number; online_count: number };
export const fetchSalesByStore = (role: Role) =>
  getJson<{ items: StoreSales[] }>('/dashboard/sales-by-store', role);

// ─── Books catalog ──────────────────────────────────────────────────
export type Book = {
  isbn13: string;
  title: string;
  author: string | null;
  publisher: string | null;
  pub_date: string | null;
  category: string | null;
  price_standard: number | null;
  price_sales: number | null;
  discontinue_mode: string | null;
  expected_soldout_at: string | null;
};
export const fetchBooks = (role: Role, params: { limit?: number; offset?: number; q?: string } = {}) => {
  const qs = new URLSearchParams();
  if (params.limit !== undefined)  qs.set('limit',  String(params.limit));
  if (params.offset !== undefined) qs.set('offset', String(params.offset));
  if (params.q)                    qs.set('q',      params.q);
  return getJson<{ total: number; limit: number; offset: number; items: Book[] }>(
    `/dashboard/books?${qs.toString()}`, role,
  );
};

// ─── Spike events ───────────────────────────────────────────────────
export type SpikeEvent = {
  event_id: string;
  detected_at: string;
  isbn13: string;
  z_score: number | null;
  mentions_count: number;
  title: string | null;
  author: string | null;
  category: string | null;
};
export const fetchSpikeEvents = (role: Role, limit = 20) =>
  getJson<{ items: SpikeEvent[] }>(`/dashboard/spike-events?limit=${limit}`, role);

// ─── Returns ────────────────────────────────────────────────────────
export type ReturnRow = {
  return_id: string;
  isbn13: string;
  location_id: number;
  qty: number;
  reason: string;
  status: string;
  requested_at: string;
  hq_approved_at: string | null;
  executed_at: string | null;
  title: string | null;
  author: string | null;
};
export const fetchReturns = (role: Role, limit = 50) =>
  getJson<{ items: ReturnRow[] }>(`/dashboard/returns?limit=${limit}`, role);

// ─── New book requests ──────────────────────────────────────────────
export type NewBookRequest = {
  id: number;
  isbn13: string;
  publisher_id: number;
  title: string | null;
  status: string;
  requested_at: string;
};
export const fetchNewBookRequests = (role: Role, limit = 50) =>
  getJson<{ items: NewBookRequest[] }>(`/dashboard/new-book-requests?limit=${limit}`, role);

// ─── Notifications ──────────────────────────────────────────────────
export type Notification = {
  notification_id: string;
  event_type: string;
  severity: string | null;
  status: string;
  channels: string | null;
  payload_summary: unknown;
  sent_at: string;
};
export const fetchNotifications = (role: Role, limit = 50) =>
  getJson<{ items: Notification[] }>(`/dashboard/notifications?limit=${limit}`, role);

// ─── Mutations ──────────────────────────────────────────────────────
export const postIntervene = (role: Role, action: 'approve' | 'reject', body: unknown) =>
  postJson<{ approval_id?: string; order_id?: string; decision?: string; detail?: string }>(
    `/dashboard/intervene/${action}`, role, body,
  );

export const postDecide = (role: Role, body: unknown) =>
  postJson<{ order_id: string; status: string; created_at: string }>('/dashboard/decide', role, body);

export const postNotifySend = (role: Role, body: unknown) =>
  postJson<{ notification_id: string; status: string; sent_at: string }>('/dashboard/notify/send', role, body);
