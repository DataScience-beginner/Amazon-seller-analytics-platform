import { useCallback, useEffect, useMemo, useState } from 'react';

import { fetchHealth, fetchWorkspaces } from '../api/client';
import type { Workspace } from '../api/contracts';
import { Link, useLocation } from '../app/router';
import { WorkspaceContext, type WorkspaceSelection } from '../app/workspace';
import { DashboardPage } from '../pages/DashboardPage';
import { ImportDetailPage } from '../pages/ImportDetailPage';
import { ImportsPage } from '../pages/ImportsPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { PlanningPage } from '../pages/PlanningPage';
import { ProductDetailPage } from '../pages/ProductDetailPage';
import { ProductsPage } from '../pages/ProductsPage';
import { WorkspaceSetupPage } from '../pages/WorkspaceSetupPage';
import type { HealthResponse } from '../types/health';
import { ErrorState, LoadingState } from './Feedback';

const selectionStorageKey = 'selleros.workspace-selection';

const navItems = [
  { label: 'Dashboard', to: '/dashboard' },
  { label: 'Research', to: '/products' },
  { label: 'Imports', to: '/imports' },
  { label: 'Planning', to: '/planning' },
];

function firstSelection(workspaces: Workspace[]): WorkspaceSelection | null {
  for (const workspace of workspaces) {
    const marketplace = workspace.marketplaces[0];
    if (marketplace) return { workspace, marketplace };
  }
  return null;
}

function resolveSelection(workspaces: Workspace[], key: string | null): WorkspaceSelection | null {
  if (key) {
    const [organisationId, marketplaceId] = key.split(':');
    const workspace = workspaces.find((item) => item.organisation_id === organisationId);
    const marketplace = workspace?.marketplaces.find((item) => item.id === marketplaceId);
    if (workspace && marketplace) return { workspace, marketplace };
  }
  return firstSelection(workspaces);
}

function currentSelectionKey(selection: WorkspaceSelection): string {
  return `${selection.workspace.organisation_id}:${selection.marketplace.id}`;
}

function requireReadySystem(health: HealthResponse): HealthResponse {
  if (health.status !== 'ok' || health.database !== 'ok') {
    throw new Error('SellerOS is not ready. The application or database health check failed.');
  }
  return health;
}

function RouteContent() {
  const { pathname } = useLocation();
  if (pathname === '/' || pathname === '/dashboard') return <DashboardPage />;
  if (pathname === '/products') return <ProductsPage />;
  if (pathname.startsWith('/products/')) {
    return (
      <ProductDetailPage productId={decodeURIComponent(pathname.slice('/products/'.length))} />
    );
  }
  if (pathname === '/imports') return <ImportsPage />;
  if (pathname.startsWith('/imports/')) {
    return <ImportDetailPage importId={decodeURIComponent(pathname.slice('/imports/'.length))} />;
  }
  if (pathname === '/planning') return <PlanningPage />;
  if (pathname === '/setup') return <WorkspaceSetupPage />;
  return <NotFoundPage />;
}

