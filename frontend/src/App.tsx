import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  Outlet,
  useLocation,
} from 'react-router-dom';
import { useEffect, useState } from 'react';
import { authApi } from './api/client';
import { Layout } from './components/Layout';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { Chat } from './pages/Chat';
import { Dashboard } from './pages/Dashboard';
import { Settings } from './pages/Settings';
import { Knowledge } from './pages/Knowledge';
import { Login } from './pages/Login';
import { Admin } from './pages/Admin';
import { Setup } from './pages/Setup';

function SetupGate() {
  const { auth } = useAuth();
  const location = useLocation();
  const [setupReasons, setSetupReasons] = useState<string[]>([]);
  const [checkingSetup, setCheckingSetup] = useState(true);

  useEffect(() => {
    let cancelled = false;

    authApi
      .bootstrapStatus()
      .then((status) => {
        if (!cancelled) {
          setSetupReasons(status.requires_setup ? status.reasons : []);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSetupReasons([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setCheckingSetup(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  if (checkingSetup) {
    return (
      <div className="page-loading">
        <p>Checking setup...</p>
      </div>
    );
  }

  const blockingSetupReasons =
    auth.user?.role === 'admin'
      ? setupReasons.filter((reason) => reason !== 'admin_password')
      : setupReasons;

  if (blockingSetupReasons.length > 0 && location.pathname !== '/setup') {
    if (auth.user?.role !== 'admin') {
      return (
        <div className="page-error">
          <p>Admin setup is required.</p>
        </div>
      );
    }
    return <Navigate to="/setup" replace />;
  }

  return <Outlet />;
}

function AppShell() {
  const { auth } = useAuth();

  if (auth.isLoading) {
    return (
      <div className="page-loading">
        <p>Validating session...</p>
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={auth.isAuthenticated ? <Navigate to="/chat" replace /> : <Login />}
      />
      <Route
        element={auth.isAuthenticated ? <Layout /> : <Navigate to="/login" replace />}
      >
        <Route element={<SetupGate />}>
          <Route
            path="/setup"
            element={
              auth.user?.role === 'admin' ? <Setup /> : <Navigate to="/chat" replace />
            }
          />
          <Route path="/chat" element={<Chat />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/knowledge" element={<Knowledge />} />
          <Route path="/settings" element={<Settings />} />
          <Route
            path="/admin"
            element={
              auth.user?.role === 'admin' ? <Admin /> : <Navigate to="/chat" replace />
            }
          />
        </Route>
      </Route>
      <Route
        path="*"
        element={<Navigate to={auth.isAuthenticated ? '/chat' : '/login'} replace />}
      />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <AppShell />
      </Router>
    </AuthProvider>
  );
}

export default App;
