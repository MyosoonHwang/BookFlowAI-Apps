import { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchPending, postDecide, type Role } from '../api';

const ORDER_TYPES = ['REBALANCE', 'WH_TRANSFER', 'PUBLISHER_ORDER'] as const;
const URGENCY = ['NORMAL', 'URGENT', 'CRITICAL'] as const;

export default function Decision() {
  const { role } = useOutletContext<{ role: Role }>();
  const qc = useQueryClient();

  const pending = useQuery({ queryKey: ['pending', role], queryFn: () => fetchPending(role, 30), refetchInterval: 5000 });

  const [form, setForm] = useState({
    order_type: 'REBALANCE' as typeof ORDER_TYPES[number],
    isbn13: '',
    source_location_id: '' as string | number,
    target_location_id: '' as string | number,
    qty: 10,
    urgency_level: 'NORMAL' as typeof URGENCY[number],
  });
  const [result, setResult] = useState<string | null>(null);

  const decide = useMutation({
    mutationFn: () => postDecide(role, {
      order_type: form.order_type,
      isbn13: form.isbn13,
      source_location_id: form.source_location_id ? Number(form.source_location_id) : null,
      target_location_id: form.target_location_id ? Number(form.target_location_id) : null,
      qty: Number(form.qty),
      urgency_level: form.urgency_level,
    }),
    onSuccess: (d) => {
      setResult(`✓ pending order 생성: ${d.order_id} (${d.status})`);
      qc.invalidateQueries({ queryKey: ['pending'] });
    },
    onError: (e) => setResult(`✗ 실패: ${String(e)}`),
  });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="lg:col-span-2 card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="h2">PENDING 결정 큐</h2>
          <span className="label-tag">decision-svc · 5초 polling</span>
        </div>
        <table className="data-table">
          <thead>
            <tr><th>생성</th><th>유형</th><th>ISBN</th><th>src→tgt</th><th>수량</th><th>긴급도</th><th>상태</th></tr>
          </thead>
          <tbody>
            {pending.data?.items.slice(0, 20).map((o) => (
              <tr key={o.order_id}>
                <td className="text-bf-muted">{new Date(o.created_at).toLocaleString()}</td>
                <td className="font-mono">{o.order_type}</td>
                <td className="font-mono text-[11px]">{o.isbn13}</td>
                <td>{o.source_location_id ?? '-'} → {o.target_location_id ?? '-'}</td>
                <td>{o.qty}</td>
                <td>
                  <span className={
                    o.urgency_level === 'CRITICAL' ? 'pill-rejected' :
                    o.urgency_level === 'URGENT'   ? 'pill-pending' : 'pill-info'
                  }>{o.urgency_level}</span>
                </td>
                <td><span className="pill-pending">{o.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2 className="h2 mb-3">신규 의사결정 생성</h2>
        <p className="text-[11px] text-bf-muted mb-3">decision-svc /decide POST 프록시 · pending_orders INSERT + Redis pub `order.pending`</p>
        <div className="space-y-3">
          <div>
            <div className="label-tag mb-1">유형</div>
            <select className="ipt w-full" value={form.order_type} onChange={(e) => setForm({ ...form, order_type: e.target.value as typeof ORDER_TYPES[number] })}>
              {ORDER_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <div className="label-tag mb-1">ISBN13</div>
            <input className="ipt w-full font-mono" value={form.isbn13} onChange={(e) => setForm({ ...form, isbn13: e.target.value })} placeholder="9788936434120" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <div className="label-tag mb-1">출발 location</div>
              <input className="ipt w-full" type="number" value={form.source_location_id} onChange={(e) => setForm({ ...form, source_location_id: e.target.value })} placeholder="1" />
            </div>
            <div>
              <div className="label-tag mb-1">도착 location</div>
              <input className="ipt w-full" type="number" value={form.target_location_id} onChange={(e) => setForm({ ...form, target_location_id: e.target.value })} placeholder="2" />
            </div>
          </div>
          <div>
            <div className="label-tag mb-1">수량</div>
            <input className="ipt w-full" type="number" min={1} value={form.qty} onChange={(e) => setForm({ ...form, qty: Number(e.target.value) })} />
          </div>
          <div>
            <div className="label-tag mb-1">긴급도</div>
            <select className="ipt w-full" value={form.urgency_level} onChange={(e) => setForm({ ...form, urgency_level: e.target.value as typeof URGENCY[number] })}>
              {URGENCY.map((u) => <option key={u}>{u}</option>)}
            </select>
          </div>
          <button
            className="btn-primary w-full"
            disabled={!form.isbn13 || decide.isPending}
            onClick={() => decide.mutate()}
          >
            {decide.isPending ? '생성 중…' : '의사결정 제출'}
          </button>
          {result && (
            <div className={`text-xs ${result.startsWith('✓') ? 'text-bf-success' : 'text-bf-danger'}`}>{result}</div>
          )}
        </div>
      </div>
    </div>
  );
}