function Shell({
  health,
  workspaces,
  selection,
  onSelect,
  onWorkspaceCreated,
}: {
  health: HealthResponse;
  workspaces: Workspace[];
  selection: WorkspaceSelection;
  onSelect: (organisationId: string, marketplaceId: string) => void;
  onWorkspaceCreated: (workspace: Workspace) => void;
}) {
  const { pathname } = useLocation();
  useEffect(() => {
    const focusTimer = window.setTimeout(() => {
      document.getElementById('main-content')?.focus({ preventScroll: true });
    }, 0);
    return () => window.clearTimeout(focusTimer);
  }, [pathname]);
  const context = useMemo(
    () => ({ workspaces, selection, select: onSelect, addWorkspace: onWorkspaceCreated }),
    [workspaces, selection, onSelect, onWorkspaceCreated],
  );

  return (
    <WorkspaceContext.Provider value={context}>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <div className="app-shell">
        <aside className="sidebar" aria-label="SellerOS">
          <Link to="/dashboard" className="brand">
            SellerOS
            <span>Decision intelligence</span>
          </Link>
          <nav aria-label="Primary navigation">
            {navItems.map((item) => {
              const active =
                item.to === '/dashboard'
                  ? pathname === '/' || pathname === '/dashboard'
                  : pathname === item.to || pathname.startsWith(`${item.to}/`);
              return (
                <Link to={item.to} key={item.to} aria-current={active ? 'page' : undefined}>
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="sidebar__scope">
            <label htmlFor="workspace-selection">Active workspace</label>
            <select
              id="workspace-selection"
              value={currentSelectionKey(selection)}
              onChange={(event) => {
                const [organisationId, marketplaceId] = event.target.value.split(':');
                onSelect(organisationId, marketplaceId);
              }}
            >
              {workspaces.flatMap((workspace) =>
                workspace.marketplaces.map((marketplace) => (
                  <option
                    value={`${workspace.organisation_id}:${marketplace.id}`}
                    key={`${workspace.organisation_id}:${marketplace.id}`}
                  >
                    {workspace.organisation_name} · {marketplace.code}
                  </option>
                )),
              )}
            </select>
            <Link to="/setup">Add workspace</Link>
            <span
              className="status-badge status-badge--positive"
              role="status"
              aria-label="System status: verified"
              title={`${health.application}: application and database checks passed`}
            >
              <span className="status-badge__mark" aria-hidden="true">
                ●
              </span>
              System verified
            </span>
          </div>
        </aside>
        <main className="main-content" id="main-content" tabIndex={-1}>
          <div className="topbar">
            <span>{selection.workspace.organisation_name}</span>
            <strong>{selection.marketplace.name}</strong>
          </div>
          <div className="content-container">
            <RouteContent />
          </div>
        </main>
      </div>
    </WorkspaceContext.Provider>
  );
}

export function AppShell() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[] | null>(null);
  const [selection, setSelection] = useState<WorkspaceSelection | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    setHealth(null);
    setWorkspaces(null);
    setSelection(null);
    Promise.all([fetchHealth(controller.signal), fetchWorkspaces(controller.signal)])
      .then(([healthResponse, workspaceResponse]) => {
        if (controller.signal.aborted) return;
        setHealth(requireReadySystem(healthResponse));
        setWorkspaces(workspaceResponse.items);
        setSelection(
          resolveSelection(workspaceResponse.items, localStorage.getItem(selectionStorageKey)),
        );
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(caught instanceof Error ? caught : new Error('Unable to load workspaces'));
        }
      });
    return () => controller.abort();
  }, [attempt]);

  const select = useCallback(
    (organisationId: string, marketplaceId: string) => {
      if (!workspaces) return;
      const next = resolveSelection(workspaces, `${organisationId}:${marketplaceId}`);
      if (!next) return;
      localStorage.setItem(selectionStorageKey, currentSelectionKey(next));
      setSelection(next);
    },
    [workspaces],
  );

  const addWorkspace = useCallback((workspace: Workspace) => {
    setWorkspaces((current) => {
      const withoutDuplicate = (current ?? []).filter(
        (item) => item.organisation_id !== workspace.organisation_id,
      );
      return [...withoutDuplicate, workspace];
    });
    const next = firstSelection([workspace]);
    if (next) {
      localStorage.setItem(selectionStorageKey, currentSelectionKey(next));
      setSelection(next);
    }
  }, []);

  if (error) {
    return (
      <main className="standalone-page">
        <ErrorState error={error} onRetry={() => setAttempt((value) => value + 1)} />
      </main>
    );
  }
  if (!health || !workspaces) {
    return <LoadingState label="Verifying SellerOS and loading your workspace…" />;
  }
  if (!selection) {
    return (
      <main className="standalone-page" id="main-content" tabIndex={-1}>
        <WorkspaceSetupPage onCreated={addWorkspace} firstUse />
      </main>
    );
  }

  return (
    <Shell
      health={health}
      workspaces={workspaces}
      selection={selection}
      onSelect={select}
      onWorkspaceCreated={addWorkspace}
    />
  );
}
