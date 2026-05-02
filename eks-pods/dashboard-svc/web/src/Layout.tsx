import { Outlet, NavLink, useParams } from 'react-router-dom';
import { useState } from 'react';
import { useLiveStream } from './useLiveStream';
import type { Role } from './api';

const ROLES: Role[] = ['hq-admin', 'wh-manager-1', 'wh-manager-2', 'branch-clerk'];

export const RoleContext = (() => {
  // Lift to a tiny module-level state so children can read it.
  // (For a 1-2 page demo this beats setting up Context.)
  const listeners = new Set<(r: Role) => void>();
  let role: Role = 'hq-admin';
  return {
    get: () => role,
    set: (r: Role) => { role = r; listeners.forEach((f) => f(r)); },
    subscribe: (f: (r: Role) => void) => { listeners.add(f); return () => { listeners.delete(f); }; },
  };
})();

export default function Layout() {
  const params = useParams();
  const [role, setRoleLocal] = useState<Role>(RoleContext.get());
  const { status, counts } = useLiveStream(role);

  const setRole = (r: Role) => {
    setRoleLocal(r);
    RoleContext.set(r);
  };

  return (
    <div className="min-h-screen bg-gh-bg text-gh-text p-6">
      <header className="border-b-2 border-gh-border pb-2 mb-4 flex items-center justify-between">
        <h1 className="m-0 text-lg">
          📊 BookFlow · dashboard-svc
          <span className={status === 'up' ? 'pill-up ml-2' : status === 'connecting' ? 'pill-connecting ml-2' : 'pill-down ml-2'}>
            WS {status}
          </span>
        </h1>
        <nav className="flex gap-2 text-xs">
          <NavLink to={`/overview/${params.wh ?? 1}`} className={({isActive}) => isActive ? 'text-gh-blue' : 'text-gh-muted hover:text-gh-text'}>Overview</NavLink>
          <NavLink to="/pending" className={({isActive}) => isActive ? 'text-gh-blue' : 'text-gh-muted hover:text-gh-text'}>Pending Orders</NavLink>
        </nav>
      </header>

      <div className="flex gap-3 mb-4 items-center">
        <span className="text-xs text-gh-muted">role</span>
        <select className="ipt" value={role} onChange={(e) => setRole(e.target.value as Role)}>
          {ROLES.map((r) => <option key={r}>{r}</option>)}
        </select>

        <div className="ml-auto flex gap-2">
          {Object.entries(counts).map(([k, v]) => (
            <div key={k} className="metric min-w-[90px]">
              <div className="metric-label">{k.split('.')[0]}</div>
              <div className="metric-value text-base">{v}</div>
            </div>
          ))}
        </div>
      </div>

      <Outlet context={{ role }} />
    </div>
  );
}
