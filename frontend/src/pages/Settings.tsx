import { useState, useEffect } from 'react';
import { Save, Cpu, RefreshCw } from 'lucide-react';
import { settingsApi } from '../api/client';
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

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await settingsApi.get();
        setSettings(data);
      } catch (err) {
        setMessage({ type: 'error', text: 'Failed to load settings' });
      }
      setLoading(false);
    };
    fetchSettings();
  }, []);

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setMessage(null);

    try {
      await settingsApi.update(settings);
      setMessage({ type: 'success', text: 'Settings saved successfully' });
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to save settings' });
    }

    setSaving(false);
  };

  if (loading) {
    return (
      <div className="page-loading">
        <Cpu size={48} className="spinner" />
        <p>Loading settings...</p>
      </div>
    );
  }

  return (
    <div className="settings-page">
      <div className="page-header">
        <h1>Settings</h1>
        <button className="save-btn" onClick={handleSave} disabled={saving}>
          {saving ? (
            <RefreshCw size={16} className="spinner" />
          ) : (
            <Save size={16} />
          )}
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      {message && (
        <div className={`message-bar message-${message.type}`}>
          {message.text}
        </div>
      )}

      <div className="settings-grid">
        <div className="settings-card">
          <h3>API Keys</h3>
          <div className="setting-field">
            <label>Deepseek API Key</label>
            <div className="key-input-row">
              <input
                type="password"
                placeholder={typeof settings?.deepseek_api_key === 'boolean' && settings.deepseek_api_key ? '•••••••• (configured)' : 'Enter your Deepseek API key'}
                value={typeof settings?.deepseek_api_key === 'string' ? settings.deepseek_api_key : ''}
                onChange={(e) =>
                  setSettings((prev) =>
                    prev ? { ...prev, deepseek_api_key: e.target.value } : prev
                  )
                }
              />
              {typeof settings?.deepseek_api_key === 'boolean' && settings.deepseek_api_key && (
                <span className="key-status configured">Configured</span>
              )}
            </div>
          </div>
        </div>

        <div className="settings-card">
          <h3>Model Configuration</h3>
          <div className="setting-field">
            <label>Deepseek Model</label>
            <input
              type="text"
              value={settings?.deepseek_model || ''}
              onChange={(e) =>
                setSettings((prev) =>
                  prev ? { ...prev, deepseek_model: e.target.value } : prev
                )
              }
            />
          </div>
          <div className="setting-field">
            <label>OpenAI Model (Fallback)</label>
            <input
              type="text"
              value={settings?.openai_model || ''}
              onChange={(e) =>
                setSettings((prev) =>
                  prev ? { ...prev, openai_model: e.target.value } : prev
                )
              }
            />
          </div>
          <div className="setting-field">
            <label>Temperature</label>
            <div className="range-input">
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={settings?.temperature ?? 0.7}
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
            <label>Max Tokens</label>
            <input
              type="number"
              value={settings?.max_tokens || 1500}
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
          <h3>Conversation</h3>
          <div className="setting-field">
            <label>History Limit</label>
            <input
              type="number"
              value={settings?.conversation_history_limit || 20}
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
          <h3>LLM Budget</h3>
          <div className="setting-field">
            <label>Daily Budget (USD)</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={settings?.llm_daily_budget_usd ?? 0}
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
            <small>Use `0` to disable the daily budget alert.</small>
          </div>
          <div className="setting-field">
            <label>Monthly Budget (USD)</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={settings?.llm_monthly_budget_usd ?? 0}
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
            <small>Uses the current calendar month, not a rolling 30-day window.</small>
          </div>
          <div className="setting-field">
            <label>Warning Threshold (%)</label>
            <input
              type="number"
              min="0"
              max="100"
              step="1"
              value={settings?.llm_budget_warning_threshold_pct ?? 80}
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
            <label>Critical Threshold (%)</label>
            <input
              type="number"
              min="0"
              max="200"
              step="1"
              value={settings?.llm_budget_critical_threshold_pct ?? 100}
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
            <small>Critical can be above `100` if you want a soft overrun policy.</small>
          </div>
        </div>

        <div className="settings-card">
          <h3>Project Access</h3>
          <div className="setting-field">
            <label>My Mutation Scope</label>
            <textarea
              rows={5}
              value={(settings?.project_mutation_allowlist || []).join('\n')}
              readOnly
            />
            <small>
              {auth.user?.role === 'admin'
                ? 'Admin permissions are managed from the Admin area.'
                : 'Your project mutation permissions are managed by an admin.'}
            </small>
          </div>
        </div>

        <div className="settings-card">
          <h3>API Server</h3>
          <div className="setting-field">
            <label>Host</label>
            <input
              type="text"
              value={settings?.api_host || '127.0.0.1'}
              onChange={(e) =>
                setSettings((prev) =>
                  prev ? { ...prev, api_host: e.target.value } : prev
                )
              }
            />
          </div>
          <div className="setting-field">
            <label>Port</label>
            <input
              type="number"
              value={settings?.api_port || 8000}
              onChange={(e) =>
                setSettings((prev) =>
                  prev
                    ? { ...prev, api_port: parseInt(e.target.value) }
                    : prev
                )
              }
            />
          </div>
        </div>
      </div>
    </div>
  );
}
