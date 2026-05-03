import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fetchNewBookRequests, postNewBookApprove, type Role } from '../api';

export default function Requests() {
  const { role } = useOutletContext<{ role: Role }>();
  const qc = useQueryClient();
  const [busy, setBusy] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const q = useQuery({ queryKey: ['requests', role], queryFn: () => fetchNewBookRequests(role, 50), refetchInterval: 8000 });

  const act = useMutation({
    mutationFn: (id: number) => postNewBookApprove(role, id),
    onMutate: (id) => { setBusy(id); setFeedback(null); },
    onSuccess: (d) => {
      setBusy(null);
      setFeedback(`✓ 신간 ${d.isbn13} 승인 완료 (요청 #${d.id})`);
      qc.invalidateQueries({ queryKey: ['requests'] });
    },
    onError: (e) => { setBusy(null); setFeedback(`✗ 실패: ${String(e)}`); },
  });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="h1">출판사 신간 신청</h1>
        <p className="text-bf-muted text-xs mt-1">
          publisher-watcher CronJob (1분 폴링) → new_book_requests · NEW → FETCHED → APPROVED · 본사 단독 승인
        </p>
      </div>

      {feedback && (
        <div className={`card-tight text-xs ${feedback.startsWith('✓') ? 'text-bf-success' : 'text-bf-danger'}`}>
          {feedback}
        </div>
      )}

      <div className="card">
        <table className="data-table">
          <thead>
            <tr><th>요청 일시</th><th>ISBN</th><th>제목</th><th>출판사</th><th>상태</th><th className="text-right">액션</th></tr>
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
                <td className="text-right">
                  {r.status !== 'APPROVED' && role === 'hq-admin' ? (
                    <button
                      className="btn-primary btn-sm"
                      disabled={busy === r.id}
                      onClick={() => act.mutate(r.id)}
                    >
                      승인
                    </button>
                  ) : (
                    <span className="text-[10px] text-bf-muted">-</span>
                  )}
                </td>
              </tr>
            ))}
            {q.data?.items.length === 0 && (
              <tr><td colSpan={6} className="text-center py-6 text-bf-muted">신청 없음 · publisher-watcher 의 PUBLISHER_API_URL 미설정 (Phase 4)</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
