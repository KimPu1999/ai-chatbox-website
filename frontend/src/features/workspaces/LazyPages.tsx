import { lazy } from 'react';
export const WorkspacesPage = lazy(() => import('./pages').then((m) => ({ default: m.WorkspacesPage })));
export const WorkspaceOverviewPage = lazy(() => import('./pages').then((m) => ({ default: m.WorkspaceOverviewPage })));
export const WorkspaceMembersPage = lazy(() => import('./pages').then((m) => ({ default: m.WorkspaceMembersPage })));
export const WorkspaceKnowledgePage = lazy(() => import('./pages').then((m) => ({ default: m.WorkspaceKnowledgePage })));
export const WorkspacePlaceholderPage = lazy(() => import('./pages').then((m) => ({ default: m.WorkspacePlaceholderPage })));
