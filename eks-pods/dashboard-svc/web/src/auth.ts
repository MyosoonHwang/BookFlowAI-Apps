// Mock auth state in localStorage. Phase 4: real Entra OIDC swap.
import { useEffect, useState } from 'react';

export type Role = 'hq-admin' | 'wh-manager-1' | 'wh-manager-2' | 'branch-clerk';

const STORAGE_KEY = 'bookflow.role';

const ROLE_LABELS: Record<Role, string> = {
  'hq-admin':     '본사 관리자',
  'wh-manager-1': '창고 매니저 (수도권)',
  'wh-manager-2': '창고 매니저 (영남)',
  'branch-clerk': '지점 직원',
};

const ROLE_GROUP: Record<Role, 'HQ' | 'WH' | 'BRANCH'> = {
  'hq-admin': 'HQ', 'wh-manager-1': 'WH', 'wh-manager-2': 'WH', 'branch-clerk': 'BRANCH',
};

export function roleLabel(r: Role): string { return ROLE_LABELS[r]; }
export function roleGroup(r: Role): 'HQ' | 'WH' | 'BRANCH' { return ROLE_GROUP[r]; }
export function token(role: Role): string { return `Bearer mock-token-${role}`; }

export function getRole(): Role | null {
  const v = localStorage.getItem(STORAGE_KEY);
  return v ? (v as Role) : null;
}
export function setRole(r: Role | null): void {
  if (r) localStorage.setItem(STORAGE_KEY, r);
  else localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new Event('bookflow-role-changed'));
}

export function useRole(): [Role | null, (r: Role | null) => void] {
  const [role, set] = useState<Role | null>(getRole());
  useEffect(() => {
    const f = () => set(getRole());
    window.addEventListener('bookflow-role-changed', f);
    window.addEventListener('storage', f);
    return () => {
      window.removeEventListener('bookflow-role-changed', f);
      window.removeEventListener('storage', f);
    };
  }, []);
  return [role, (r) => { setRole(r); set(r); }];
}
