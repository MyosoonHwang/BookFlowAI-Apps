import { useQuery } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fetchInstructions, type Role } from '../api';
import { ko, ORDER_TYPE_KO, URGENCY_KO } from '../labels';

export default function BranchInbound() {
  const { role } = useOutletContext<{ role: Role }>();
  const my_store = 1; // branch-clerk default store
  // wh_id 미지정 = 전체. 매장 작업자는 location 으로 한번 더 필터.
  const q = useQuery({ queryKey: ['instr-all', role], queryFn: () => fetchInstructions(role), refetchInterval: 8000 });

  const myInbound = q.data?.items.filter((o) => o.target_location_id === my_store) ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="h1">입고 확인 · 매장 {my_store}</h1>
        <p className="text-bf-muted text-xs mt-1">
          창고에서 발송된 도서 - 매장 도착 시 수령 확인
        </p>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="h2">입고 대기 ({myInbound.length})</h2>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>승인 일시</th>
              <th>유형</th>
              <th>긴급도</th>
              <th>ISBN</th>
              <th>제목</th>
              <th>출발지</th>
              <th className="text-right">수량</th>
              <th className="text-right">액션</th>
            </tr>
          </thead>
          <tbody>
            {myInbound.map((o) => (
              <tr key={o.order_id}>
                <td className="text-bf-muted">{o.approved_at ? new Date(o.approved_at).toLocaleString() : '-'}</td>
                <td>{ko(ORDER_TYPE_KO, o.order_type)}</td>
                <td>
                  <span className={
                    o.urgency_level === 'CRITICAL' ? 'pill-rejected' :
                    o.urgency_level === 'URGENT'   ? 'pill-pending' : 'pill-info'
                  }>{ko(URGENCY_KO, o.urgency_level)}</span>
                </td>
                <td className="font-mono text-[11px]">{o.isbn13}</td>
                <td>{o.title ?? '-'}</td>
                <td>위치 {o.source_location_id ?? '-'}</td>
                <td className="text-right">{o.qty}권</td>
                <td className="text-right">
                  <button className="btn-primary btn-sm" onClick={() => alert('수령 처리는 다음 단계에서 활성화 예정')}>
                    수령
                  </button>
                </td>
              </tr>
            ))}
            {myInbound.length === 0 && (
              <tr><td colSpan={8} className="text-center py-6 text-bf-muted">입고 대기 없음</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
