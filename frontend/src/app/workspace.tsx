import { createContext, useContext } from 'react';

import type { Marketplace, Workspace } from '../api/contracts';

export type WorkspaceSelection = {
  workspace: Workspace;
  marketplace: Marketplace;
};

type WorkspaceContextValue = {
  workspaces: Workspace[];
  selection: WorkspaceSelection;
  select: (organisationId: string, marketplaceId: string) => void;
  addWorkspace: (workspace: Workspace) => void;
};

export const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function useWorkspace(): WorkspaceContextValue {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error('useWorkspace must be used inside WorkspaceContext');
  return value;
}
