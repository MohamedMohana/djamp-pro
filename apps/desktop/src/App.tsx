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
import djampMark from './assets/djamp-mark.svg';

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
    } catch (_ignored) {
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
    const loadLogs = async () => {
      if (!selectedProject || activeTab !== 'logs') return;
      setLogsLoading(true);
      try {
        const text = await api.getLogs(selectedProject.id, logsSource);
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
      // Backend may return a warning if cert/CA steps failed but the Django server started.
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

  const handleDeleteProject = async (id: string) => {
    if (confirm('Are you sure you want to delete this project?')) {
      try {
        await api.deleteProject(id);
        await loadProjects();
        if (selectedProject?.id === id) {
          setSelectedProject(null);
        }
      } catch (error) {
        console.error('Failed to delete project:', error);
        alert(`Failed to delete project: ${extractErrorMessage(error, 'Unknown error')}`);
      }
    }
  };

  const handleAddProject = () => {
    setShowAddModal(true);
  };

  const isSelectedBusy = Boolean(selectedProject && actionProjectId === selectedProject.id);

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="flex h-screen">
        {/* Sidebar */}
        <div className="w-80 bg-gray-800 border-r border-gray-700 flex flex-col">
          <div className="p-4 border-b border-gray-700">
            <div className="flex items-center gap-3">
              <img src={djampMark} alt="DJAMP PRO" className="h-10 w-10 rounded-xl ring-1 ring-white/10" />
              <div>
                <h1 className="text-2xl font-bold text-brand-400">DJAMP PRO</h1>
                <p className="text-sm text-gray-400 mt-1">Django Local Environment Manager</p>
              </div>
            </div>
          </div>

          <div className="p-4 border-b border-gray-700">
            <button
              onClick={handleAddProject}
              className="w-full bg-brand-600 hover:bg-brand-700 text-white font-medium py-2 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors"
            >
              <Plus size={18} />
              Add Project
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

          <div className="p-4 border-t border-gray-700">
            <button
              onClick={() => setShowSettings(true)}
              className="w-full bg-gray-700 hover:bg-gray-600 text-white font-medium py-2 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors"
            >
              <Settings size={18} />
              Settings
            </button>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex flex-col">
          {selectedProject ? (
            <>
              {/* Project Header */}
              <div className="bg-gray-800 border-b border-gray-700 p-6">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    <ProjectAvatar name={selectedProject.name} size="md" className="mt-1" />
                    <div>
                      <h2 className="text-3xl font-bold">{selectedProject.name}</h2>
                    <div className="flex items-center gap-4 mt-2 text-gray-400">
                      <span className={cn('flex items-center gap-1', getStatusColor(selectedProject.status))}>
                        <span>{getStatusIcon(selectedProject.status)}</span>
                        {selectedProject.status}
                      </span>
                      <span className="flex items-center gap-1">
                        <Globe size={16} />
                        {selectedProject.httpsEnabled ? 'https://' : 'http://'}{selectedProject.domain}
                      </span>
                      {selectedProject.database.type !== 'none' && (
                        <span className="flex items-center gap-1">
                          <Database size={16} />
                          {selectedProject.database.type}
                        </span>
                      )}
                    </div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleRestartProject(selectedProject.id)}
                      disabled={isSelectedBusy}
                      className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-white p-2 rounded-lg transition-colors"
                      title="Restart"
                    >
                      <RefreshCw size={20} />
                    </button>
                    {selectedProject.status === 'running' ? (
                      <button
                        onClick={() => handleStopProject(selectedProject.id)}
                        disabled={isSelectedBusy}
                        className="bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors"
                      >
                        <Square size={18} />
                        {isSelectedBusy && actionKind === 'stop' ? 'Stopping...' : 'Stop'}
                      </button>
                    ) : (
                      <button
                        onClick={() => handleStartProject(selectedProject.id)}
                        disabled={isSelectedBusy}
                        className="bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors"
                      >
                        <Play size={18} />
                        {isSelectedBusy && actionKind === 'start' ? 'Starting...' : 'Start'}
                      </button>
                    )}
                  </div>
                </div>

                {/* Tabs */}
                <div className="flex gap-4 mt-6 border-b border-gray-700">
                  {(['projects', 'logs', 'environment'] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={cn(
                        'pb-3 px-2 font-medium transition-colors capitalize',
                        activeTab === tab
                          ? 'text-brand-400 border-b-2 border-brand-400'
                          : 'text-gray-400 hover:text-white'
                      )}
                    >
                      {tab}
                    </button>
                  ))}
                </div>
              </div>

              {/* Tab Content */}
              <div className="flex-1 overflow-y-auto p-6">
                {activeTab === 'projects' && (
                  <ProjectCard
                    project={selectedProject}
                    onDelete={() => handleDeleteProject(selectedProject.id)}
                  />
                )}
                {activeTab === 'logs' && (
                  <div className="bg-gray-800 rounded-lg p-4 h-full min-h-0 flex flex-col gap-3">
                    <div className="flex gap-2">
                      {(['django', 'proxy', 'database'] as const).map((source) => (
                        <button
                          key={source}
                          onClick={() => setLogsSource(source)}
                          className={cn(
                            'px-3 py-1 rounded font-medium capitalize transition-colors',
                            logsSource === source
                              ? 'bg-brand-600 text-white'
                              : 'bg-gray-700 hover:bg-gray-600 text-gray-200'
                          )}
                        >
                          {source}
                        </button>
                      ))}
                      <div className="flex-1" />
                      <span className="text-sm text-gray-400">
                        {logsLoading ? 'Loading...' : 'Auto-refreshing'}
                      </span>
                    </div>

                    <pre className="flex-1 min-h-0 overflow-auto rounded-lg border border-gray-700 bg-gray-900/80 p-3 font-mono text-xs text-gray-200 whitespace-pre-wrap">
                      {logsText ? logsText : 'No logs yet.'}
                    </pre>
                  </div>
                )}
                {activeTab === 'environment' && (
                  <div className="bg-gray-800 rounded-lg p-6">
                    <h3 className="text-xl font-semibold mb-2">Environment Variables</h3>
                    <p className="text-sm text-gray-400 mb-4">Loaded from project <code>.env</code> (sensitive values are masked).</p>
                    {Object.entries(selectedProject.environmentVars || {}).length === 0 ? (
                      <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4 text-sm text-gray-400">
                        No environment variables were found in the project <code>.env</code> file.
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {Object.entries(selectedProject.environmentVars).map(([key, value]) => (
                          <div key={key} className="flex items-center gap-4">
                            <span className="w-56 shrink-0 text-gray-400 font-mono text-sm">{key}</span>
                            <span className="flex-1 bg-gray-700 px-3 py-2 rounded font-mono text-sm break-all">
                              {value}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <Globe size={64} className="mx-auto text-gray-600 mb-4" />
                <h2 className="text-2xl font-semibold text-gray-400 mb-2">No Project Selected</h2>
                <p className="text-gray-500">Select a project from the sidebar or add a new one</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {showAddModal && (
        <AddProjectModal onClose={() => setShowAddModal(false)} onAdd={loadProjects} />
      )}

      {showSettings && (
        <SettingsPanel onClose={() => setShowSettings(false)} />
      )}
    </div>
  );
}

export default App;
