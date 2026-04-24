import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { Chat } from './pages/Chat';
import { Dashboard } from './pages/Dashboard';
import { Settings } from './pages/Settings';
import { Login } from './pages/Login';
import { Admin } from './pages/Admin';

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
        <Route path="/chat" element={<Chat />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/settings" element={<Settings />} />
        <Route
          path="/admin"
          element={
            auth.user?.role === 'admin' ? <Admin /> : <Navigate to="/chat" replace />
          }
        />
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
