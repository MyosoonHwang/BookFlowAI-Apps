import { useQuery } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fetchNotifications, type Role } from '../api';

const SEVERITY_PILL: Record<string, string> = {
  CRITICAL: 'pill-rejected', WARNING: 'pill-pending', INFO: 'pill-info',
};
const STATUS_PILL: Record<string, string> = {
  SENT: 'pill-approved', FAILED: 'pill-rejected', RETRYING: 'pill-pending', PENDING: 'pill-pending',
};

export default function Notifications() {
  const { role } = useOutletContext<{ role: Role }>();
  const q = useQuery({ queryKey: ['notif', role], queryFn: () => fetchNotifications(role, 50), refetchInterval: 5000 });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="h1">알림 로그</h1>
        <p className="text-bf-muted text-xs mt-1">notification-svc · 12 Logic Apps 이벤트 · azure-logic-apps-mock webhook</p>
      </div>
      <div className="card">
        <table className="data-table">
          <thead>
            <tr><th>발송</th><th>이벤트</th><th>심각도</th><th>채널</th><th>상태</th><th>요약</th></tr>
          </thead>
          <tbody>
            {q.data?.items.map((n) => (
              <tr key={n.notification_id}>
                <td className="text-bf-muted">{new Date(n.sent_at).toLocaleString()}</td>
                <td className="font-mono">{n.event_type}</td>
                <td><span className={SEVERITY_PILL[n.severity ?? 'INFO'] ?? 'pill-info'}>{n.severity ?? '-'}</span></td>
                <td className="text-bf-muted">{n.channels ?? '-'}</td>
                <td><span className={STATUS_PILL[n.status] ?? 'pill-info'}>{n.status}</span></td>
                <td className="text-[11px] text-bf-muted truncate max-w-md">
                  {n.payload_summary ? JSON.stringify(n.payload_summary).slice(0, 100) : '-'}
                </td>
              </tr>
            ))}
            {q.data?.items.length === 0 && (
              <tr><td colSpan={6} className="text-center py-6 text-bf-muted">알림 없음</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
