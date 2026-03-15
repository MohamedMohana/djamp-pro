import { useEffect, useState } from 'react';
import {
  Play,
  Square,
  Settings,
  Plus,
  RefreshCw,
  Database,
  Globe,
  Code,
  type LucideIcon,
} from 'lucide-react';
import { api } from './services/api';
import type { Project } from './types';
import { useI18n, type Locale } from './i18n';
import { cn, getStatusColor, getStatusIcon } from './utils';

import ProjectList from './components/ProjectList';
import ProjectCard from './components/ProjectCard';
import ProjectAvatar from './components/ProjectAvatar';
import AddProjectModal from './components/AddProjectModal';
import SettingsPanel from './components/SettingsPanel';
import djampMark from './assets/djamp-mark.png';

type AppTab = 'projects' | 'logs' | 'environment';
type LogSource = 'django' | 'proxy' | 'database';
type ToolbarActionTone = 'neutral' | 'start' | 'stop';

const APP_TABS: AppTab[] = ['projects', 'logs', 'environment'];
const LOG_SOURCES: LogSource[] = ['django', 'proxy', 'database'];
const LOCALES: Locale[] = ['en', 'ar'];

interface ToolbarActionProps {
  icon: LucideIcon;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  tone?: ToolbarActionTone;
}

function ToolbarAction({ icon: Icon, label, onClick, disabled, tone = 'neutral' }: ToolbarActionProps) {
  const toneClasses =
    tone === 'start'
      ? 'border-emerald-400/20 bg-emerald-500/12 text-emerald-50 hover:bg-emerald-500/22'
      : tone === 'stop'
        ? 'border-red-400/20 bg-red-500/12 text-red-50 hover:bg-red-500/22'
        : 'border-white/8 bg-white/5 text-[var(--mamp-text)] hover:bg-white/10';

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'flex min-w-[74px] flex-col items-center justify-center gap-1 rounded-lg border px-3 py-2 text-center text-[11px] font-semibold transition',
        toneClasses,
        disabled && 'cursor-not-allowed opacity-40 hover:bg-inherit',
      )}
    >
      <Icon size={18} />
      <span className="leading-none">{label}</span>
    </button>
  );
}

