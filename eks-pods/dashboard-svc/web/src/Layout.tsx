import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { roleLabel, roleGroup, useRole, type Role } from './auth';
import { useLiveStream } from './useLiveStream';

type NavItem = { to: string; label: string; allow: 'HQ' | 'WH' | 'BRANCH' | 'ALL' };

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: 'HQ · 본사',
    items: [
      { to: '/kpi',      label: 'KPI 모니터링',  allow: 'HQ' },
      { to: '/books',    label: 'Books · 도서',  allow: 'HQ' },
      { to: '/decision', label: 'Decision',    allow: 'HQ' },
      { to: '/approval', label: 'Approval',    allow: 'HQ' },
      { to: '/returns',  label: 'Returns',     allow: 'HQ' },
      { to: '/requests', label: 'Requests',    allow: 'HQ' },
      { to: '/spikes',   label: 'Spike Detect',allow: 'HQ' },
    ],
  },
  {
    section: 'WH · 창고',
    items: [
      { to: '/wh-dashboard', label: 'Dashboard', allow: 'WH' },
      { to: '/wh-approve',   label: 'Approve',   allow: 'WH' },
    ],
  },
  {
    section: 'Branch · 지점',
    items: [
      { to: '/branch-inventory', label: 'Inventory', allow: 'BRANCH' },
      { to: '/branch-sales',     label: 'Sales',     allow: 'BRANCH' },
    ],
  },
  {
    section: '공통',
    items: [
      { to: '/notifications', label: 'Notifications', allow: 'ALL' },
      { to: '/live',          label: 'Live Events',   allow: 'ALL' },
    ],
  },
];

const STATUS_PILL: Record<string, string> = {
  up: 'pill-up', connecting: 'pill-connecting', down: 'pill-down',
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

  return (
    <div className="min-h-screen bg-bf-bg flex">
      <aside className="w-[220px] shrink-0 bg-bf-sidebar text-white flex flex-col">
        <div className="px-5 py-4 border-b border-bf-sidebar2">
          <div className="text-base font-bold flex items-center gap-2">📚 BookFlow</div>
          <div className="text-[10px] text-gray-400 mt-0.5">V6.4 · MSA Demo</div>
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
          <div className="text-[10px] uppercase tracking-wider text-gray-500">{group}</div>
          <div className="text-xs text-white mb-2">{roleLabel(role)}</div>
          <button onClick={onLogout} className="text-[11px] text-gray-400 hover:text-white">
            로그아웃
          </button>
        </div>
      </aside>

      <main className="flex-1 flex flex-col min-w-0">
        <header className="h-12 border-b border-bf-border px-6 flex items-center gap-4 bg-bf-panel shrink-0">
          <div className="text-[11px] text-bf-muted uppercase tracking-wider">{seg}</div>
          <span className={STATUS_PILL[status] ?? 'pill-down'}>WS {status}</span>
          <div className="flex gap-3 ml-auto text-[11px]">
            <span title="stock.changed (pos-ingestor Lambda)" className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-bf-success inline-block"></span>
              <span className="text-bf-muted">stock</span><b className="text-bf-text">{counts['stock.changed']}</b>
            </span>
            <span title="order.pending" className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-bf-warn inline-block"></span>
              <span className="text-bf-muted">order</span><b className="text-bf-text">{counts['order.pending']}</b>
            </span>
            <span title="spike.detected (spike-detect Lambda)" className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-bf-danger inline-block"></span>
              <span className="text-bf-muted">spike</span><b className="text-bf-text">{counts['spike.detected']}</b>
            </span>
            <span title="newbook.request (publisher-watcher CronJob)" className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-purple-600 inline-block"></span>
              <span className="text-bf-muted">newbook</span><b className="text-bf-text">{counts['newbook.request']}</b>
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
