import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fetchPending, postIntervene, type Role } from '../api';

export default function Approval() {
  const { role } = useOutletContext<{ role: Role }>();
  const qc = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const pending = useQuery({ queryKey: ['pending', role], queryFn: () => fetchPending(role, 50), refetchInterval: 5000 });

  const act = useMutation({
    mutationFn: async (a: { order_id: string; action: 'approve' | 'reject'; reason?: string }) => {
      const body = a.action === 'reject'
        ? { order_id: a.order_id, approval_side: 'FINAL', reject_reason: a.reason ?? '관리자 거절' }
        : { order_id: a.order_id, approval_side: 'FINAL' };
      return postIntervene(role, a.action, body);
    },
    onMutate: (v) => { setBusy(v.order_id); setFeedback(null); },
    onSuccess: (d, v) => {
      setBusy(null);
      setFeedback(`✓ ${v.action} 처리: ${d.approval_id ?? d.order_id ?? d.detail}`);
      qc.invalidateQueries({ queryKey: ['pending'] });
    },
    onError: (e) => { setBusy(null); setFeedback(`✗ 실패: ${String(e)}`); },
  });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="h1">승인 / 거절</h1>
        <p className="text-bf-muted text-xs mt-1">intervention-svc /intervention/{'{approve,reject}'} 프록시 · order_approvals 생성 + audit_log</p>
      </div>

      {feedback && (
        <div className={`card-tight text-xs ${feedback.startsWith('✓') ? 'text-bf-success' : 'text-bf-danger'}`}>
          {feedback}
        </div>
      )}

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="h2">PENDING 큐 ({pending.data?.items.length ?? 0})</h2>
          <span className="label-tag">5초 polling</span>
        </div>
        <table className="data-table">
          <thead>
            <tr><th>긴급도</th><th>유형</th><th>ISBN</th><th>src→tgt</th><th>수량</th><th>생성</th><th className="text-right">액션</th></tr>
          </thead>
          <tbody>
            {pending.data?.items.map((o) => (
              <tr key={o.order_id}>
                <td>
                  <span className={
                    o.urgency_level === 'CRITICAL' ? 'pill-rejected' :
                    o.urgency_level === 'URGENT'   ? 'pill-pending' : 'pill-info'
                  }>{o.urgency_level}</span>
                </td>
                <td className="font-mono">{o.order_type}</td>
                <td className="font-mono text-[11px]">{o.isbn13}</td>
                <td>{o.source_location_id ?? '-'} → {o.target_location_id ?? '-'}</td>
                <td>{o.qty}</td>
                <td className="text-bf-muted">{new Date(o.created_at).toLocaleString()}</td>
                <td className="text-right">
                  <div className="flex gap-1 justify-end">
                    <button
                      className="btn-primary btn-sm"
                      disabled={busy === o.order_id}
                      onClick={() => act.mutate({ order_id: o.order_id, action: 'approve' })}
                    >
                      승인
                    </button>
                    <button
                      className="btn-danger btn-sm"
                      disabled={busy === o.order_id}
                      onClick={() => {
                        const reason = window.prompt('거절 사유?', '재고 부족');
                        if (reason) act.mutate({ order_id: o.order_id, action: 'reject', reason });
                      }}
                    >
                      거절
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {pending.data?.items.length === 0 && (
              <tr><td colSpan={7} className="text-center py-6 text-bf-muted">대기 중인 주문 없음</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
