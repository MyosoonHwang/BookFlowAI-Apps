import { useQuery } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fetchOverview, fetchSalesByStore, type Role } from '../api';
import { ko, ORDER_TYPE_KO, URGENCY_KO } from '../labels';

export default function WhDashboard() {
  const { role } = useOutletContext<{ role: Role }>();
  const wh_id = role === 'wh-manager-2' ? 2 : 1;

  const ov = useQuery({ queryKey: ['ov', wh_id, role], queryFn: () => fetchOverview(wh_id, role), refetchInterval: 5000 });
  const byStore = useQuery({ queryKey: ['byStore', role], queryFn: () => fetchSalesByStore(role), refetchInterval: 5000 });

  // Filter stores by wh_id mapping (1-5 = wh1, 6-10 = wh2, 11/12 = wh1 online)
  const wh1Stores = [1, 2, 3, 4, 5, 11, 12];
  const wh2Stores = [6, 7, 8, 9, 10];
  const myStores = wh_id === 1 ? wh1Stores : wh2Stores;
  const filtered = byStore.data?.items.filter((s) => myStores.includes(s.store_id)) ?? [];
  const totalRev = filtered.reduce((sum, s) => sum + s.revenue, 0);
  const totalTx = filtered.reduce((sum, s) => sum + s.transactions, 0);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="h1">{wh_id === 1 ? '수도권' : '영남'} 권역 대시보드</h1>
        <p className="text-bf-muted text-xs mt-1">관할 매장 매출 · 재고 · 대기 중인 주문 한눈에</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="metric-card">
          <div className="metric-label">관할 매장 수</div>
          <div className="metric-value">{filtered.length}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">최근 1시간 매출</div>
          <div className="metric-value">₩{(totalRev / 1000).toFixed(0)}K</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">최근 1시간 거래수</div>
          <div className="metric-value">{totalTx}건</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">관리 중인 도서</div>
          <div className="metric-value">{ov.data?.inventory?.items.length ?? '-'}종</div>
        </div>
      </div>

      <div className="card">
        <h2 className="h2 mb-3">관할 매장 매출 (최근 1시간)</h2>
        <table className="data-table">
          <thead>
            <tr><th>매장</th><th className="text-right">거래 수</th><th className="text-right">매출</th><th className="text-right">온라인 비중</th></tr>
          </thead>
          <tbody>
            {filtered.map((s) => (
              <tr key={s.store_id}>
                <td>매장 {s.store_id}{s.store_id >= 11 ? ' (온라인)' : ''}</td>
                <td className="text-right">{s.transactions}건</td>
                <td className="text-right">₩{s.revenue.toLocaleString()}</td>
                <td className="text-right">{s.transactions > 0 ? `${Math.round((s.online_count / s.transactions) * 100)}%` : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2 className="h2 mb-3">대기 중인 주문 (관할)</h2>
        <table className="data-table">
          <thead>
            <tr><th>긴급도</th><th>유형</th><th>ISBN</th><th>출발 → 도착</th><th>수량</th><th>접수 시각</th></tr>
          </thead>
          <tbody>
            {ov.data?.pending_orders?.items.slice(0, 15).map((o) => (
              <tr key={o.order_id}>
                <td>
                  <span className={
                    o.urgency_level === 'CRITICAL' ? 'pill-rejected' :
                    o.urgency_level === 'URGENT'   ? 'pill-pending' : 'pill-info'
                  }>{ko(URGENCY_KO, o.urgency_level)}</span>
                </td>
                <td>{ko(ORDER_TYPE_KO, o.order_type)}</td>
                <td className="font-mono text-[11px]">{o.isbn13}</td>
                <td>{o.source_location_id ?? '-'} → {o.target_location_id ?? '-'}</td>
                <td>{o.qty}권</td>
                <td className="text-bf-muted">{new Date(o.created_at).toLocaleString('ko-KR')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
