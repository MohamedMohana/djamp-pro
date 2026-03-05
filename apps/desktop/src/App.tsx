import { useState, useEffect } from 'react';
import { Play, Square, Settings, Plus, RefreshCw, Database, Globe } from 'lucide-react';
import { api } from './services/api';
import { Project } from './types';
import { cn, getStatusColor, getStatusIcon } from './utils';

import ProjectList from './components/ProjectList';
import ProjectCard from './components/ProjectCard';
import ProjectAvatar from './components/ProjectAvatar';
import AddProjectModal from './components/AddProjectModal';
import SettingsPanel from './components/SettingsPanel';
import djampMark from './assets/djamp-mark.png';

function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'projects' | 'logs' | 'environment'>('projects');
  const [logsSource, setLogsSource] = useState<'django' | 'proxy' | 'database'>('django');
  const [logsText, setLogsText] = useState<string>('');
  const [logsLoading, setLogsLoading] = useState(false);
  const [actionProjectId, setActionProjectId] = useState<string | null>(null);
  const [actionKind, setActionKind] = useState<'start' | 'stop' | 'restart' | null>(null);
  const [deleteModalProject, setDeleteModalProject] = useState<Project | null>(null);
  const [deleteConfirmName, setDeleteConfirmName] = useState('');
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);

  const extractErrorMessage = (error: unknown, fallback: string): string => {
    if (error instanceof Error && error.message.trim()) {
      return error.message;
    }

    const raw = String(error ?? '').trim();
    if (!raw) {
      return fallback;
    }

    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed === 'string' && parsed.trim()) {
        return parsed;
      }
      if (parsed && typeof parsed === 'object') {
        const detail = (parsed as { detail?: unknown }).detail;
        if (typeof detail === 'string' && detail.trim()) {
          return detail;
        }
      }
    } catch {
      // Keep raw string fallback below.
    }

    return raw;
  };

  useEffect(() => {
    loadProjects();
    const interval = setInterval(loadProjects, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const selectedProjectId = selectedProject?.id;

    const loadLogs = async () => {
      if (!selectedProjectId || activeTab !== 'logs') return;
      setLogsLoading(true);
      try {
        const text = await api.getLogs(selectedProjectId, logsSource);
        setLogsText(text);
      } catch (error) {
        console.error('Failed to load logs:', error);
        setLogsText('');
      }
      setLogsLoading(false);
    };

    loadLogs();
    const interval = setInterval(loadLogs, 2000);
    return () => clearInterval(interval);
  }, [selectedProject?.id, activeTab, logsSource]);

  const loadProjects = async () => {
    try {
      const loaded = await api.getProjects();
      setProjects(loaded);
      setSelectedProject((prev) => {
        if (!prev) {
          return loaded.length === 1 ? loaded[0] : null;
        }
        const fresh = loaded.find((p) => p.id === prev.id);
        return fresh || null;
      });
      setLoading(false);
    } catch (error) {
      console.error('Failed to load projects:', error);
      setLoading(false);
    }
  };

  const setProjectStatusLocal = (id: string, status: Project['status']) => {
    setProjects((prev) => prev.map((project) => (project.id === id ? { ...project, status } : project)));
    setSelectedProject((prev) => (prev && prev.id === id ? { ...prev, status } : prev));
  };

  const handleStartProject = async (id: string) => {
    setActionProjectId(id);
    setActionKind('start');
    setProjectStatusLocal(id, 'starting');
    try {
      const result = await api.startProject(id);
      if (result?.message && result.message !== 'Project started') {
        alert(result.message);
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const certWarning = (result as any)?.certificateWarning as string | undefined;
      if (certWarning) {
        alert(`HTTPS warning: ${certWarning}`);
      }
      if (result?.hosts && !result.hosts.success) {
        alert(`Domain mapping warning: ${result.hosts.error || 'Unable to update hosts file'}`);
      }
      if (result?.proxy && !result.proxy.success) {
        alert(`Proxy warning: ${result.proxy.error || 'Unable to start/reload Caddy'}`);
      }
      if (result?.proxy?.success && result.proxy.output?.includes('Use https://')) {
        alert(`Proxy info: ${result.proxy.output}`);
      }
      await loadProjects();
    } catch (error) {
      console.error('Failed to start project:', error);
      alert(`Failed to start project: ${extractErrorMessage(error, 'Unknown error')}`);
      setProjectStatusLocal(id, 'error');
    } finally {
      setActionProjectId(null);
      setActionKind(null);
    }
  };

  const handleStopProject = async (id: string) => {
    setActionProjectId(id);
    setActionKind('stop');
    setProjectStatusLocal(id, 'stopping');
    try {
      await api.stopProject(id);
      await loadProjects();
    } catch (error) {
      console.error('Failed to stop project:', error);
      alert(`Failed to stop project: ${extractErrorMessage(error, 'Unknown error')}`);
      setProjectStatusLocal(id, 'running');
    } finally {
      setActionProjectId(null);
      setActionKind(null);
    }
  };

  const handleRestartProject = async (id: string) => {
    setActionProjectId(id);
    setActionKind('restart');
    setProjectStatusLocal(id, 'starting');
    try {
      await api.restartProject(id);
      await loadProjects();
    } catch (error) {
      console.error('Failed to restart project:', error);
      alert(`Failed to restart project: ${extractErrorMessage(error, 'Unknown error')}`);
      setProjectStatusLocal(id, 'error');
    } finally {
      setActionProjectId(null);
      setActionKind(null);
    }
  };

  const handleDeleteProject = (project: Project) => {
    setDeleteModalProject(project);
    setDeleteConfirmName('');
  };

  const closeDeleteModal = () => {
    if (deleteSubmitting) return;
    setDeleteModalProject(null);
    setDeleteConfirmName('');
  };

  const handleConfirmDeleteProject = async () => {
    if (!deleteModalProject) return;

    const expectedName = deleteModalProject.name.trim();
    if (deleteConfirmName.trim() !== expectedName) {
      alert(`Type "${expectedName}" exactly to confirm deletion.`);
      return;
    }

    setDeleteSubmitting(true);
    try {
      const id = deleteModalProject.id;
      await api.deleteProject(id);
      await loadProjects();
      if (selectedProject?.id === id) {
        setSelectedProject(null);
      }
      setDeleteModalProject(null);
      setDeleteConfirmName('');
    } catch (error) {
      console.error('Failed to delete project:', error);
      alert(`Failed to delete project: ${extractErrorMessage(error, 'Unknown error')}`);
    } finally {
      setDeleteSubmitting(false);
    }
  };

  const isSelectedBusy = Boolean(selectedProject && actionProjectId === selectedProject.id);

  return (
    <div className="app-bg min-h-screen text-slate-100">
      <div className="flex h-screen gap-3 p-3">
        <aside className="glass-panel flex w-80 flex-col overflow-hidden rounded-2xl border border-white/10">
          <div className="border-b border-white/10 px-4 py-5">
            <div className="flex items-center gap-3">
              <img
                src={djampMark}
                alt="DJAMP PRO"
                className="h-14 w-14 object-contain"
              />
              <div>
                <h1 className="text-[2rem] font-extrabold leading-none tracking-tight text-brand-300">DJAMP PRO</h1>
                <p className="mt-1 text-sm text-slate-400">Django Local Environment Manager</p>
              </div>
            </div>
          </div>

          <div className="border-b border-white/10 px-4 py-4">
            <button
              onClick={() => setShowAddModal(true)}
              className="w-full rounded-xl bg-gradient-to-r from-brand-500 to-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-[0_8px_25px_rgba(23,116,230,0.35)] transition hover:brightness-110"
            >
              <span className="inline-flex items-center justify-center gap-2">
                <Plus size={17} />
                Add Project
              </span>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            <ProjectList
              projects={projects}
              selectedId={selectedProject?.id}
              onSelect={setSelectedProject}
              loading={loading}
            />
          </div>

          <div className="border-t border-white/10 p-4">
            <button
              onClick={() => setShowSettings(true)}
              className="w-full rounded-xl border border-white/10 bg-slate-800/80 px-4 py-2.5 text-sm font-semibold text-slate-100 transition hover:bg-slate-700/80"
            >
              <span className="inline-flex items-center justify-center gap-2">
                <Settings size={17} />
                Settings
              </span>
            </button>
          </div>
        </aside>

        <main className="glass-panel flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/10">
          {selectedProject ? (
            <>
              <header className="border-b border-white/10 bg-slate-900/55 px-7 py-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <ProjectAvatar name={selectedProject.name} size="md" className="mt-0.5" />
                    <div>
                      <h2 className="text-4xl font-bold leading-tight tracking-tight">{selectedProject.name}</h2>
                      <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-slate-300">
                        <span className={cn('inline-flex items-center gap-1 rounded-full px-3 py-1 ring-1 ring-inset', getStatusColor(selectedProject.status), selectedProject.status === 'running' ? 'bg-emerald-500/10 ring-emerald-500/20' : 'bg-slate-700/35 ring-white/10')}>
                          <span>{getStatusIcon(selectedProject.status)}</span>
                          {selectedProject.status}
                        </span>
                        <span className="inline-flex items-center gap-1 rounded-full bg-slate-700/35 px-3 py-1 ring-1 ring-inset ring-white/10">
                          <Globe size={14} />
                          {selectedProject.httpsEnabled ? 'https://' : 'http://'}{selectedProject.domain}
                        </span>
                        {selectedProject.database.type !== 'none' && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-slate-700/35 px-3 py-1 uppercase ring-1 ring-inset ring-white/10">
                            <Database size={14} />
                            {selectedProject.database.type}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleRestartProject(selectedProject.id)}
                      disabled={isSelectedBusy}
                      className="rounded-xl border border-white/10 bg-slate-700/80 p-2.5 text-slate-100 transition hover:bg-slate-600 disabled:cursor-not-allowed disabled:opacity-50"
                      title="Restart"
                    >
                      <RefreshCw size={18} />
                    </button>
                    {selectedProject.status === 'running' ? (
                      <button
                        onClick={() => handleStopProject(selectedProject.id)}
                        disabled={isSelectedBusy}
                        className="rounded-xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <span className="inline-flex items-center gap-2">
                          <Square size={16} />
                          {isSelectedBusy && actionKind === 'stop' ? 'Stopping...' : 'Stop'}
                        </span>
                      </button>
                    ) : (
                      <button
                        onClick={() => handleStartProject(selectedProject.id)}
                        disabled={isSelectedBusy}
                        className="rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <span className="inline-flex items-center gap-2">
                          <Play size={16} />
                          {isSelectedBusy && actionKind === 'start' ? 'Starting...' : 'Start'}
                        </span>
                      </button>
                    )}
                  </div>
                </div>

                <div className="mt-6 inline-flex rounded-xl border border-white/10 bg-slate-900/80 p-1">
                  {(['projects', 'logs', 'environment'] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={cn(
                        'rounded-lg px-4 py-2 text-sm font-semibold capitalize transition',
                        activeTab === tab
                          ? 'bg-brand-500 text-white shadow-[0_8px_22px_rgba(38,131,255,0.35)]'
                          : 'text-slate-300 hover:bg-slate-700/70 hover:text-white',
                      )}
                    >
                      {tab}
                    </button>
                  ))}
                </div>
              </header>

              <section className="flex-1 overflow-y-auto p-6">
                {activeTab === 'projects' && (
                  <ProjectCard
                    project={selectedProject}
                    onDelete={() => handleDeleteProject(selectedProject)}
                  />
                )}

                {activeTab === 'logs' && (
                  <div className="flex h-full min-h-0 flex-col gap-3 rounded-xl border border-white/10 bg-slate-900/70 p-4">
                    <div className="flex items-center gap-2">
                      {(['django', 'proxy', 'database'] as const).map((source) => (
                        <button
                          key={source}
                          onClick={() => setLogsSource(source)}
                          className={cn(
                            'rounded-lg px-3 py-1.5 text-sm font-semibold capitalize transition',
                            logsSource === source
                              ? 'bg-brand-500 text-white'
                              : 'bg-slate-700/70 text-slate-200 hover:bg-slate-600/80',
                          )}
                        >
                          {source}
                        </button>
                      ))}
                      <div className="flex-1" />
                      <span className="text-xs text-slate-400">{logsLoading ? 'Loading...' : 'Auto-refreshing'}</span>
                    </div>

                    <pre className="flex-1 min-h-0 overflow-auto rounded-lg border border-white/10 bg-slate-950/80 p-3 font-mono text-xs leading-relaxed text-slate-200 whitespace-pre-wrap">
                      {logsText ? logsText : 'No logs yet.'}
                    </pre>
                  </div>
                )}

                {activeTab === 'environment' && (
                  <div className="rounded-xl border border-white/10 bg-slate-900/70 p-6">
                    <h3 className="mb-2 text-xl font-semibold">Environment Variables</h3>
                    <p className="mb-4 text-sm text-slate-400">
                      Loaded from project <code>.env</code> (sensitive values are masked).
                    </p>
                    {Object.entries(selectedProject.environmentVars || {}).length === 0 ? (
                      <div className="rounded-lg border border-white/10 bg-slate-950/60 p-4 text-sm text-slate-400">
                        No environment variables were found in the project <code>.env</code> file.
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {Object.entries(selectedProject.environmentVars).map(([key, value]) => (
                          <div key={key} className="grid grid-cols-[minmax(0,14rem)_minmax(0,1fr)] items-start gap-4">
                            <span className="break-all font-mono text-sm leading-relaxed text-slate-400">{key}</span>
                            <span className="min-w-0 break-all whitespace-pre-wrap rounded-lg bg-slate-700/70 px-3 py-2 font-mono text-sm leading-relaxed text-slate-100">
                              {value}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </section>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center">
              <div className="text-center">
                <Globe size={64} className="mx-auto mb-4 text-slate-500" />
                <h2 className="mb-2 text-2xl font-semibold text-slate-300">No Project Selected</h2>
                <p className="text-slate-400">Select a project from the sidebar or add a new one</p>
              </div>
            </div>
          )}
        </main>
      </div>

      {showAddModal && <AddProjectModal onClose={() => setShowAddModal(false)} onAdd={loadProjects} />}
      {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}

      {deleteModalProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-red-500/40 bg-slate-900 p-5 shadow-[0_25px_60px_rgba(0,0,0,0.45)]">
            <h3 className="text-xl font-semibold text-red-300">Delete Project</h3>
            <p className="mt-3 text-sm text-slate-300">
              This will remove <span className="font-semibold text-white">{deleteModalProject.name}</span> from DJAMP PRO.
            </p>
            <p className="mt-2 text-sm text-slate-400">
              Project files on disk will stay untouched. This action cannot be undone in the app.
            </p>

            <label className="mt-4 block text-sm font-medium text-slate-300">
              Type <span className="font-mono text-white">{deleteModalProject.name}</span> to confirm
            </label>
            <input
              autoFocus
              value={deleteConfirmName}
              onChange={(event) => setDeleteConfirmName(event.target.value)}
              className="mt-2 w-full rounded-xl border border-white/15 bg-slate-800/80 px-3 py-2 text-sm text-white outline-none transition focus:border-red-400/70"
              placeholder={deleteModalProject.name}
            />

            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                onClick={closeDeleteModal}
                disabled={deleteSubmitting}
                className="rounded-xl border border-white/10 bg-slate-800 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDeleteProject}
                disabled={deleteSubmitting || deleteConfirmName.trim() !== deleteModalProject.name.trim()}
                className="rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {deleteSubmitting ? 'Deleting...' : 'Delete Project'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
