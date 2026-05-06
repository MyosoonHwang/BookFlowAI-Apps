import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fetchReturns, postReturnsApprove, type Role } from '../api';
import { ko, RETURN_STATUS_KO } from '../labels';
import { useLocations } from '../useLocations';

const RETURN_REASON_KO: Record<string, string> = {
  CUSTOMER:             '고객 반품',
  DAMAGED:              '파손',
  SOFT_DISCONTINUE_END: '소진 모드 종료',
  LONG_TAIL:            '판매 부진',
};

export default function Returns() {
  const { role } = useOutletContext<{ role: Role }>();
  const qc = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const { nameOf } = useLocations(role);

  const q = useQuery({ queryKey: ['returns', role], queryFn: () => fetchReturns(role, 50), refetchInterval: 8000 });

  const act = useMutation({
    mutationFn: (return_id: string) => postReturnsApprove(role, { return_id }),
    onMutate: (id) => { setBusy(id); setFeedback(null); },
    onSuccess: (d) => {
      setBusy(null);
      setFeedback(`✓ 반품 ${d.return_id} 승인 완료`);
      qc.invalidateQueries({ queryKey: ['returns'] });
    },
    onError: (e) => { setBusy(null); setFeedback(`✗ 실패: ${String(e)}`); },
  });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="h1">반품 처리</h1>
        <p className="text-bf-muted text-xs mt-1">반품 신청 → 본사 승인 → 창고가 출판사로 반품 실행 (본사 단독 결정)</p>
      </div>

      {feedback && (
        <div className={`card-tight text-xs ${feedback.startsWith('✓') ? 'text-bf-success' : 'text-bf-danger'}`}>
          {feedback}
        </div>
      )}

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
              <th>승인</th>
              <th className="text-right">액션</th>
            </tr>
          </thead>
          <tbody>
            {q.data?.items.map((r) => (
              <tr key={r.return_id}>
                <td className="text-bf-muted">{new Date(r.requested_at).toLocaleString('ko-KR')}</td>
                <td className="font-mono text-[11px]">{r.isbn13}</td>
                <td>{r.title ?? '-'}</td>
                <td>{nameOf(r.location_id)}</td>
                <td>{r.qty}권</td>
                <td className="text-bf-muted">{ko(RETURN_REASON_KO, r.reason)}</td>
                <td>
                  <span className={
                    r.status === 'APPROVED' ? 'pill-approved' :
                    r.status === 'EXECUTED' ? 'pill-info' :
                    r.status === 'REJECTED' ? 'pill-rejected' : 'pill-pending'
                  }>{ko(RETURN_STATUS_KO, r.status)}</span>
                </td>
                <td className="text-bf-muted">{r.hq_approved_at ? new Date(r.hq_approved_at).toLocaleString('ko-KR') : '-'}</td>
                <td className="text-right">
                  {r.status === 'PENDING' && role === 'hq-admin' ? (
                    <button
                      className="btn-primary btn-sm"
                      disabled={busy === r.return_id}
                      onClick={() => act.mutate(r.return_id)}
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
              <tr><td colSpan={9} className="text-center py-6 text-bf-muted">반품 요청 없음</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
