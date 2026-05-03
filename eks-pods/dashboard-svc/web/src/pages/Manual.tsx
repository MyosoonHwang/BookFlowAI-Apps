import { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { type Role } from '../api';

const REASONS = ['파손', '분실', '도난', '입고 누락', '폐기', '기타'];

/**
 * 수동 조정 폼 - inventory-svc /adjust 직접 호출 (Phase 4 BFF proxy 추가 후).
 * 현재는 인터페이스만 시연.
 */
export default function Manual({ scope }: { scope: 'WH' | 'BRANCH' }) {
  const { role } = useOutletContext<{ role: Role }>();
  const isWh = scope === 'WH';
  const [form, setForm] = useState({
    isbn13: '',
    location_id: isWh && role === 'wh-manager-2' ? 6 : 1,
    delta: -1,
    reason: REASONS[0],
    note: '',
  });
  const [feedback, setFeedback] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: async () => {
      // Phase 4: dashboard-svc 가 inventory-svc /adjust proxy. 현재는 직접 호출 불가.
      // 시연용: 의도만 표시, BFF /dashboard/inventory/adjust 가 추가되면 fetch 호출.
      await new Promise((r) => setTimeout(r, 600));
      throw new Error('Phase 4 BFF proxy 미구현 · /dashboard/inventory/adjust 추가 필요');
    },
    onSuccess: () => setFeedback('✓ 조정 완료'),
    onError: (e) => setFeedback(`✗ ${String(e)}`),
  });

  return (
    <div className="flex flex-col gap-4 max-w-2xl">
      <div>
        <h1 className="h1">{isWh ? '창고' : '매장'} 수동 재고 조정</h1>
        <p className="text-bf-muted text-xs mt-1">
          {isWh ? '창고 직원' : '매장 직원'} 권한 · 파손/분실/입고 누락 등 수동 보정 · audit_log 자동 기록
        </p>
      </div>

      {feedback && (
        <div className={`card-tight text-xs ${feedback.startsWith('✓') ? 'text-bf-success' : 'text-bf-danger'}`}>
          {feedback}
        </div>
      )}

      <div className="card">
        <h2 className="h2 mb-4">신규 조정</h2>
        <div className="space-y-3">
          <div>
            <div className="label-tag mb-1">도서 ISBN13</div>
            <input
              className="ipt w-full font-mono"
              value={form.isbn13}
              onChange={(e) => setForm({ ...form, isbn13: e.target.value })}
              placeholder="9788936434120"
              maxLength={13}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="label-tag mb-1">위치 ID</div>
              <input
                className="ipt w-full"
                type="number"
                value={form.location_id}
                onChange={(e) => setForm({ ...form, location_id: Number(e.target.value) })}
              />
            </div>
            <div>
              <div className="label-tag mb-1">변동 수량 (음수=감소)</div>
              <input
                className="ipt w-full"
                type="number"
                value={form.delta}
                onChange={(e) => setForm({ ...form, delta: Number(e.target.value) })}
              />
            </div>
          </div>
          <div>
            <div className="label-tag mb-1">사유</div>
            <select
              className="ipt w-full"
              value={form.reason}
              onChange={(e) => setForm({ ...form, reason: e.target.value })}
            >
              {REASONS.map((r) => <option key={r}>{r}</option>)}
            </select>
          </div>
          <div>
            <div className="label-tag mb-1">상세 메모</div>
            <textarea
              className="ipt w-full h-20"
              value={form.note}
              onChange={(e) => setForm({ ...form, note: e.target.value })}
              placeholder="예: 매대 추락으로 표지 손상 5권"
            />
          </div>
          <button
            className="btn-primary w-full"
            disabled={!form.isbn13 || form.delta === 0 || submit.isPending}
            onClick={() => submit.mutate()}
          >
            {submit.isPending ? '처리 중…' : '조정 제출'}
          </button>
        </div>
      </div>

      <div className="card-tight bg-bf-warnbg border-bf-warn">
        <div className="text-xs text-bf-warn font-semibold mb-1">Phase 4 예정</div>
        <div className="text-xs text-bf-text2">
          이 폼은 dashboard-svc 가 inventory-svc /adjust 를 프록시로 호출하면 활성화됩니다.
          현재는 인터페이스만 시연 중 (Phase 5 UI 검증).
        </div>
      </div>
    </div>
  );
}
