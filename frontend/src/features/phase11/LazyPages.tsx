import { lazy } from 'react';

export const PlanPage = lazy(() => import('./pages').then((module) => ({ default: module.PlanPage })));
export const UsagePage = lazy(() => import('./pages').then((module) => ({ default: module.UsagePage })));
export const PrivacyPage = lazy(() => import('./pages').then((module) => ({ default: module.PrivacyPage })));
export const SupportPage = lazy(() => import('./pages').then((module) => ({ default: module.SupportPage })));
export const OperationsPage = lazy(() => import('./pages').then((module) => ({ default: module.OperationsPage })));
