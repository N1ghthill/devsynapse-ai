import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import {
  BarChart3,
  CircleDot,
  Cpu,
  Library,
  LogOut,
  MessageSquare,
  Settings,
  Shield,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const navItems = [
  { path: '/chat', icon: MessageSquare, label: 'Chat' },
  { path: '/dashboard', icon: BarChart3, label: 'Painel' },
  { path: '/knowledge', icon: Library, label: 'Conhecimento' },
  { path: '/settings', icon: Settings, label: 'Ajustes' },
];

export function Layout() {
  const { auth, logout } = useAuth();
  const navigate = useNavigate();
  const userInitial = auth.user?.username?.slice(0, 1).toUpperCase() || 'D';

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="brand-mark" aria-hidden="true">
            <Cpu size={22} className="sidebar-logo" />
          </div>
          <div className="brand-copy">
            <span className="sidebar-title">DevSynapse</span>
            <span className="sidebar-kicker">Workspace local de IA</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <span className="nav-section-label">Workspace</span>
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
          <div className="sidebar-status">
            <CircleDot size={12} />
            <span>Execução local</span>
          </div>
          {auth.isAuthenticated && (
            <div className="user-card">
              <div className="user-avatar" aria-hidden="true">
                {userInitial}
              </div>
              <div className="user-info">
                <span className="user-name">{auth.user?.username}</span>
                <span className="user-role">{auth.user?.role}</span>
              </div>
            </div>
          )}
          <button className="logout-btn" onClick={handleLogout}>
            <LogOut size={18} />
            <span>Sair</span>
          </button>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
