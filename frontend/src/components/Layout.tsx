import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { MessageSquare, BarChart3, Settings, LogOut, Cpu, Shield } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const navItems = [
  { path: '/chat', icon: MessageSquare, label: 'Chat' },
  { path: '/dashboard', icon: BarChart3, label: 'Dashboard' },
  { path: '/settings', icon: Settings, label: 'Settings' },
];

export function Layout() {
  const { auth, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <Cpu size={28} className="sidebar-logo" />
          <span className="sidebar-title">DevSynapse</span>
        </div>

        <nav className="sidebar-nav">
          {navItems.map(({ path, icon: Icon, label }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                `nav-item ${isActive ? 'active' : ''}`
              }
            >
              <Icon size={20} />
              <span>{label}</span>
            </NavLink>
          ))}
          {auth.user?.role === 'admin' && (
            <NavLink
              to="/admin"
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <Shield size={20} />
              <span>Admin</span>
            </NavLink>
          )}
        </nav>

        <div className="sidebar-footer">
          {auth.isAuthenticated && (
            <div className="user-info">
              <span className="user-name">{auth.user?.username}</span>
              <span className="user-role">{auth.user?.role}</span>
            </div>
          )}
          <button className="logout-btn" onClick={handleLogout}>
            <LogOut size={18} />
            <span>Logout</span>
          </button>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
