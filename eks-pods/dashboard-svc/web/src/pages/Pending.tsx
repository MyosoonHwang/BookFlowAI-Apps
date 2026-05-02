import { useQuery } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fetchPending, type Role } from '../api';

export default function Pending() {
  const { role } = useOutletContext<{ role: Role }>();

  const q = useQuery({
    queryKey: ['pending', role],
    queryFn: () => fetchPending(role, 100),
    refetchInterval: 5_000,
  });

  return (
    <div className="panel">
      <h3 className="h3-tag">All Pending Orders <span className="text-gh-muted normal-case">({(q.data as any)?.items?.length ?? '-'} rows · 5s polling)</span></h3>
      {q.isLoading && <div className="text-gh-muted text-xs">loading…</div>}
      {q.error && <div className="text-gh-red text-xs">error: {String(q.error)}</div>}
      {(q.data as any)?.items && (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gh-muted text-[10px] uppercase">
              <th className="text-left py-1">created_at</th>
              <th className="text-left py-1">type</th>
              <th className="text-left py-1">isbn13</th>
              <th className="text-left py-1">src→tgt</th>
              <th className="text-left py-1">qty</th>
              <th className="text-left py-1">urgency</th>
              <th className="text-left py-1">status</th>
            </tr>
          </thead>
          <tbody>
            {(q.data as any).items.map((o: any) => (
              <tr key={o.order_id} className="border-t border-gh-border">
                <td className="py-1">{new Date(o.created_at).toLocaleString()}</td>
                <td className="py-1">{o.order_type}</td>
                <td className="py-1">{o.isbn13}</td>
                <td className="py-1">{o.source_location_id ?? '-'} → {o.target_location_id ?? '-'}</td>
                <td className="py-1">{o.qty}</td>
                <td className="py-1">{o.urgency_level}</td>
                <td className="py-1">{o.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
