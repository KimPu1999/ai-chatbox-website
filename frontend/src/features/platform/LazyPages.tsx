import { lazy } from 'react';

// Keep the admin control center out of the user application's initial bundle.
// Each screen is loaded only when its route is visited; platform authorization
// is still enforced by the server and PlatformRoute.
export const PlatformLoginPage = lazy(() => import('./pages').then((module) => ({ default: module.PlatformLoginPage })));
export const PlatformRoute = lazy(() => import('./pages').then((module) => ({ default: module.PlatformRoute })));
export const PlatformOverviewPage = lazy(() => import('./pages').then((module) => ({ default: module.PlatformOverviewPage })));
export const UsersPage = lazy(() => import('./pages').then((module) => ({ default: module.UsersPage })));
export const UsageAnalyticsPage = lazy(() => import('./pages').then((module) => ({ default: module.UsageAnalyticsPage })));
export const CostsPage = lazy(() => import('./pages').then((module) => ({ default: module.CostsPage })));
export const ModelsPage = lazy(() => import('./pages').then((module) => ({ default: module.ModelsPage })));
export const QuotasPage = lazy(() => import('./pages').then((module) => ({ default: module.QuotasPage })));
export const StoragePage = lazy(() => import('./pages').then((module) => ({ default: module.StoragePage })));
export const AuditLogsPage = lazy(() => import('./pages').then((module) => ({ default: module.AuditLogsPage })));
export const HealthPage = lazy(() => import('./pages').then((module) => ({ default: module.HealthPage })));
export const SettingsPage = lazy(() => import('./pages').then((module) => ({ default: module.SettingsPage })));
