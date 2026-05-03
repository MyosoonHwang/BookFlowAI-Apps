import { useQuery } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fetchInventoryHeatmap, type Role } from '../api';

export default function Inventory() {
  const { role } = useOutletContext<{ role: Role }>();
  const q = useQuery({ queryKey: ['inv-heatmap', role], queryFn: () => fetchInventoryHeatmap(role), refetchInterval: 8000 });

  const items = q.data?.items ?? [];
  const totalSku = items.reduce((s, c) => s + c.sku_count, 0);
  const totalQty = items.reduce((s, c) => s + c.total_qty, 0);
  const totalLow = items.reduce((s, c) => s + c.low_count, 0);
  const totalZero = items.reduce((s, c) => s + c.zero_count, 0);

  const byWh = (whId: number | null) => items.filter((c) => c.wh_id === whId);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="h1">전사 재고 현황</h1>
        <p className="text-bf-muted text-xs mt-1">14개 위치 · 보유/예약/부족 한눈 보기 · 8초 자동 갱신</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="metric-card">
          <div className="metric-label">총 SKU</div>
          <div className="metric-value">{totalSku.toLocaleString()}</div>
          <div className="text-[10px] text-bf-muted mt-1">위치 × 도서 조합</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">총 보유 수량</div>
          <div className="metric-value">{totalQty.toLocaleString()}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">재고 부족 (가용≤10)</div>
          <div className="metric-value text-bf-warn">{totalLow.toLocaleString()}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">완전 소진 (보유=0)</div>
          <div className="metric-value text-bf-danger">{totalZero.toLocaleString()}</div>
        </div>
      </div>

      <WarehouseSection title="수도권 권역 (창고 1)" cells={byWh(1)} />
      <WarehouseSection title="영남 권역 (창고 2)" cells={byWh(2)} />
    </div>
  );
}

function WarehouseSection({ title, cells }: { title: string; cells: ReturnType<typeof Array.prototype.filter> & any[] }) {
  if (cells.length === 0) return null;
  const maxQty = Math.max(1, ...cells.map((c) => c.total_qty));
  return (
    <div className="card">
      <h2 className="h2 mb-3">{title}</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {cells.map((c) => {
          const intensity = c.total_qty / maxQty;
          const rowsClass =
            c.zero_count > 0 ? 'border-bf-danger' :
            c.low_count > 5  ? 'border-bf-warn'   : 'border-bf-border';
          return (
            <div key={c.location_id} className={`card-tight border-l-4 ${rowsClass}`}>
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="text-sm font-semibold">{c.name}</div>
                  <div className="text-[10px] text-bf-muted">위치 #{c.location_id} · {c.location_type ?? '-'} · {c.region ?? '-'}</div>
                </div>
                <span className={
                  c.zero_count > 0 ? 'pill-rejected' :
                  c.low_count > 5  ? 'pill-pending'  : 'pill-approved'
                }>
                  {c.zero_count > 0 ? '주의' : c.low_count > 5 ? '경고' : '정상'}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="text-[10px] text-bf-muted">SKU</div>
                  <div className="text-sm font-semibold">{c.sku_count}</div>
                </div>
                <div>
                  <div className="text-[10px] text-bf-muted">보유</div>
                  <div className="text-sm font-semibold">{c.total_qty.toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-[10px] text-bf-muted">부족</div>
                  <div className={`text-sm font-semibold ${c.low_count > 0 ? 'text-bf-warn' : ''}`}>{c.low_count}</div>
                </div>
              </div>
              <div className="mt-2 h-1.5 bg-bf-bg rounded overflow-hidden">
                <div className="h-full bg-bf-primary" style={{ width: `${intensity * 100}%` }}></div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
