import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

function ProtectedRoute() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  // Only reviewers and org_admins can access the panel
  if (user.user_type === 'reporter') return <Navigate to="/login" replace />;
  return <Outlet />;
}

export default ProtectedRoute;
