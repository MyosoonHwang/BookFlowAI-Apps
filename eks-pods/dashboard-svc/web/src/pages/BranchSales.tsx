import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fetchSalesBySpecificStore, type Role } from '../api';

export default function BranchSales() {
  const { role } = useOutletContext<{ role: Role }>();
  const [storeId, setStoreId] = useState(1);

  const q = useQuery({
    queryKey: ['sales-store', storeId, role],
    queryFn: () => fetchSalesBySpecificStore(role, storeId, 50),
    refetchInterval: 3000,
  });

  const items = q.data?.items ?? [];
  const totalRev = items.reduce((s, x) => s + x.revenue, 0);
  const onlineCount = items.filter((x) => x.channel.startsWith('ONLINE')).length;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="h1">매장 매출</h1>
          <p className="text-bf-muted text-xs mt-1">
            매장 별 POS 트랜잭션 실시간 흐름 · 3초 자동 갱신 (pos-ingestor Lambda)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="label-tag">매장</span>
          <select className="ipt" value={storeId} onChange={(e) => setStoreId(Number(e.target.value))}>
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((n) => (
              <option key={n} value={n}>매장 {n}{n >= 11 ? ' (온라인)' : ''}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="metric-card">
          <div className="metric-label">최근 트랜잭션</div>
          <div className="metric-value">{items.length}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">합계 매출</div>
          <div className="metric-value">₩{(totalRev / 1000).toFixed(0)}K</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">온라인</div>
          <div className="metric-value">{onlineCount}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">오프라인</div>
          <div className="metric-value">{items.length - onlineCount}</div>
        </div>
      </div>

      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>시간</th>
              <th>ISBN</th>
              <th>제목</th>
              <th>저자</th>
              <th>채널</th>
              <th className="text-right">수량</th>
              <th className="text-right">단가</th>
              <th className="text-right">매출</th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={s.txn_id}>
                <td className="text-bf-muted">{new Date(s.event_ts).toLocaleTimeString()}</td>
                <td className="font-mono text-[11px]">{s.isbn13}</td>
                <td className="font-medium">{s.title ?? '-'}</td>
                <td>{s.author ?? '-'}</td>
                <td><span className={s.channel === 'OFFLINE' ? 'pill-info' : 'pill-up'}>{s.channel}</span></td>
                <td className="text-right">{s.qty}</td>
                <td className="text-right">₩{s.unit_price.toLocaleString()}</td>
                <td className="text-right font-semibold">₩{s.revenue.toLocaleString()}</td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={8} className="text-center py-6 text-bf-muted">최근 트랜잭션 없음</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
