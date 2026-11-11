import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthProvider';
import { AdminRoute, ProtectedRoute } from './auth/guards';
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage, VerifyEmailPage } from './auth/pages';
import { AccountSecurityPage, AdminUsersPage } from './auth/secure-pages';
import { ChatPage } from './features/chat/pages/ChatPage';
import { SharedConversationViewer } from './features/chat/components/SharedConversationViewer';

export default function App() {
  return <BrowserRouter><AuthProvider><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<RegisterPage />} />
    <Route path="/verify-email" element={<VerifyEmailPage />} />
    <Route path="/forgot-password" element={<ForgotPasswordPage />} />
    <Route path="/reset-password" element={<ResetPasswordPage />} />
    <Route path="/shared/:publicToken" element={<SharedConversationViewer />} />
    <Route element={<ProtectedRoute />}>
      <Route path="/" element={<Navigate to="/chat" replace />} />
      <Route path="/chat" element={<ChatPage />} />
      <Route path="/chat/:conversationId" element={<ChatPage />} />
      <Route path="/account/security" element={<AccountSecurityPage />} />
      <Route element={<AdminRoute />}><Route path="/admin/users" element={<AdminUsersPage />} /></Route>
    </Route>
    <Route path="*" element={<Navigate to="/chat" replace />} />
  </Routes></AuthProvider></BrowserRouter>;
}
