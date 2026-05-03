import { useQuery } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fetchNewBookRequests, type Role } from '../api';

export default function Requests() {
  const { role } = useOutletContext<{ role: Role }>();
  const q = useQuery({ queryKey: ['requests', role], queryFn: () => fetchNewBookRequests(role, 50), refetchInterval: 8000 });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="h1">출판사 신간 신청</h1>
        <p className="text-bf-muted text-xs mt-1">publisher-watcher CronJob (1분 폴링) → new_book_requests · NEW → FETCHED → APPROVED</p>
      </div>
      <div className="card">
        <table className="data-table">
          <thead>
            <tr><th>요청 일시</th><th>ISBN</th><th>제목</th><th>출판사</th><th>상태</th></tr>
          </thead>
          <tbody>
            {q.data?.items.map((r) => (
              <tr key={r.id}>
                <td className="text-bf-muted">{new Date(r.requested_at).toLocaleString()}</td>
                <td className="font-mono text-[11px]">{r.isbn13}</td>
                <td className="font-medium">{r.title ?? '-'}</td>
                <td>출판사 {r.publisher_id}</td>
                <td>
                  <span className={
                    r.status === 'APPROVED' ? 'pill-approved' :
                    r.status === 'FETCHED'  ? 'pill-info' : 'pill-pending'
                  }>{r.status}</span>
                </td>
              </tr>
            ))}
            {q.data?.items.length === 0 && (
              <tr><td colSpan={5} className="text-center py-6 text-bf-muted">신청 없음 · publisher-watcher 의 PUBLISHER_API_URL 환경변수 미설정 (Phase 4)</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
