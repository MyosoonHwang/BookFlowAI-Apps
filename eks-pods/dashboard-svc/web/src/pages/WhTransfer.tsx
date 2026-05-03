import { useQuery } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fetchPending, type Role } from '../api';
import { ko, ORDER_STATUS_KO, URGENCY_KO, whName } from '../labels';

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

  const q = useQuery({ queryKey: ['pending-transfer', role], queryFn: () => fetchPending(role, { order_type: 'WH_TRANSFER', limit: 100 }), refetchInterval: 5000 });

  const transfers = q.data?.items.filter((o) => o.order_type === 'WH_TRANSFER') ?? [];
  const inbound = transfers.filter((o) => o.target_location_id !== null);
  const outbound = transfers.filter((o) => o.source_location_id !== null);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="h1">권역 이동 · {whName(wh)} 권역</h1>
        <p className="text-bf-muted text-xs mt-1">
          창고 간 재고 이동 — 출고측 창고가 먼저 발의하고 입고측 창고가 수락해야 운송됩니다 (양쪽 승인 필요)
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="h2">우리 창고가 보낼 항목 ({outbound.length})</h2>
            <span className="text-[10px] text-bf-muted">상대 창고 수락 대기</span>
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
                    }>{ko(URGENCY_KO, o.urgency_level)}</span>
                  </td>
                  <td className="font-mono text-[11px]">{o.isbn13}</td>
                  <td>{o.source_location_id ?? '-'} → {o.target_location_id ?? '-'}</td>
                  <td className="text-right">{o.qty}권</td>
                  <td>
                    <span className={
                      o.status === 'APPROVED' ? 'pill-approved' :
                      o.status === 'REJECTED' ? 'pill-rejected' : 'pill-pending'
                    }>{ko(ORDER_STATUS_KO, o.status)}</span>
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
            <h2 className="h2">우리 창고가 받을 항목 ({inbound.length})</h2>
            <span className="text-[10px] text-bf-muted">수락하면 운송 시작</span>
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
                    }>{ko(URGENCY_KO, o.urgency_level)}</span>
                  </td>
                  <td className="font-mono text-[11px]">{o.isbn13}</td>
                  <td>{o.source_location_id ?? '-'} → {o.target_location_id ?? '-'}</td>
                  <td className="text-right">{o.qty}권</td>
                  <td>
                    <span className={
                      o.status === 'APPROVED' ? 'pill-approved' :
                      o.status === 'REJECTED' ? 'pill-rejected' : 'pill-pending'
                    }>{ko(ORDER_STATUS_KO, o.status)}</span>
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
    </div>
  );
}
