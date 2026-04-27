import { useState, useEffect } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle,
  Cpu,
  DollarSign,
  XCircle,
} from 'lucide-react';
import { dashboardApi } from '../api/client';
import type { DashboardStats } from '../types';

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { color: string; icon: typeof CheckCircle }> = {
    healthy: { color: '#22c55e', icon: CheckCircle },
    degraded: { color: '#eab308', icon: AlertTriangle },
    warning: { color: '#f97316', icon: AlertTriangle },
    critical: { color: '#ef4444', icon: XCircle },
  };

  const { color, icon: Icon } = config[status] || config.warning;

  return (
    <span className="status-badge" style={{ color }}>
      <Icon size={16} />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

export function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeframeHours, setTimeframeHours] = useState(24);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await dashboardApi.getStats(timeframeHours);
        setStats(data);
        setError(null);
      } catch {
        setError('Failed to load dashboard data');
      }
      setLoading(false);
    };

    void fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, [timeframeHours]);

  const formatUsd = (value: number) =>
    value < 0.01 ? `$${value.toFixed(6)}` : `$${value.toFixed(4)}`;

  if (loading) {
    return (
      <div className="page-loading">
        <Cpu size={48} className="spinner" />
        <p>Loading dashboard...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-error">
        <XCircle size={48} />
        <p>{error}</p>
      </div>
    );
  }

  const costSeries = stats?.llm_usage?.by_day || [];
  const projectSeries = stats?.llm_usage?.by_project || [];
  const budget = stats?.llm_usage?.budget;
  const agentLearning = stats?.llm_usage?.agent_learning;
  const maxDailyCost = Math.max(...costSeries.map((item) => item.estimated_cost_usd), 0.000001);
  const maxProjectCost = Math.max(
    ...projectSeries.map((item) => item.estimated_cost_usd),
    0.000001
  );

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <div className="dashboard-filters">
            {[
              { label: '24h', hours: 24 },
              { label: '7d', hours: 24 * 7 },
              { label: '30d', hours: 24 * 30 },
            ].map((option) => (
              <button
                key={option.hours}
                type="button"
                className={`dashboard-filter-btn ${timeframeHours === option.hours ? 'active' : ''}`}
                onClick={() => setTimeframeHours(option.hours)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <StatusBadge status={stats?.system_health?.overall_status || 'unknown'} />
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">
            <BarChart3 size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{stats?.command_stats?.totals?.total || 0}</span>
            <span className="stat-label">Total Commands</span>
          </div>
        </div>

        <div className="stat-card success">
          <div className="stat-icon">
            <CheckCircle size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{stats?.command_stats?.totals?.successful || 0}</span>
            <span className="stat-label">Successful</span>
          </div>
        </div>

        <div className="stat-card danger">
          <div className="stat-icon">
            <XCircle size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{stats?.command_stats?.totals?.failed || 0}</span>
            <span className="stat-label">Failed</span>
          </div>
        </div>

        <div className="stat-card info">
          <div className="stat-icon">
            <Activity size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{stats?.api_stats?.totals?.total_requests || 0}</span>
            <span className="stat-label">API Requests</span>
          </div>
        </div>

        <div className="stat-card success">
          <div className="stat-icon">
            <DollarSign size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">
              {formatUsd(stats?.llm_usage?.totals?.estimated_cost_usd || 0)}
            </span>
            <span className="stat-label">LLM Cost</span>
          </div>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="dashboard-card">
          <h3>Command Types</h3>
          <div className="chart-container">
            {stats?.command_stats?.by_type?.map((item) => (
              <div key={item.command_type} className="chart-bar">
                <div className="chart-bar-label">{item.command_type}</div>
                <div className="chart-bar-track">
                  <div
                    className="chart-bar-fill"
                    style={{
                      width: `${Math.min(
                        (item.count /
                          Math.max(
                            ...(stats?.command_stats?.by_type?.map((t) => t.count) || [1])
                          )) * 100,
                        100
                      )}%`,
                    }}
                  />
                </div>
                <div className="chart-bar-value">{item.count}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="dashboard-card">
          <h3>System Health</h3>
          <div className="health-metrics">
            <div className="health-item">
              <span>Command Error Rate</span>
              <span
                className={`health-value ${
                  (stats?.system_health?.command_error_rate || 0) > 0.1 ? 'danger' : 'success'
                }`}
              >
                {((stats?.system_health?.command_error_rate || 0) * 100).toFixed(1)}%
              </span>
            </div>
            <div className="health-item">
              <span>API Error Rate</span>
              <span
                className={`health-value ${
                  (stats?.system_health?.api_error_rate || 0) > 0.1 ? 'danger' : 'success'
                }`}
              >
                {((stats?.system_health?.api_error_rate || 0) * 100).toFixed(1)}%
              </span>
            </div>
            <div className="health-item">
              <span>Active Alerts</span>
              <span
                className={`health-value ${
                  (stats?.system_health?.active_alerts || 0) > 0 ? 'warning' : 'success'
                }`}
              >
                {stats?.system_health?.active_alerts || 0}
              </span>
            </div>
          </div>
        </div>

        <div className="dashboard-card">
          <h3>LLM Usage</h3>
          <div className="health-metrics">
            <div className="health-item">
              <span>Total Tokens</span>
              <span className="health-value success">
                {(stats?.llm_usage?.totals?.total_tokens || 0).toLocaleString()}
              </span>
            </div>
            <div className="health-item">
              <span>Prompt / Completion</span>
              <span className="health-value">
                {(stats?.llm_usage?.totals?.prompt_tokens || 0).toLocaleString()} /{' '}
                {(stats?.llm_usage?.totals?.completion_tokens || 0).toLocaleString()}
              </span>
            </div>
            <div className="health-item">
              <span>Cache Hit Rate</span>
              <span
                className={`health-value ${
                  (stats?.llm_usage?.totals?.cache_hit_rate_pct || 0) >= 70
                    ? 'success'
                    : 'warning'
                }`}
              >
                {(stats?.llm_usage?.totals?.cache_hit_rate_pct || 0).toFixed(1)}%
              </span>
            </div>
            <div className="health-item">
              <span>Cache Hit / Miss</span>
              <span className="health-value">
                {(stats?.llm_usage?.totals?.prompt_cache_hit_tokens || 0).toLocaleString()} /{' '}
                {(stats?.llm_usage?.totals?.prompt_cache_miss_tokens || 0).toLocaleString()}
              </span>
            </div>
            <div className="health-item">
              <span>Requests</span>
              <span className="health-value">
                {stats?.llm_usage?.totals?.request_count || 0}
              </span>
            </div>
            <div className="health-item">
              <span>Learned Patterns</span>
              <span className="health-value">
                {agentLearning?.learned_patterns || 0}
              </span>
            </div>
            <div className="health-item">
              <span>Learning Signals</span>
              <span className="health-value">
                {(agentLearning?.success_signals || 0).toLocaleString()} /{' '}
                {(agentLearning?.failure_signals || 0).toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        <div className="dashboard-card">
          <h3>Budget Status</h3>
          <div className="health-metrics">
            <div className="health-item">
              <span>Daily</span>
              <span className={`health-value budget-${budget?.daily?.level || 'disabled'}`}>
                {budget?.daily?.budget_usd
                  ? `${formatUsd(budget?.daily?.actual_cost_usd || 0)} / ${formatUsd(
                      budget?.daily?.budget_usd || 0
                    )}`
                  : 'Disabled'}
              </span>
            </div>
            <div className="health-item">
              <span>Daily Usage</span>
              <span className={`health-value budget-${budget?.daily?.level || 'disabled'}`}>
                {budget?.daily?.budget_usd ? `${(budget?.daily?.usage_pct || 0).toFixed(1)}%` : 'n/a'}
              </span>
            </div>
            <div className="health-item">
              <span>Monthly</span>
              <span className={`health-value budget-${budget?.monthly?.level || 'disabled'}`}>
                {budget?.monthly?.budget_usd
                  ? `${formatUsd(budget?.monthly?.actual_cost_usd || 0)} / ${formatUsd(
                      budget?.monthly?.budget_usd || 0
                    )}`
                  : 'Disabled'}
              </span>
            </div>
            <div className="health-item">
              <span>Monthly Usage</span>
              <span className={`health-value budget-${budget?.monthly?.level || 'disabled'}`}>
                {budget?.monthly?.budget_usd
                  ? `${(budget?.monthly?.usage_pct || 0).toFixed(1)}%`
                  : 'n/a'}
              </span>
            </div>
          </div>
        </div>

        <div className="dashboard-card full-width">
          <h3>Daily LLM Cost</h3>
          <div className="chart-container">
            {costSeries.length ? (
              costSeries.map((item) => (
                <div key={item.day} className="chart-bar">
                  <div className="chart-bar-label">{item.day.slice(5)}</div>
                  <div className="chart-bar-track">
                    <div
                      className="chart-bar-fill cost-bar"
                      style={{
                        width: `${Math.min((item.estimated_cost_usd / maxDailyCost) * 100, 100)}%`,
                      }}
                    />
                  </div>
                  <div className="chart-bar-value">{formatUsd(item.estimated_cost_usd)}</div>
                </div>
              ))
            ) : (
              <div className="empty-section">
                <p>Sem uso LLM suficiente para o período.</p>
              </div>
            )}
          </div>
        </div>

        <div className="dashboard-card full-width">
          <h3>Cost by Project</h3>
          <div className="chart-container">
            {projectSeries.length ? (
              projectSeries.map((item) => (
                <div key={item.project_name} className="chart-bar">
                  <div className="chart-bar-label">{item.project_name}</div>
                  <div className="chart-bar-track">
                    <div
                      className="chart-bar-fill cost-bar"
                      style={{
                        width: `${Math.min((item.estimated_cost_usd / maxProjectCost) * 100, 100)}%`,
                      }}
                    />
                  </div>
                  <div className="chart-bar-value">
                    {formatUsd(item.estimated_cost_usd)} / {item.total_tokens.toLocaleString()} tok
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-section">
                <p>Sem atribuição de projeto suficiente para o período.</p>
              </div>
            )}
          </div>
        </div>

        <div className="dashboard-card full-width">
          <h3>Budget Thresholds</h3>
          <div className="health-metrics">
            <div className="health-item">
              <span>Warning Threshold</span>
              <span className="health-value">
                {budget?.daily?.warning_threshold_pct ?? 0}% / {budget?.monthly?.warning_threshold_pct ?? 0}%
              </span>
            </div>
            <div className="health-item">
              <span>Critical Threshold</span>
              <span className="health-value">
                {budget?.daily?.critical_threshold_pct ?? 0}% / {budget?.monthly?.critical_threshold_pct ?? 0}%
              </span>
            </div>
            <div className="health-item">
              <span>Daily Trigger</span>
              <span className="health-value">
                {budget?.daily?.budget_usd
                  ? `${formatUsd(budget?.daily?.warning_threshold_cost_usd || 0)} -> ${formatUsd(
                      budget?.daily?.critical_threshold_cost_usd || 0
                    )}`
                  : 'Disabled'}
              </span>
            </div>
            <div className="health-item">
              <span>Monthly Trigger</span>
              <span className="health-value">
                {budget?.monthly?.budget_usd
                  ? `${formatUsd(budget?.monthly?.warning_threshold_cost_usd || 0)} -> ${formatUsd(
                      budget?.monthly?.critical_threshold_cost_usd || 0
                    )}`
                  : 'Disabled'}
              </span>
            </div>
          </div>
        </div>

        <div className="dashboard-card full-width">
          <h3>Recent Alerts</h3>
          {stats?.active_alerts?.length ? (
            <div className="alerts-list">
              {stats.active_alerts.map((alert) => (
                <div key={alert.id} className={`alert-item alert-${alert.severity}`}>
                  <AlertTriangle size={16} />
                  <div className="alert-info">
                    <span className="alert-type">{alert.alert_type}</span>
                    <span className="alert-message">{alert.message}</span>
                  </div>
                  <span className="alert-time">{new Date(alert.timestamp).toLocaleString()}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-section">
              <CheckCircle size={32} />
              <p>No active alerts</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
