import { useQuery } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fetchInstructions, type Role } from '../api';

export default function WhInstructions() {
  const { role } = useOutletContext<{ role: Role }>();
  const wh = role === 'wh-manager-2' ? 2 : 1;
  const q = useQuery({ queryKey: ['instr', wh, role], queryFn: () => fetchInstructions(role, wh), refetchInterval: 8000 });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="h1">출고 지시서 · 창고 {wh}</h1>
        <p className="text-bf-muted text-xs mt-1">
          승인된 발주/이동 지시 - 창고 작업자가 출고 또는 수령 처리할 항목
        </p>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="h2">지시서 목록 ({q.data?.items.length ?? 0})</h2>
          <span className="label-tag">pending_orders · status=APPROVED</span>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>승인 일시</th>
              <th>유형</th>
              <th>긴급도</th>
              <th>ISBN</th>
              <th>제목</th>
              <th>출발 → 도착</th>
              <th className="text-right">수량</th>
              <th>상태</th>
            </tr>
          </thead>
          <tbody>
            {q.data?.items.map((o) => (
              <tr key={o.order_id}>
                <td className="text-bf-muted">{o.approved_at ? new Date(o.approved_at).toLocaleString() : '-'}</td>
                <td className="font-mono">{o.order_type}</td>
                <td>
                  <span className={
                    o.urgency_level === 'CRITICAL' ? 'pill-rejected' :
                    o.urgency_level === 'URGENT'   ? 'pill-pending' : 'pill-info'
                  }>{o.urgency_level}</span>
                </td>
                <td className="font-mono text-[11px]">{o.isbn13}</td>
                <td>{o.title ?? '-'}</td>
                <td>{o.source_location_id ?? '-'} → {o.target_location_id ?? '-'}</td>
                <td className="text-right">{o.qty}</td>
                <td>
                  <span className={
                    o.status === 'EXECUTED' ? 'pill-info' : 'pill-approved'
                  }>{o.status === 'EXECUTED' ? '실행됨' : '대기 중'}</span>
                </td>
              </tr>
            ))}
            {q.data?.items.length === 0 && (
              <tr><td colSpan={8} className="text-center py-6 text-bf-muted">지시서 없음 · 승인 대기 중인 주문은 상위 승인 큐에서 처리</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