function App() {
  const { direction, locale, setLocale, t } = useI18n();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<AppTab>('projects');
  const [logsSource, setLogsSource] = useState<LogSource>('django');
  const [logsText, setLogsText] = useState('');
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
    void loadProjects();
    const interval = setInterval(() => {
      void loadProjects();
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const selectedProjectId = selectedProject?.id;

    const loadLogs = async () => {
      if (!selectedProjectId || activeTab !== 'logs') {
        return;
      }

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

    void loadLogs();
    const interval = setInterval(() => {
      void loadLogs();
    }, 2000);
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

        const fresh = loaded.find((project) => project.id === prev.id);
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
        alert(t.app.httpsWarning(certWarning));
      }
      if (result?.hosts && !result.hosts.success) {
        alert(t.app.domainWarning(result.hosts.error || t.app.hostsUpdateFallback));
      }
      if (result?.proxy && !result.proxy.success) {
        alert(t.app.proxyWarning(result.proxy.error || t.app.proxyReloadFallback));
      }
      if (result?.proxy?.success && result.proxy.output?.includes('Use https://')) {
        alert(t.app.proxyInfo(result.proxy.output));
      }
      await loadProjects();
    } catch (error) {
      console.error('Failed to start project:', error);
      alert(t.app.failedStart(extractErrorMessage(error, t.app.unknownError)));
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
      alert(t.app.failedStop(extractErrorMessage(error, t.app.unknownError)));
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
      alert(t.app.failedRestart(extractErrorMessage(error, t.app.unknownError)));
      setProjectStatusLocal(id, 'error');
    } finally {
      setActionProjectId(null);
      setActionKind(null);
    }
  };

  const handleOpenSelectedSite = async () => {
    if (!selectedProject || selectedProject.status !== 'running') {
      return;
    }

    const protocol = selectedProject.httpsEnabled ? 'https' : 'http';
    let url = `${protocol}://${selectedProject.domain}`;
    try {
      const status = await api.getProxyStatus();
      const proxyActive = selectedProject.httpsEnabled ? status.proxyHttpsActive : status.proxyHttpActive;
      const standardActive = selectedProject.httpsEnabled ? status.standardHttpsActive : status.standardHttpActive;

      if (!proxyActive || !standardActive) {
        const port = selectedProject.httpsEnabled ? status.proxyPort : status.proxyHttpPort;
        url = `${protocol}://${selectedProject.domain}:${port}`;
      }
    } catch (error) {
      console.error('Failed to detect proxy status:', error);
    }

    try {
      await api.openInBrowser(url);
    } catch (error) {
      console.error('Failed to open browser via Tauri API, falling back to window.open:', error);
      const opened = window.open(url, '_blank');
      if (!opened) {
        alert(t.projectCard.browserManualOpen(url));
      }
    }
  };

  const handleOpenSelectedEditor = async () => {
    if (!selectedProject) {
      return;
    }

    try {
      await api.openVSCode(selectedProject.id);
    } catch (error) {
      console.error('Failed to open VS Code:', error);
    }
  };

  const handleDeleteProject = (project: Project) => {
    setDeleteModalProject(project);
    setDeleteConfirmName('');
  };

  const closeDeleteModal = () => {
    if (deleteSubmitting) {
      return;
    }

    setDeleteModalProject(null);
    setDeleteConfirmName('');
  };

  const handleConfirmDeleteProject = async () => {
    if (!deleteModalProject) {
      return;
    }

    const expectedName = deleteModalProject.name.trim();
    if (deleteConfirmName.trim() !== expectedName) {
      alert(t.app.deleteProjectTypeExact(expectedName));
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
      alert(t.app.failedDelete(extractErrorMessage(error, t.app.unknownError)));
    } finally {
      setDeleteSubmitting(false);
    }
  };

  const isSelectedBusy = Boolean(selectedProject && actionProjectId === selectedProject.id);
  const selectedRuntime = selectedProject?.runtimeMode || 'uv';

  return (
    <div dir={direction} className="app-bg min-h-screen text-[var(--mamp-text)]">
      <div className="mamp-window flex h-screen flex-col">
        <header className="mamp-toolbar">
          <div className="flex min-w-0 items-center gap-3">
            <img
              src={djampMark}
              alt="DJAMP PRO"
              className="h-11 w-11 rounded-xl border border-white/10 bg-black/20 p-1.5 object-contain"
            />
            <div className="min-w-0">
              <div className="truncate text-xl font-bold tracking-tight text-white">DJAMP PRO</div>
              <div className="truncate text-xs text-[var(--mamp-text-muted)]">{t.app.subtitle}</div>
            </div>
          </div>

          <div className="hidden min-w-0 flex-1 items-center justify-center xl:flex">
            <div className="text-center">
              <div className="text-lg font-semibold text-[var(--mamp-text)]">
                DJAMP PRO - {t.app.hostsTitle}
              </div>
              <div className="text-xs text-[var(--mamp-text-muted)]">
                {selectedProject ? selectedProject.domain : t.app.noProjectSelectedDescription}
              </div>
            </div>
          </div>

          <div className="flex items-stretch gap-1.5">
            <ToolbarAction
              icon={Plus}
              label={t.app.addProject}
              onClick={() => setShowAddModal(true)}
            />
            <ToolbarAction
              icon={Globe}
              label={t.app.openSite}
              onClick={() => void handleOpenSelectedSite()}
              disabled={!selectedProject || selectedProject.status !== 'running'}
            />
            <ToolbarAction
              icon={Code}
              label={t.app.editor}
              onClick={() => void handleOpenSelectedEditor()}
              disabled={!selectedProject}
            />
            <ToolbarAction
              icon={RefreshCw}
              label={t.app.restart}
              onClick={() => selectedProject && void handleRestartProject(selectedProject.id)}
              disabled={!selectedProject || isSelectedBusy}
            />
            {selectedProject?.status === 'running' ? (
              <ToolbarAction
                icon={Square}
                label={isSelectedBusy && actionKind === 'stop' ? t.app.stopping : t.app.stop}
                onClick={() => selectedProject && void handleStopProject(selectedProject.id)}
                disabled={!selectedProject || isSelectedBusy}
                tone="stop"
              />
            ) : (
              <ToolbarAction
                icon={Play}
                label={isSelectedBusy && actionKind === 'start' ? t.app.starting : t.app.start}
                onClick={() => selectedProject && void handleStartProject(selectedProject.id)}
                disabled={!selectedProject || isSelectedBusy}
                tone="start"
              />
            )}
            <ToolbarAction
              icon={Settings}
              label={t.app.settings}
              onClick={() => setShowSettings(true)}
            />

            <div className="ms-2 flex min-w-[132px] flex-col justify-center rounded-lg border border-white/8 bg-black/12 px-2 py-2">
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--mamp-text-dim)]">
                {t.common.language}
              </div>
              <div className="inline-flex rounded-md border border-white/8 bg-black/20 p-1">
                {LOCALES.map((item) => {
                  const isActive = locale === item;
                  const label = item === 'en' ? t.common.english : t.common.arabic;
                  return (
                    <button
                      key={item}
                      onClick={() => setLocale(item)}
                      className={cn(
                        'rounded px-2.5 py-1 text-[11px] font-semibold transition',
                        isActive
                          ? 'bg-[var(--mamp-accent)] text-white'
                          : 'text-[var(--mamp-text-muted)] hover:bg-white/8 hover:text-white',
                      )}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </header>

        <div className="min-h-0 flex flex-1">
          <aside className="mamp-sidebar flex w-[19.5rem] min-w-[19.5rem] flex-col">
            <div className="flex items-center justify-between border-b border-white/8 px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--mamp-text-dim)]">
              <span>{t.app.sidebarName}</span>
              <span>{t.app.allProjects}</span>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto">
              <ProjectList
                projects={projects}
                selectedId={selectedProject?.id}
                onSelect={setSelectedProject}
                loading={loading}
              />
            </div>

            <div className="flex items-center justify-between border-t border-white/8 px-3 py-2">
              <span className="text-xs text-[var(--mamp-text-muted)]">{t.app.projectCount(projects.length)}</span>
              <button
                onClick={() => void loadProjects()}
                className="inline-flex items-center gap-1 rounded-md border border-white/8 bg-white/5 px-2.5 py-1.5 text-xs font-semibold text-[var(--mamp-text-muted)] transition hover:bg-white/10 hover:text-white"
              >
                <RefreshCw size={13} />
                {t.app.refreshList}
              </button>
            </div>
          </aside>

          <main className="mamp-content flex min-w-0 flex-1 flex-col">
            {selectedProject ? (
              <>
                <div className="border-b border-white/8 px-6 py-5">
                  <div className="flex items-start justify-between gap-6">
                    <div className="flex min-w-0 items-start gap-4">
                      <ProjectAvatar name={selectedProject.name} size="md" />
                      <div className="min-w-0">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--mamp-text-dim)]">
                          {t.projectCard.sectionProject}
                        </div>
                        <h2 className="truncate text-3xl font-semibold tracking-tight text-white">
                          {selectedProject.name}
                        </h2>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <span
                            className={cn(
                              'inline-flex items-center gap-2 rounded-full border border-white/8 bg-black/15 px-3 py-1 text-sm',
                              getStatusColor(selectedProject.status),
                            )}
                          >
                            <span>{getStatusIcon(selectedProject.status)}</span>
                            {t.common.status[selectedProject.status]}
                          </span>
                          <span className="inline-flex items-center gap-2 rounded-full border border-white/8 bg-black/15 px-3 py-1 text-sm text-[var(--mamp-text-muted)]">
                            <Globe size={14} />
                            {selectedProject.domain}
                          </span>
                          <span className="inline-flex items-center gap-2 rounded-full border border-white/8 bg-black/15 px-3 py-1 text-sm text-[var(--mamp-text-muted)]">
                            {t.common.runtimeModes[selectedRuntime]}
                          </span>
                          {selectedProject.database.type !== 'none' && (
                            <span className="inline-flex items-center gap-2 rounded-full border border-white/8 bg-black/15 px-3 py-1 text-sm text-[var(--mamp-text-muted)]">
                              <Database size={14} />
                              {t.common.databaseTypes[selectedProject.database.type]}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="hidden max-w-[24rem] text-end lg:block">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--mamp-text-dim)]">
                        {t.projectCard.projectPath}
                      </div>
                      <div className="mt-1 truncate font-mono text-sm text-[var(--mamp-text-muted)]">
                        {selectedProject.path}
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-white/6 pt-4">
                    {APP_TABS.map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={cn(
                          'rounded-md border px-3 py-1.5 text-sm font-semibold transition',
                          activeTab === tab
                            ? 'border-[var(--mamp-accent)] bg-[var(--mamp-accent)] text-white'
                            : 'border-white/8 bg-black/12 text-[var(--mamp-text-muted)] hover:bg-white/8 hover:text-white',
                        )}
                      >
                        {t.app.tabs[tab]}
                      </button>
                    ))}
                  </div>
                </div>

                <section className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
                  {activeTab === 'projects' && (
                    <ProjectCard
                      project={selectedProject}
                      onDelete={() => handleDeleteProject(selectedProject)}
                    />
                  )}

                  {activeTab === 'logs' && (
                    <div className="mamp-section">
                      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/6 pb-4">
                        <div className="flex flex-wrap gap-2">
                          {LOG_SOURCES.map((source) => (
                            <button
                              key={source}
                              onClick={() => setLogsSource(source)}
                              className={cn(
                                'rounded-md border px-3 py-1.5 text-sm font-semibold transition',
                                logsSource === source
                                  ? 'border-[var(--mamp-accent)] bg-[var(--mamp-accent)] text-white'
                                  : 'border-white/8 bg-black/12 text-[var(--mamp-text-muted)] hover:bg-white/8 hover:text-white',
                              )}
                            >
                              {t.app.logSources[source]}
                            </button>
                          ))}
                        </div>
                        <span className="text-xs text-[var(--mamp-text-muted)]">
                          {logsLoading ? t.common.loading : t.app.autoRefreshing}
                        </span>
                      </div>

                      <pre className="mamp-console mt-4">{logsText || t.app.noLogs}</pre>
                    </div>
                  )}

                  {activeTab === 'environment' && (
                    <div className="mamp-section">
                      <div className="mamp-section-title">{t.app.environmentVariables}</div>
                      <p className="mb-4 text-sm text-[var(--mamp-text-muted)]">
                        {t.app.environmentDescription}
                      </p>
                      {Object.entries(selectedProject.environmentVars || {}).length === 0 ? (
                        <div className="rounded-lg border border-white/8 bg-black/10 p-4 text-sm text-[var(--mamp-text-muted)]">
                          {t.app.environmentEmpty}
                        </div>
                      ) : (
                        <div className="space-y-0 divide-y divide-white/6">
                          {Object.entries(selectedProject.environmentVars).map(([key, value]) => (
                            <div
                              key={key}
                              className="grid gap-3 py-3 md:grid-cols-[12rem_minmax(0,1fr)]"
                            >
                              <span className="break-all font-mono text-[13px] text-[var(--mamp-text-dim)]">
                                {key}
                              </span>
                              <span className="min-w-0 break-all whitespace-pre-wrap rounded-md border border-white/6 bg-black/12 px-3 py-2 font-mono text-[13px] text-[var(--mamp-text)]">
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
                <div className="max-w-md text-center">
                  <Globe size={56} className="mx-auto mb-4 text-[var(--mamp-text-dim)]" />
                  <h2 className="mb-2 text-2xl font-semibold text-white">{t.app.noProjectSelected}</h2>
                  <p className="text-sm text-[var(--mamp-text-muted)]">{t.app.noProjectSelectedDescription}</p>
                </div>
              </div>
            )}
          </main>
        </div>
      </div>

      {showAddModal && <AddProjectModal onClose={() => setShowAddModal(false)} onAdd={loadProjects} />}
      {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}

      {deleteModalProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-red-500/30 bg-[var(--mamp-panel)] p-5 shadow-[0_25px_60px_rgba(0,0,0,0.45)]">
            <h3 className="text-xl font-semibold text-red-300">{t.app.deleteProjectTitle}</h3>
            <p className="mt-3 text-sm text-[var(--mamp-text)]">
              {t.app.deleteProjectIntro(deleteModalProject.name)}
            </p>
            <p className="mt-2 text-sm text-[var(--mamp-text-muted)]">{t.app.deleteProjectNote}</p>

            <label className="mt-4 block text-sm font-medium text-[var(--mamp-text)]">
              {t.app.deleteProjectConfirm(deleteModalProject.name)}
            </label>
            <input
              autoFocus
              value={deleteConfirmName}
              onChange={(event) => setDeleteConfirmName(event.target.value)}
              className="mt-2 w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none transition focus:border-red-400/70"
              placeholder={deleteModalProject.name}
            />

            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                onClick={closeDeleteModal}
                disabled={deleteSubmitting}
                className="rounded-md border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-[var(--mamp-text)] transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {t.common.cancel}
              </button>
              <button
                onClick={handleConfirmDeleteProject}
                disabled={deleteSubmitting || deleteConfirmName.trim() !== deleteModalProject.name.trim()}
                className="rounded-md border border-red-400/30 bg-red-500/15 px-4 py-2 text-sm font-semibold text-red-100 transition hover:bg-red-500/25 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {deleteSubmitting ? t.app.deleting : t.app.deleteProjectTitle}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
