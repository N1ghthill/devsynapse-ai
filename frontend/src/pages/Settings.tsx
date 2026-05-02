import { useState, useEffect } from 'react';
import { Download, Save, Cpu, RefreshCw } from 'lucide-react';
import {
  desktopUpdaterApi,
  isDesktopRuntime,
  settingsApi,
  type DesktopUpdateStatus,
} from '../api/client';
import type { SettingsData } from '../types';
import { useAuth } from '../hooks/useAuth';

export function Settings() {
  const { auth } = useAuth();
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);
  const [updateStatus, setUpdateStatus] = useState<DesktopUpdateStatus | null>(null);
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [installingUpdate, setInstallingUpdate] = useState(false);
  const canEditSettings = auth.user?.role === 'admin';

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await settingsApi.get();
        setSettings(data);
      } catch {
        setMessage({ type: 'error', text: 'Falha ao carregar ajustes' });
      }
      setLoading(false);
    };
    fetchSettings();
  }, []);

  const handleSave = async () => {
    if (!settings || !canEditSettings) return;
    setSaving(true);
    setMessage(null);

    try {
      await settingsApi.update(settings);
      setMessage({ type: 'success', text: 'Ajustes salvos com sucesso' });
    } catch {
      setMessage({ type: 'error', text: 'Falha ao salvar ajustes' });
    }

    setSaving(false);
  };

  const checkForUpdate = async () => {
    setCheckingUpdate(true);
    try {
      const status = await desktopUpdaterApi.check();
      setUpdateStatus(status);
    } catch {
      setMessage({ type: 'error', text: 'Falha ao verificar atualizações do desktop' });
    }
    setCheckingUpdate(false);
  };

  const installUpdate = async () => {
    setInstallingUpdate(true);
    try {
      await desktopUpdaterApi.install();
    } catch {
      setMessage({ type: 'error', text: 'Falha ao instalar atualização do desktop' });
      setInstallingUpdate(false);
    }
  };

  if (loading) {
    return (
      <div className="page-loading">
        <Cpu size={48} className="spinner" />
        <p>Carregando ajustes...</p>
      </div>
    );
  }

  return (
    <div className="settings-page">
      <div className="page-header">
        <h1>Ajustes</h1>
        {canEditSettings && (
          <button className="save-btn" onClick={handleSave} disabled={saving}>
            {saving ? (
              <RefreshCw size={16} className="spinner" />
            ) : (
              <Save size={16} />
            )}
            {saving ? 'Salvando...' : 'Salvar alterações'}
          </button>
        )}
      </div>

      {message && (
        <div className={`message-bar message-${message.type}`}>
          {message.text}
        </div>
      )}

      <div className="settings-grid">
        <div className="settings-card">
          <h3>Chaves de API</h3>
          <div className="setting-field">
            <label>Chave da API DeepSeek</label>
            <div className="key-input-row">
              <input
                type="password"
                placeholder={typeof settings?.deepseek_api_key === 'boolean' && settings.deepseek_api_key ? '•••••••• (configurada)' : 'Informe sua chave da API DeepSeek'}
                value={typeof settings?.deepseek_api_key === 'string' ? settings.deepseek_api_key : ''}
                disabled={!canEditSettings}
                onChange={(e) =>
                  setSettings((prev) =>
                    prev ? { ...prev, deepseek_api_key: e.target.value } : prev
                  )
                }
              />
              {typeof settings?.deepseek_api_key === 'boolean' && settings.deepseek_api_key && (
                <span className="key-status configured">Configurada</span>
              )}
            </div>
          </div>
        </div>

        <div className="settings-card">
          <h3>Configuração de Modelo</h3>
          <div className="setting-field">
            <label>Modelo DeepSeek</label>
            <input
              type="text"
              value={settings?.deepseek_model || ''}
              disabled={!canEditSettings}
              onChange={(e) =>
                setSettings((prev) =>
                  prev ? { ...prev, deepseek_model: e.target.value } : prev
                )
              }
            />
          </div>
          <div className="setting-field">
            <label>Modelo Flash</label>
            <input
              type="text"
              value={settings?.deepseek_flash_model || ''}
              disabled={!canEditSettings}
              onChange={(e) =>
                setSettings((prev) =>
                  prev ? { ...prev, deepseek_flash_model: e.target.value } : prev
                )
              }
            />
          </div>
          <div className="setting-field">
            <label>Modelo Pro</label>
            <input
              type="text"
              value={settings?.deepseek_pro_model || ''}
              disabled={!canEditSettings}
              onChange={(e) =>
                setSettings((prev) =>
                  prev ? { ...prev, deepseek_pro_model: e.target.value } : prev
                )
              }
            />
          </div>
          <div className="setting-field checkbox-field">
            <label>
              <input
                type="checkbox"
                checked={settings?.llm_model_routing_enabled ?? true}
                disabled={!canEditSettings}
                onChange={(e) =>
                  setSettings((prev) =>
                    prev ? { ...prev, llm_model_routing_enabled: e.target.checked } : prev
                  )
                }
              />
              Roteamento Flash/Pro
            </label>
          </div>
          <div className="setting-field checkbox-field">
            <label>
              <input
                type="checkbox"
                checked={settings?.llm_auto_economy_enabled ?? true}
                disabled={!canEditSettings}
                onChange={(e) =>
                  setSettings((prev) =>
                    prev ? { ...prev, llm_auto_economy_enabled: e.target.checked } : prev
                  )
                }
              />
              Modo econômico automático
            </label>
          </div>
          <div className="setting-field">
            <label>Aviso de cache hit (%)</label>
            <input
              type="number"
              min="0"
              max="100"
              step="1"
              value={settings?.llm_cache_hit_warning_threshold_pct ?? 70}
              disabled={!canEditSettings}
              onChange={(e) =>
                setSettings((prev) =>
                  prev
                    ? {
                        ...prev,
                        llm_cache_hit_warning_threshold_pct: parseFloat(e.target.value || '0'),
                      }
                    : prev
                )
              }
            />
          </div>
          <div className="setting-field">
            <label>Temperatura</label>
            <div className="range-input">
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={settings?.temperature ?? 0.7}
                disabled={!canEditSettings}
                onChange={(e) =>
                  setSettings((prev) =>
                    prev
                      ? { ...prev, temperature: parseFloat(e.target.value) }
                      : prev
                  )
                }
              />
              <span className="range-value">
                {settings?.temperature ?? 0.7}
              </span>
            </div>
          </div>
          <div className="setting-field">
            <label>Máximo de tokens</label>
            <input
              type="number"
              value={settings?.max_tokens || 1500}
              disabled={!canEditSettings}
              onChange={(e) =>
                setSettings((prev) =>
                  prev
                    ? { ...prev, max_tokens: parseInt(e.target.value) }
                    : prev
                )
              }
            />
          </div>
        </div>

        <div className="settings-card">
          <h3>Conversa</h3>
          <div className="setting-field">
            <label>Limite de histórico</label>
            <input
              type="number"
              value={settings?.conversation_history_limit || 20}
              disabled={!canEditSettings}
              onChange={(e) =>
                setSettings((prev) =>
                  prev
                    ? {
                        ...prev,
                        conversation_history_limit: parseInt(e.target.value),
                      }
                    : prev
                )
              }
            />
          </div>
        </div>

        <div className="settings-card">
          <h3>Orçamento de LLM</h3>
          <div className="setting-field">
            <label>Orçamento diário (USD)</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={settings?.llm_daily_budget_usd ?? 0}
              disabled={!canEditSettings}
              onChange={(e) =>
                setSettings((prev) =>
                  prev
                    ? {
                        ...prev,
                        llm_daily_budget_usd: parseFloat(e.target.value || '0'),
                      }
                    : prev
                )
              }
            />
            <small>Use `0` para desativar o alerta de orçamento diário.</small>
          </div>
          <div className="setting-field">
            <label>Orçamento mensal (USD)</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={settings?.llm_monthly_budget_usd ?? 0}
              disabled={!canEditSettings}
              onChange={(e) =>
                setSettings((prev) =>
                  prev
                    ? {
                        ...prev,
                        llm_monthly_budget_usd: parseFloat(e.target.value || '0'),
                      }
                    : prev
                )
              }
            />
            <small>Usa o mês calendário atual, não uma janela móvel de 30 dias.</small>
          </div>
          <div className="setting-field">
            <label>Limite de aviso (%)</label>
            <input
              type="number"
              min="0"
              max="100"
              step="1"
              value={settings?.llm_budget_warning_threshold_pct ?? 80}
              disabled={!canEditSettings}
              onChange={(e) =>
                setSettings((prev) =>
                  prev
                    ? {
                        ...prev,
                        llm_budget_warning_threshold_pct: parseFloat(e.target.value || '0'),
                      }
                    : prev
                )
              }
            />
          </div>
          <div className="setting-field">
            <label>Limite crítico (%)</label>
            <input
              type="number"
              min="0"
              max="200"
              step="1"
              value={settings?.llm_budget_critical_threshold_pct ?? 100}
              disabled={!canEditSettings}
              onChange={(e) =>
                setSettings((prev) =>
                  prev
                    ? {
                        ...prev,
                        llm_budget_critical_threshold_pct: parseFloat(e.target.value || '0'),
                      }
                    : prev
                )
              }
            />
            <small>O crítico pode ficar acima de `100` para permitir estouro controlado.</small>
          </div>
        </div>

        <div className="settings-card">
          <h3>Acesso a Projetos</h3>
          <div className="setting-field">
            <label>Meu escopo de mutação</label>
            <textarea
              rows={5}
              value={(settings?.project_mutation_allowlist || []).join('\n')}
              readOnly
            />
            <small>
              {auth.user?.role === 'admin'
                ? 'Administradores podem alterar todos os projetos registrados.'
                : 'Suas permissões de mutação são gerenciadas por um administrador.'}
            </small>
          </div>
        </div>

        <div className="settings-card">
          <h3>Servidor API</h3>
          <div className="setting-field">
            <label>Host</label>
            <input
              type="text"
              value={settings?.api_host || '127.0.0.1'}
              readOnly
            />
          </div>
          <div className="setting-field">
            <label>Port</label>
            <input
              type="number"
              value={settings?.api_port || 8000}
              readOnly
            />
          </div>
        </div>

        <div className="settings-card">
          <h3>Atualizações do Aplicativo</h3>
          <div className="setting-field">
            <label>Versão instalada</label>
              <input
                type="text"
                value={updateStatus?.currentVersion || __APP_VERSION__}
                readOnly
              />
          </div>
          {isDesktopRuntime() ? (
            <>
              {updateStatus && !updateStatus.configured && (
                <div className="message-bar message-error">
                  O atualizador desktop não está configurado nesta build.
                </div>
              )}
              {updateStatus?.configured && updateStatus.available && (
                <div className="message-bar message-success">
                  Versão {updateStatus.version} disponível.
                </div>
              )}
              {updateStatus?.configured && !updateStatus.available && (
                <div className="message-bar message-success">
                  O aplicativo desktop está atualizado.
                </div>
              )}
              {updateStatus?.body && (
                <div className="setting-field">
                  <label>Notas da versão</label>
                  <textarea rows={5} value={updateStatus.body} readOnly />
                </div>
              )}
              <div className="settings-actions-row">
                <button
                  className="save-btn"
                  onClick={() => void checkForUpdate()}
                  disabled={checkingUpdate || installingUpdate}
                  type="button"
                >
                  <RefreshCw size={16} className={checkingUpdate ? 'spinner' : ''} />
                  {checkingUpdate ? 'Verificando...' : 'Verificar atualizações'}
                </button>
                <button
                  className="save-btn"
                  onClick={() => void installUpdate()}
                  disabled={
                    installingUpdate ||
                    checkingUpdate ||
                    !updateStatus?.configured ||
                    !updateStatus.available
                  }
                  type="button"
                >
                  <Download size={16} className={installingUpdate ? 'spinner' : ''} />
                  {installingUpdate ? 'Instalando...' : 'Instalar atualização'}
                </button>
              </div>
            </>
          ) : (
            <small>Atualizações desktop estão disponíveis no aplicativo Tauri empacotado.</small>
          )}
        </div>
      </div>
    </div>
  );
}
