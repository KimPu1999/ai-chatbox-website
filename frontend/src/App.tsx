import { Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthProvider';
import { AdminRoute, ProtectedRoute } from './auth/guards';
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage, VerifyEmailPage } from './auth/pages';
import { AccountSecurityPage, AdminUsersPage } from './auth/secure-pages';
import { ChatPage } from './features/chat/pages/ChatPage';
import { SharedConversationViewer } from './features/chat/components/SharedConversationViewer';
import { DocumentLibraryPage, DocumentViewerPage } from './features/documents/components';
import { PlatformLoginPage, PlatformRoute, PlatformOverviewPage, UsersPage, UsageAnalyticsPage, CostsPage, ModelsPage, QuotasPage, StoragePage, AuditLogsPage, HealthPage, SettingsPage } from './features/platform/LazyPages';
import { OperationsPage, PlanPage, PrivacyPage, SupportPage, UsagePage } from './features/phase11/LazyPages';

function PlatformLoading() {
  return <div className="grid min-h-screen place-items-center bg-slate-50 text-sm text-slate-500 dark:bg-slate-950 dark:text-slate-300">Loading platform…</div>;
}

export default function App() {
  return <BrowserRouter><AuthProvider><Suspense fallback={<PlatformLoading />}><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<RegisterPage />} />
    <Route path="/verify-email" element={<VerifyEmailPage />} />
    <Route path="/forgot-password" element={<ForgotPasswordPage />} />
    <Route path="/reset-password" element={<ResetPasswordPage />} />
    <Route path="/platform/login" element={<PlatformLoginPage />} />
    <Route path="/shared/:publicToken" element={<SharedConversationViewer />} />
    <Route element={<ProtectedRoute />}>
      <Route path="/" element={<Navigate to="/chat" replace />} />
      <Route path="/chat" element={<ChatPage />} />
      <Route path="/chat/:conversationId" element={<ChatPage />} />
      <Route path="/documents" element={<DocumentLibraryPage />} />
      <Route path="/documents/:documentId" element={<DocumentViewerPage />} />
      <Route path="/account/security" element={<AccountSecurityPage />} />
      <Route path="/account/plan" element={<PlanPage />} />
      <Route path="/account/usage" element={<UsagePage />} />
      <Route path="/account/privacy" element={<PrivacyPage />} />
      <Route path="/support" element={<SupportPage />} />
      <Route path="/support/tickets" element={<SupportPage />} />
      <Route element={<AdminRoute />}><Route path="/admin/users" element={<AdminUsersPage />} /></Route>
    </Route>
    <Route element={<PlatformRoute />}>
      <Route path="/platform/overview" element={<PlatformOverviewPage />} />
      <Route path="/platform/users" element={<UsersPage />} />
      <Route path="/platform/usage" element={<UsageAnalyticsPage />} />
      <Route path="/platform/costs" element={<CostsPage />} />
      <Route path="/platform/models" element={<ModelsPage />} />
      <Route path="/platform/quotas" element={<QuotasPage />} />
      <Route path="/platform/storage" element={<StoragePage />} />
      <Route path="/platform/audit-logs" element={<AuditLogsPage />} />
      <Route path="/platform/health" element={<HealthPage />} />
      <Route path="/platform/settings" element={<SettingsPage />} />
      <Route path="/platform/operations" element={<OperationsPage />} />
      <Route path="/platform/operations/monitoring" element={<OperationsPage />} />
      <Route path="/platform/operations/plans" element={<OperationsPage />} />
      <Route path="/platform/operations/feature-flags" element={<OperationsPage />} />
      <Route path="/platform/operations/support" element={<OperationsPage />} />
      <Route path="/platform/operations/incidents" element={<OperationsPage />} />
    </Route>
    <Route path="*" element={<Navigate to="/chat" replace />} />
  </Routes></Suspense></AuthProvider></BrowserRouter>;
}
