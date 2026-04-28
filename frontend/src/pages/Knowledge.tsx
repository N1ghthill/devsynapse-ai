import { useEffect, useState } from 'react';
import { Brain, Check, Library, Plus, RefreshCw, ThumbsDown, ThumbsUp } from 'lucide-react';
import { knowledgeApi, settingsApi } from '../api/client';
import type { ProjectInfo, ProjectMemory, SkillSummary } from '../types';
import { useAuth } from '../hooks/useAuth';

const confidencePct = (value: number) => `${Math.round(value * 100)}%`;

export function Knowledge() {
  const { auth } = useAuth();
  const [memories, setMemories] = useState<ProjectMemory[]>([]);
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [savingMemory, setSavingMemory] = useState(false);
  const [savingSkill, setSavingSkill] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [memoryForm, setMemoryForm] = useState({
    content: '',
    memory_type: 'fact',
    confidence_score: 0.6,
  });
  const [skillForm, setSkillForm] = useState({
    name: '',
    description: '',
    category: 'general',
    body: '',
  });
  const canCreateSkills = auth.user?.role === 'admin';

  const load = async () => {
    try {
      const [memoryList, skillList, projectList] = await Promise.all([
        knowledgeApi.listMemories(selectedProject || undefined, query || undefined),
        knowledgeApi.listSkills(selectedProject || undefined),
        settingsApi.listProjects(),
      ]);
      setMemories(memoryList);
      setSkills(skillList);
      setProjects(projectList);
      setMessage(null);
    } catch {
      setMessage('Failed to load knowledge data');
    }
    setLoading(false);
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProject]);

  const createMemory = async () => {
    if (!memoryForm.content.trim()) return;
    setSavingMemory(true);
    try {
      await knowledgeApi.createMemory({
        content: memoryForm.content.trim(),
        memory_type: memoryForm.memory_type,
        confidence_score: memoryForm.confidence_score,
        project_name: selectedProject || null,
      });
      setMemoryForm({ content: '', memory_type: 'fact', confidence_score: 0.6 });
      await load();
    } catch {
      setMessage('Failed to save memory');
    }
    setSavingMemory(false);
  };

  const createSkill = async () => {
    if (!canCreateSkills || !skillForm.name.trim() || !skillForm.body.trim()) return;
    setSavingSkill(true);
    try {
      await knowledgeApi.createSkill({
        name: skillForm.name.trim(),
        description: skillForm.description.trim(),
        category: skillForm.category.trim() || 'general',
        body: skillForm.body.trim(),
        project_name: selectedProject || null,
      });
      setSkillForm({ name: '', description: '', category: 'general', body: '' });
      await load();
    } catch {
      setMessage('Failed to save skill');
    }
    setSavingSkill(false);
  };

  const adjustMemory = async (memoryId: number, delta: number) => {
    await knowledgeApi.adjustMemoryConfidence(memoryId, delta);
    await load();
  };

  const activateSkill = async (skill: SkillSummary) => {
    await knowledgeApi.activateSkill(skill.slug, selectedProject || skill.project_name || null);
    await load();
  };

  return (
    <div className="knowledge-page">
      <div className="page-header">
        <div>
          <h1>Knowledge</h1>
          <div className="dashboard-filters">
            <select
              value={selectedProject}
              onChange={(event) => setSelectedProject(event.target.value)}
              className="knowledge-select"
              aria-label="Project scope"
            >
              <option value="">Global</option>
              {projects.map((project) => (
                <option key={project.name} value={project.name}>
                  {project.name}
                </option>
              ))}
            </select>
            <input
              className="knowledge-search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void load();
              }}
              placeholder="Search memories"
            />
            <button className="dashboard-filter-btn" type="button" onClick={() => void load()}>
              <RefreshCw size={14} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {message && <div className="message-bar message-error">{message}</div>}

      <div className="knowledge-grid">
        <section className="settings-card">
          <div className="admin-card-header">
            <div>
              <h3>Memories</h3>
              <p className="admin-subtitle">{memories.length} loaded</p>
            </div>
            <Brain size={18} />
          </div>
          <div className="setting-field">
            <label>Content</label>
            <textarea
              rows={4}
              value={memoryForm.content}
              onChange={(event) =>
                setMemoryForm((prev) => ({ ...prev, content: event.target.value }))
              }
            />
          </div>
          <div className="knowledge-form-row">
            <div className="setting-field">
              <label>Type</label>
              <select
                value={memoryForm.memory_type}
                onChange={(event) =>
                  setMemoryForm((prev) => ({ ...prev, memory_type: event.target.value }))
                }
              >
                <option value="fact">fact</option>
                <option value="procedure">procedure</option>
                <option value="insight">insight</option>
                <option value="preference">preference</option>
              </select>
            </div>
            <div className="setting-field">
              <label>Confidence</label>
              <input
                type="number"
                min="0"
                max="1"
                step="0.05"
                value={memoryForm.confidence_score}
                onChange={(event) =>
                  setMemoryForm((prev) => ({
                    ...prev,
                    confidence_score: parseFloat(event.target.value || '0'),
                  }))
                }
              />
            </div>
          </div>
          <button
            className="save-btn"
            type="button"
            onClick={() => void createMemory()}
            disabled={savingMemory || !memoryForm.content.trim()}
          >
            {savingMemory ? <RefreshCw size={16} className="spinner" /> : <Plus size={16} />}
            Save Memory
          </button>
          <div className="knowledge-list">
            {loading ? (
              <p className="admin-subtitle">Loading...</p>
            ) : (
              memories.map((memory) => (
                <article className="knowledge-item" key={memory.id}>
                  <div className="knowledge-item-header">
                    <strong>{memory.memory_type}</strong>
                    <span>{confidencePct(memory.effective_confidence)}</span>
                  </div>
                  <p>{memory.content}</p>
                  <div className="knowledge-item-footer">
                    <span>{memory.project_name || 'global'}</span>
                    <div className="knowledge-actions">
                      <button
                        type="button"
                        className="conversation-action-btn"
                        onClick={() => void adjustMemory(memory.id, 0.05)}
                        aria-label="Reinforce memory"
                      >
                        <ThumbsUp size={14} />
                      </button>
                      <button
                        type="button"
                        className="conversation-action-btn danger"
                        onClick={() => void adjustMemory(memory.id, -0.08)}
                        aria-label="Penalize memory"
                      >
                        <ThumbsDown size={14} />
                      </button>
                    </div>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>

        <section className="settings-card">
          <div className="admin-card-header">
            <div>
              <h3>Skills</h3>
              <p className="admin-subtitle">{skills.length} registered</p>
            </div>
            <Library size={18} />
          </div>
          <fieldset className="knowledge-fieldset" disabled={!canCreateSkills}>
            <div className="knowledge-form-row">
              <div className="setting-field">
                <label>Name</label>
                <input
                  type="text"
                  value={skillForm.name}
                  onChange={(event) =>
                    setSkillForm((prev) => ({ ...prev, name: event.target.value }))
                  }
                />
              </div>
              <div className="setting-field">
                <label>Category</label>
                <input
                  type="text"
                  value={skillForm.category}
                  onChange={(event) =>
                    setSkillForm((prev) => ({ ...prev, category: event.target.value }))
                  }
                />
              </div>
            </div>
            <div className="setting-field">
              <label>Description</label>
              <input
                type="text"
                value={skillForm.description}
                onChange={(event) =>
                  setSkillForm((prev) => ({ ...prev, description: event.target.value }))
                }
              />
            </div>
            <div className="setting-field">
              <label>Body</label>
              <textarea
                rows={6}
                value={skillForm.body}
                onChange={(event) =>
                  setSkillForm((prev) => ({ ...prev, body: event.target.value }))
                }
              />
            </div>
          </fieldset>
          <button
            className="save-btn"
            type="button"
            onClick={() => void createSkill()}
            disabled={savingSkill || !canCreateSkills || !skillForm.name.trim()}
          >
            {savingSkill ? <RefreshCw size={16} className="spinner" /> : <Plus size={16} />}
            Save Skill
          </button>
          {!canCreateSkills && (
            <p className="admin-subtitle knowledge-note">Skill writes require admin access.</p>
          )}
          <div className="knowledge-list">
            {skills.map((skill) => (
              <article className="knowledge-item" key={`${skill.scope}-${skill.slug}`}>
                <div className="knowledge-item-header">
                  <strong>{skill.name}</strong>
                  <span>{skill.use_count} uses</span>
                </div>
                <p>{skill.description}</p>
                <div className="knowledge-item-footer">
                  <span>
                    {skill.project_name || 'global'} / {skill.category}
                  </span>
                  <button
                    type="button"
                    className="conversation-action-btn"
                    onClick={() => void activateSkill(skill)}
                    aria-label="Activate skill"
                  >
                    <Check size={14} />
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
