import { useState, useEffect } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Brain,
  CheckCircle,
  Cpu,
  DollarSign,
  Library,
  ShieldAlert,
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
  const labels: Record<string, string> = {
    healthy: 'Saudável',
    degraded: 'Degradado',
    warning: 'Atenção',
    critical: 'Crítico',
  };

  const { color, icon: Icon } = config[status] || config.warning;

  return (
    <span className="status-badge" style={{ color }}>
      <Icon size={16} />
      {labels[status] || 'Desconhecido'}
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
        setError('Falha ao carregar os dados do painel');
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
        <p>Carregando painel...</p>
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
  const knowledge = stats?.llm_usage?.knowledge;
  const telemetry = stats?.llm_usage?.telemetry?.by_user_model || [];
  const maxDailyCost = Math.max(...costSeries.map((item) => item.estimated_cost_usd), 0.000001);
  const maxProjectCost = Math.max(
    ...projectSeries.map((item) => item.estimated_cost_usd),
    0.000001
  );

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <div>
          <h1>Painel</h1>
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
            <span className="stat-label">Comandos</span>
          </div>
        </div>

        <div className="stat-card success">
          <div className="stat-icon">
            <CheckCircle size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{stats?.command_stats?.totals?.successful || 0}</span>
            <span className="stat-label">Sucesso</span>
          </div>
        </div>

        <div className="stat-card warning">
          <div className="stat-icon">
            <ShieldAlert size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{stats?.command_stats?.totals?.blocked || 0}</span>
            <span className="stat-label">Bloqueados</span>
          </div>
        </div>

        <div className="stat-card danger">
          <div className="stat-icon">
            <XCircle size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{stats?.command_stats?.totals?.failed || 0}</span>
            <span className="stat-label">Falhas</span>
          </div>
        </div>

        <div className="stat-card info">
          <div className="stat-icon">
            <Activity size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{stats?.api_stats?.totals?.total_requests || 0}</span>
            <span className="stat-label">Requisições API</span>
          </div>
        </div>

        <div className="stat-card info">
          <div className="stat-icon">
            <Brain size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{knowledge?.memories.total_memories || 0}</span>
            <span className="stat-label">Memórias</span>
          </div>
        </div>

        <div className="stat-card info">
          <div className="stat-icon">
            <Library size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{knowledge?.skills.active_skills || 0}</span>
            <span className="stat-label">Skills</span>
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
            <span className="stat-label">Custo LLM</span>
          </div>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="dashboard-card">
          <h3>Tipos de Comando</h3>
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
          <h3>Saúde do Sistema</h3>
          <div className="health-metrics">
            <div className="health-item">
              <span>Taxa de falha operacional</span>
              <span
                className={`health-value ${
                  (stats?.system_health?.command_error_rate || 0) > 0.1 ? 'danger' : 'success'
                }`}
              >
                {((stats?.system_health?.command_error_rate || 0) * 100).toFixed(1)}%
              </span>
            </div>
            <div className="health-item">
              <span>Taxa de erro API</span>
              <span
                className={`health-value ${
                  (stats?.system_health?.api_error_rate || 0) > 0.1 ? 'danger' : 'success'
                }`}
              >
                {((stats?.system_health?.api_error_rate || 0) * 100).toFixed(1)}%
              </span>
            </div>
            <div className="health-item">
              <span>Alertas ativos</span>
              <span
                className={`health-value ${
                  (stats?.system_health?.active_alerts || 0) > 0 ? 'warning' : 'success'
                }`}
              >
                {stats?.system_health?.active_alerts || 0}
              </span>
            </div>
            <div className="health-item">
              <span>Bloqueios de política</span>
              <span className="health-value warning">
                {stats?.system_health?.policy_blocks || 0}
              </span>
            </div>
          </div>
        </div>

        <div className="dashboard-card">
          <h3>Uso de LLM</h3>
          <div className="health-metrics">
            <div className="health-item">
              <span>Total de tokens</span>
              <span className="health-value success">
                {(stats?.llm_usage?.totals?.total_tokens || 0).toLocaleString()}
              </span>
            </div>
            <div className="health-item">
              <span>Prompt / Resposta</span>
              <span className="health-value">
                {(stats?.llm_usage?.totals?.prompt_tokens || 0).toLocaleString()} /{' '}
                {(stats?.llm_usage?.totals?.completion_tokens || 0).toLocaleString()}
              </span>
            </div>
            <div className="health-item">
              <span>Taxa de cache hit</span>
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
              <span>Cache hit / miss</span>
              <span className="health-value">
                {(stats?.llm_usage?.totals?.prompt_cache_hit_tokens || 0).toLocaleString()} /{' '}
                {(stats?.llm_usage?.totals?.prompt_cache_miss_tokens || 0).toLocaleString()}
              </span>
            </div>
            <div className="health-item">
              <span>Requisições</span>
              <span className="health-value">
                {stats?.llm_usage?.totals?.request_count || 0}
              </span>
            </div>
            <div className="health-item">
              <span>Padrões aprendidos</span>
              <span className="health-value">
                {agentLearning?.learned_patterns || 0}
              </span>
            </div>
            <div className="health-item">
              <span>Sinais de aprendizado</span>
              <span className="health-value">
                {(agentLearning?.success_signals || 0).toLocaleString()} /{' '}
                {(agentLearning?.failure_signals || 0).toLocaleString()}
              </span>
            </div>
            <div className="health-item">
              <span>Eventos de nudge</span>
              <span className="health-value">
                {knowledge?.nudges.total_events || 0}
              </span>
            </div>
            <div className="health-item">
              <span>Confiança da memória</span>
              <span className="health-value">
                {((knowledge?.memories.avg_confidence || 0) * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        </div>

        <div className="dashboard-card">
          <h3>Status do Orçamento</h3>
          <div className="health-metrics">
            <div className="health-item">
              <span>Diário</span>
              <span className={`health-value budget-${budget?.daily?.level || 'disabled'}`}>
                {budget?.daily?.budget_usd
                  ? `${formatUsd(budget?.daily?.actual_cost_usd || 0)} / ${formatUsd(
                      budget?.daily?.budget_usd || 0
                    )}`
                  : 'Desativado'}
              </span>
            </div>
            <div className="health-item">
              <span>Uso diário</span>
              <span className={`health-value budget-${budget?.daily?.level || 'disabled'}`}>
                {budget?.daily?.budget_usd ? `${(budget?.daily?.usage_pct || 0).toFixed(1)}%` : 'n/a'}
              </span>
            </div>
            <div className="health-item">
              <span>Mensal</span>
              <span className={`health-value budget-${budget?.monthly?.level || 'disabled'}`}>
                {budget?.monthly?.budget_usd
                  ? `${formatUsd(budget?.monthly?.actual_cost_usd || 0)} / ${formatUsd(
                      budget?.monthly?.budget_usd || 0
                    )}`
                  : 'Desativado'}
              </span>
            </div>
            <div className="health-item">
              <span>Uso mensal</span>
              <span className={`health-value budget-${budget?.monthly?.level || 'disabled'}`}>
                {budget?.monthly?.budget_usd
                  ? `${(budget?.monthly?.usage_pct || 0).toFixed(1)}%`
                  : 'n/a'}
              </span>
            </div>
          </div>
        </div>

        <div className="dashboard-card full-width">
          <h3>Custo Diário de LLM</h3>
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
          <h3>Custo por Projeto</h3>
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
          <h3>Limites de Orçamento</h3>
          <div className="health-metrics">
            <div className="health-item">
              <span>Limite de aviso</span>
              <span className="health-value">
                {budget?.daily?.warning_threshold_pct ?? 0}% / {budget?.monthly?.warning_threshold_pct ?? 0}%
              </span>
            </div>
            <div className="health-item">
              <span>Limite crítico</span>
              <span className="health-value">
                {budget?.daily?.critical_threshold_pct ?? 0}% / {budget?.monthly?.critical_threshold_pct ?? 0}%
              </span>
            </div>
            <div className="health-item">
              <span>Disparo diário</span>
              <span className="health-value">
                {budget?.daily?.budget_usd
                  ? `${formatUsd(budget?.daily?.warning_threshold_cost_usd || 0)} -> ${formatUsd(
                      budget?.daily?.critical_threshold_cost_usd || 0
                    )}`
                  : 'Desativado'}
              </span>
            </div>
            <div className="health-item">
              <span>Disparo mensal</span>
              <span className="health-value">
                {budget?.monthly?.budget_usd
                  ? `${formatUsd(budget?.monthly?.warning_threshold_cost_usd || 0)} -> ${formatUsd(
                      budget?.monthly?.critical_threshold_cost_usd || 0
                    )}`
                  : 'Desativado'}
              </span>
            </div>
          </div>
        </div>

        <div className="dashboard-card full-width">
          <h3>Alertas Recentes</h3>
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
              <p>Nenhum alerta ativo</p>
            </div>
          )}
        </div>

        <div className="dashboard-card full-width">
          <h3>Telemetria por Usuário e Modelo</h3>
          <div className="chart-container">
            {telemetry.length ? (
              telemetry.slice(0, 8).map((item) => (
                <div
                  key={`${item.user_id || 'anon'}:${item.provider || 'n/a'}:${item.model || 'n/a'}`}
                  className="chart-bar"
                >
                  <div className="chart-bar-label">
                    {(item.user_id || 'sem usuário')} · {item.provider}/{item.model}
                  </div>
                  <div className="chart-bar-value">
                    {item.request_count} req · erro {(item.error_rate * 100).toFixed(1)}% · TTFT{' '}
                    {Math.round(item.avg_first_token_latency_ms || 0)}ms · total{' '}
                    {Math.round(item.avg_total_latency_ms || 0)}ms · {formatUsd(item.estimated_cost_usd)}
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-section">
                <p>Sem telemetria de modelo suficiente para o período.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
