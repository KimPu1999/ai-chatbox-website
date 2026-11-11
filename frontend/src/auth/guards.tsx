import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from './AuthProvider';

export function ProtectedRoute() {
  const { state } = useAuth(); const location = useLocation();
  if (state === 'loading') return <PageState text="Checking your session…" />;
  if (state === 'error') return <PageState text="The API is unavailable. Please try again." />;
  return state === 'authenticated' ? <Outlet /> : <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
}

export function AdminRoute() {
  const { user } = useAuth();
  return user?.role === 'admin' || user?.role === 'superadmin' ? <Outlet /> : <Navigate to="/" replace />;
}

function PageState({ text }: { text: string }) { return <div className="grid min-h-screen place-items-center bg-slate-50 text-sm text-slate-500 dark:bg-slate-950 dark:text-slate-300">{text}</div>; }
