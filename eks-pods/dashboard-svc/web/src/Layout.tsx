import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { roleLabel, roleGroup, useRole, type Role } from './auth';
import { useLiveStream } from './useLiveStream';

type NavItem = { to: string; label: string; allow: 'HQ' | 'WH' | 'BRANCH' | 'ALL' };

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: '본사',
    items: [
      { to: '/kpi',         label: '실시간 KPI',       allow: 'HQ' },
      { to: '/inventory',   label: '전사 재고',         allow: 'HQ' },
      { to: '/books',       label: '도서 카탈로그',     allow: 'HQ' },
      { to: '/decision',    label: '의사결정',          allow: 'HQ' },
      { to: '/approval',    label: '승인 / 거절',       allow: 'HQ' },
      { to: '/returns',     label: '반품 처리',          allow: 'HQ' },
      { to: '/requests',    label: '신간 신청',          allow: 'HQ' },
      { to: '/spikes',      label: '급등 감지',          allow: 'HQ' },
    ],
  },
  {
    section: '창고',
    items: [
      { to: '/wh-dashboard',    label: '창고 대시보드',  allow: 'WH' },
      { to: '/wh-approve',      label: '승인 큐',         allow: 'WH' },
      { to: '/wh-transfer',     label: '권역 이동',       allow: 'WH' },
      { to: '/wh-instructions', label: '출고 지시서',     allow: 'WH' },
      { to: '/wh-manual',       label: '수동 조정',       allow: 'WH' },
    ],
  },
  {
    section: '지점',
    items: [
      { to: '/branch-inventory', label: '매장 재고',     allow: 'BRANCH' },
      { to: '/branch-inbound',   label: '입고 확인',     allow: 'BRANCH' },
      { to: '/branch-sales',     label: '매장 매출',     allow: 'BRANCH' },
      { to: '/branch-curation',  label: '큐레이션',      allow: 'BRANCH' },
      { to: '/branch-manual',    label: '수동 조정',     allow: 'BRANCH' },
    ],
  },
  {
    section: '공통',
    items: [
      { to: '/notifications', label: '알림 로그',        allow: 'ALL' },
      { to: '/live',          label: '실시간 이벤트',     allow: 'ALL' },
    ],
  },
];

const STATUS_PILL: Record<string, string> = {
  up: 'pill-up', connecting: 'pill-connecting', down: 'pill-down',
};

const STATUS_LABEL: Record<string, string> = {
  up: '연결됨', connecting: '연결 중', down: '끊김',
};

const PAGE_LABEL: Record<string, string> = {
  kpi: '실시간 KPI',
  inventory: '전사 재고',
  books: '도서 카탈로그',
  decision: '의사결정',
  approval: '승인 / 거절',
  returns: '반품 처리',
  requests: '신간 신청',
  spikes: '급등 감지',
  'wh-dashboard': '창고 대시보드',
  'wh-approve': '창고 승인 큐',
  'wh-transfer': '권역 이동',
  'wh-instructions': '출고 지시서',
  'wh-manual': '창고 수동 조정',
  'branch-inventory': '매장 재고',
  'branch-inbound': '입고 확인',
  'branch-sales': '매장 매출',
  'branch-curation': '큐레이션',
  'branch-manual': '매장 수동 조정',
  notifications: '알림 로그',
  live: '실시간 이벤트',
};

export default function Layout() {
  const [role, setRole] = useRole();
  const nav = useNavigate();
  const loc = useLocation();
  const { status, counts } = useLiveStream(role);

  if (!role) return null;

  const group = roleGroup(role);
  const visible = NAV.map((s) => ({
    section: s.section,
    items: s.items.filter((i) => i.allow === 'ALL' || i.allow === group),
  })).filter((s) => s.items.length > 0);

  const onLogout = () => { setRole(null); nav('/login', { replace: true }); };
  const seg = loc.pathname.split('/').filter(Boolean)[0] ?? 'home';
  const pageTitle = PAGE_LABEL[seg] ?? seg;
  const groupLabel = group === 'HQ' ? '본사' : group === 'WH' ? '창고' : '지점';

  return (
    <div className="min-h-screen bg-bf-bg flex">
      <aside className="w-[220px] shrink-0 bg-bf-sidebar text-white flex flex-col">
        <div className="px-5 py-4 border-b border-bf-sidebar2">
          <div className="text-base font-bold flex items-center gap-2">📚 BookFlow</div>
          <div className="text-[10px] text-gray-400 mt-0.5">도서 유통 통합 관제</div>
        </div>
        <nav className="flex-1 overflow-y-auto py-3 flex flex-col gap-3">
          {visible.map((s) => (
            <div key={s.section}>
              <div className="text-[10px] uppercase tracking-wider text-gray-500 px-5 mb-1">{s.section}</div>
              <ul className="flex flex-col">
                {s.items.map((i) => (
                  <li key={i.to}>
                    <NavLink
                      to={i.to}
                      className={({ isActive }) =>
                        `flex items-center px-5 py-1.5 text-xs border-l-[3px] transition ${
                          isActive
                            ? 'bg-bf-sidebar2 text-white border-bf-primary'
                            : 'text-gray-300 hover:bg-bf-sidebar2 hover:text-white border-transparent'
                        }`
                      }
                    >
                      {i.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className="px-5 py-3 border-t border-bf-sidebar2">
          <div className="text-[10px] uppercase tracking-wider text-gray-500">{groupLabel}</div>
          <div className="text-xs text-white mb-2">{roleLabel(role)}</div>
          <button onClick={onLogout} className="text-[11px] text-gray-400 hover:text-white">
            로그아웃
          </button>
        </div>
      </aside>

      <main className="flex-1 flex flex-col min-w-0">
        <header className="h-12 border-b border-bf-border px-6 flex items-center gap-4 bg-bf-panel shrink-0">
          <div className="text-sm text-bf-text font-semibold">{pageTitle}</div>
          <span className={STATUS_PILL[status] ?? 'pill-down'} title="WebSocket broker · Redis 4채널">실시간 {STATUS_LABEL[status] ?? status}</span>
          <div className="flex gap-3 ml-auto text-[11px]">
            <span title="stock.changed · pos-ingestor Lambda" className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-bf-success inline-block"></span>
              <span className="text-bf-muted">재고변동</span><b className="text-bf-text">{counts['stock.changed']}</b>
            </span>
            <span title="order.pending · 주문 대기" className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-bf-warn inline-block"></span>
              <span className="text-bf-muted">주문</span><b className="text-bf-text">{counts['order.pending']}</b>
            </span>
            <span title="spike.detected · 급등 감지 Lambda" className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-bf-danger inline-block"></span>
              <span className="text-bf-muted">급등</span><b className="text-bf-text">{counts['spike.detected']}</b>
            </span>
            <span title="newbook.request · 출판사 신간 신청" className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-purple-600 inline-block"></span>
              <span className="text-bf-muted">신간</span><b className="text-bf-text">{counts['newbook.request']}</b>
            </span>
          </div>
        </header>
        <div className="flex-1 overflow-auto p-6">
          <Outlet context={{ role } satisfies { role: Role }} />
        </div>
      </main>
    </div>
  );
}
