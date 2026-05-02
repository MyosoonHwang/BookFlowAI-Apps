// Same-origin (FastAPI serves SPA + API + WS).

export type Role = 'hq-admin' | 'wh-manager-1' | 'wh-manager-2' | 'branch-clerk';

export function token(role: Role): string {
  return `Bearer mock-token-${role}`;
}

async function getJson<T>(path: string, role: Role): Promise<T> {
  const r = await fetch(path, { headers: { Authorization: token(role) } });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export type Overview = {
  wh_id: number;
  inventory: { items: { isbn13: string; on_hand: number; reserved_qty: number; available: number }[] } | null;
  forecast: { items: unknown[] } | null;
  pending_orders: {
    items: {
      order_id: string;
      order_type: string;
      isbn13: string;
      qty: number;
      urgency_level: string;
      status: string;
      created_at: string;
    }[];
  } | null;
  interventions: { items: unknown[] } | null;
  notifications: { items: unknown[] } | null;
  _partial_failures: string[];
};

export const fetchOverview = (whId: number, role: Role) =>
  getJson<Overview>(`/dashboard/overview/${whId}`, role);

export const fetchPending = (role: Role, limit = 100) =>
  getJson<{ items: Overview['pending_orders'] extends infer P ? (P extends { items: infer I } ? I : never) : never }>(
    `/dashboard/pending?limit=${limit}`,
    role,
  );
