import { Navigate } from 'react-router-dom';
import useAuth from '../hooks/useAuth';

/**
 * ProtectedRoute
 * Wraps routes that require authentication.
 * If not authenticated → redirects to /login.
 * If role prop provided, checks role matches; otherwise redirects to /.
 */
export default function ProtectedRoute({ children, role }) {
  const { isAuthenticated, role: userRole } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (role && userRole !== role) {
    return <Navigate to="/" replace />;
  }

  return children;
}
