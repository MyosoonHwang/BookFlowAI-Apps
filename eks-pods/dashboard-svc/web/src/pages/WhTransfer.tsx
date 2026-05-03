import { useQuery } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fetchPending, type Role } from '../api';

/**
 * 권역 이동 - 2단계 SOURCE/TARGET 이중 승인 시나리오 (.pen C-1~C-4).
 * pending_orders 중 order_type='WH_TRANSFER' 만 필터.
 *
 * Phase 4 : transfer_requests 별도 테이블 + propose/accept POST 추가.
 * Phase 3 : pending_orders 의 source_location_id <-> target_location_id 로 demonstrate.
 */
export default function WhTransfer() {
  const { role } = useOutletContext<{ role: Role }>();
  const wh = role === 'wh-manager-2' ? 2 : 1;

  const q = useQuery({ queryKey: ['pending', role], queryFn: () => fetchPending(role, 100), refetchInterval: 5000 });

  const transfers = q.data?.items.filter((o) => o.order_type === 'WH_TRANSFER') ?? [];
  const inbound = transfers.filter((o) => o.target_location_id !== null);
  const outbound = transfers.filter((o) => o.source_location_id !== null);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="h1">권역 이동 · 창고 {wh}</h1>
        <p className="text-bf-muted text-xs mt-1">
          창고 간 재고 이동 - SOURCE 창고 발의 → TARGET 창고 수락 (2단계 이중 승인)
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="h2">출고 발의 ({outbound.length})</h2>
            <span className="label-tag">SOURCE 발의 → 상대 창고 수락 대기</span>
          </div>
          <table className="data-table">
            <thead>
              <tr><th>긴급도</th><th>ISBN</th><th>출발 → 도착</th><th className="text-right">수량</th><th>상태</th></tr>
            </thead>
            <tbody>
              {outbound.slice(0, 20).map((o) => (
                <tr key={o.order_id}>
                  <td>
                    <span className={
                      o.urgency_level === 'CRITICAL' ? 'pill-rejected' :
                      o.urgency_level === 'URGENT'   ? 'pill-pending' : 'pill-info'
                    }>{o.urgency_level}</span>
                  </td>
                  <td className="font-mono text-[11px]">{o.isbn13}</td>
                  <td>{o.source_location_id ?? '-'} → {o.target_location_id ?? '-'}</td>
                  <td className="text-right">{o.qty}</td>
                  <td>
                    <span className={
                      o.status === 'APPROVED' ? 'pill-approved' :
                      o.status === 'REJECTED' ? 'pill-rejected' : 'pill-pending'
                    }>{o.status}</span>
                  </td>
                </tr>
              ))}
              {outbound.length === 0 && (
                <tr><td colSpan={5} className="text-center py-6 text-bf-muted">발의 건 없음</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="h2">입고 수락 대기 ({inbound.length})</h2>
            <span className="label-tag">TARGET 수락 → 운송 시작</span>
          </div>
          <table className="data-table">
            <thead>
              <tr><th>긴급도</th><th>ISBN</th><th>출발 → 도착</th><th className="text-right">수량</th><th>상태</th></tr>
            </thead>
            <tbody>
              {inbound.slice(0, 20).map((o) => (
                <tr key={o.order_id}>
                  <td>
                    <span className={
                      o.urgency_level === 'CRITICAL' ? 'pill-rejected' :
                      o.urgency_level === 'URGENT'   ? 'pill-pending' : 'pill-info'
                    }>{o.urgency_level}</span>
                  </td>
                  <td className="font-mono text-[11px]">{o.isbn13}</td>
                  <td>{o.source_location_id ?? '-'} → {o.target_location_id ?? '-'}</td>
                  <td className="text-right">{o.qty}</td>
                  <td>
                    <span className={
                      o.status === 'APPROVED' ? 'pill-approved' :
                      o.status === 'REJECTED' ? 'pill-rejected' : 'pill-pending'
                    }>{o.status}</span>
                  </td>
                </tr>
              ))}
              {inbound.length === 0 && (
                <tr><td colSpan={5} className="text-center py-6 text-bf-muted">수락 대기 없음</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card-tight bg-bf-warnbg border-bf-warn">
        <div className="text-xs text-bf-warn font-semibold mb-1">Phase 4 예정</div>
        <div className="text-xs text-bf-text2">
          신규 발의 폼 + 수락/거절 버튼은 transfer_requests 테이블 + intervention-svc 의 SOURCE/TARGET 2단계 approval_side 추가 후 활성화.
          현재는 decision-svc 의 WH_TRANSFER 타입 pending_orders 가 동일 의미로 작동.
        </div>
      </div>
    </div>
  );
}
