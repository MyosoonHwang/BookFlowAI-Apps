import { useQuery } from '@tanstack/react-query';
import { useParams, useOutletContext } from 'react-router-dom';
import { fetchOverview, fetchRecentSales, fetchSalesSummary, type Role } from '../api';

export default function Overview() {
  const { wh } = useParams();
  const whId = Number(wh ?? 1);
  const { role } = useOutletContext<{ role: Role }>();

  const q = useQuery({
    queryKey: ['overview', whId, role],
    queryFn: () => fetchOverview(whId, role),
    refetchInterval: 5_000,
  });

  const sales = useQuery({
    queryKey: ['recent-sales', role],
    queryFn: () => fetchRecentSales(role, 15),
    refetchInterval: 3_000,
  });

  const summary = useQuery({
    queryKey: ['sales-summary', role],
    queryFn: () => fetchSalesSummary(role),
    refetchInterval: 5_000,
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="panel">
        <h3 className="h3-tag">5-pod fan-in · WH {whId}</h3>
        {q.isLoading && <div className="text-gh-muted text-xs">loading…</div>}
        {q.error && <div className="text-gh-red text-xs">error: {String(q.error)}</div>}
        {q.data && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
              <div className="metric">
                <div className="metric-label">inventory-svc</div>
                <div className="metric-value">{q.data.inventory?.items.length ?? '·'}</div>
              </div>
              <div className="metric">
                <div className="metric-label">forecast-svc</div>
                <div className="metric-value">{q.data.forecast?.items.length ?? '·'}</div>
              </div>
              <div className="metric">
                <div className="metric-label">decision-svc</div>
                <div className="metric-value">{q.data.pending_orders?.items.length ?? '·'}</div>
              </div>
              <div className="metric">
                <div className="metric-label">intervention-svc</div>
                <div className="metric-value">{q.data.interventions?.items?.length ?? '·'}</div>
              </div>
              <div className="metric">
                <div className="metric-label">notification-svc</div>
                <div className="metric-value">{q.data.notifications?.items?.length ?? '·'}</div>
              </div>
              <div className="metric">
                <div className="metric-label">partial fail</div>
                <div className="metric-value" style={{ color: q.data._partial_failures.length ? '#f85149' : '#56d364' }}>
                  {q.data._partial_failures.length}
                </div>
              </div>
            </div>
            {q.data._partial_failures.length > 0 && (
              <div className="mt-2 text-[11px] text-gh-muted">
                미응답 pod: <span className="text-gh-orange">{q.data._partial_failures.join(', ')}</span>
              </div>
            )}
          </>
        )}
      </div>

      <div className="panel">
        <h3 className="h3-tag">
          POS Sales (1h) <span className="text-gh-muted normal-case">(direct RDS read · 5s polling)</span>
        </h3>
        {summary.data && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <div className="metric">
              <div className="metric-label">transactions / 1h</div>
              <div className="metric-value">{summary.data.transactions}</div>
            </div>
            <div className="metric">
              <div className="metric-label">revenue / 1h</div>
              <div className="metric-value">{summary.data.total_revenue.toLocaleString()}</div>
            </div>
            <div className="metric">
              <div className="metric-label">online</div>
              <div className="metric-value">{summary.data.online_count}</div>
            </div>
            <div className="metric">
              <div className="metric-label">offline</div>
              <div className="metric-value">{summary.data.offline_count}</div>
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <h3 className="h3-tag">
          Recent POS transactions <span className="text-gh-muted normal-case">(pos-ingestor Lambda · 3s polling)</span>
        </h3>
        {sales.isLoading && <div className="text-gh-muted text-xs">loading…</div>}
        {sales.data?.items && (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gh-muted text-[10px] uppercase">
                <th className="text-left py-1">event_ts</th>
                <th className="text-left py-1">isbn13</th>
                <th className="text-left py-1">store</th>
                <th className="text-left py-1">channel</th>
                <th className="text-left py-1">qty</th>
                <th className="text-left py-1">revenue</th>
              </tr>
            </thead>
            <tbody>
              {sales.data.items.map((s) => (
                <tr key={s.txn_id} className="border-t border-gh-border">
                  <td className="py-1 text-gh-muted">{new Date(s.event_ts).toLocaleTimeString()}</td>
                  <td className="py-1">{s.isbn13}</td>
                  <td className="py-1">{s.store_id}</td>
                  <td className="py-1 text-gh-blue">{s.channel}</td>
                  <td className="py-1">{s.qty}</td>
                  <td className="py-1">{s.revenue.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3 className="h3-tag">Pending orders <span className="text-gh-muted normal-case">(decision-svc · 5s polling)</span></h3>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gh-muted text-[10px] uppercase">
              <th className="text-left py-1">created_at</th>
              <th className="text-left py-1">type</th>
              <th className="text-left py-1">isbn13</th>
              <th className="text-left py-1">qty</th>
              <th className="text-left py-1">urgency</th>
              <th className="text-left py-1">status</th>
            </tr>
          </thead>
          <tbody>
            {q.data?.pending_orders?.items.slice(0, 10).map((o) => (
              <tr key={o.order_id} className="border-t border-gh-border">
                <td className="py-1">{new Date(o.created_at).toLocaleString()}</td>
                <td className="py-1">{o.order_type}</td>
                <td className="py-1">{o.isbn13}</td>
                <td className="py-1">{o.qty}</td>
                <td className="py-1">{o.urgency_level}</td>
                <td className="py-1">{o.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
