import { useQuery } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fetchReturns, type Role } from '../api';

export default function Returns() {
  const { role } = useOutletContext<{ role: Role }>();
  const q = useQuery({ queryKey: ['returns', role], queryFn: () => fetchReturns(role, 50), refetchInterval: 8000 });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="h1">반품 처리</h1>
        <p className="text-bf-muted text-xs mt-1">returns 테이블 · REQUESTED → APPROVED → WH 회수</p>
      </div>
      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>요청 일시</th>
              <th>ISBN</th>
              <th>제목</th>
              <th>위치</th>
              <th>수량</th>
              <th>사유</th>
              <th>상태</th>
              <th>승인일시</th>
            </tr>
          </thead>
          <tbody>
            {q.data?.items.map((r) => (
              <tr key={r.return_id}>
                <td className="text-bf-muted">{new Date(r.requested_at).toLocaleString()}</td>
                <td className="font-mono text-[11px]">{r.isbn13}</td>
                <td>{r.title ?? '-'}</td>
                <td>{r.location_id}</td>
                <td>{r.qty}</td>
                <td className="text-bf-muted">{r.reason}</td>
                <td>
                  <span className={
                    r.status === 'APPROVED' ? 'pill-approved' :
                    r.status === 'EXECUTED' ? 'pill-info' :
                    r.status === 'REJECTED' ? 'pill-rejected' : 'pill-pending'
                  }>{r.status}</span>
                </td>
                <td className="text-bf-muted">{r.hq_approved_at ? new Date(r.hq_approved_at).toLocaleString() : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
