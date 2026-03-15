import { FolderOpen, Trash2, ExternalLink, PlayCircle, Shield, Database, Terminal, Code } from 'lucide-react';
import { Project } from '../types';
import { useI18n } from '../i18n';
import { api } from '../services/api';

interface ProjectCardProps {
  project: Project;
  onDelete: () => void;
}

export default function ProjectCard({ project, onDelete }: ProjectCardProps) {
  const { t } = useI18n();
  const runtimeMode = project.runtimeMode || 'uv';

  const commandErrorMessage = (fallback: string, output?: string, error?: string): string => {
    const details = [error, output].filter(Boolean).join('\n').trim();
    return details ? `${fallback}:\n\n${details}` : fallback;
  };

  const handleMigrate = async () => {
    try {
      const result = await api.runMigrate(project.id);
      if (!result.success) {
        alert(commandErrorMessage(t.projectCard.migrateFailed, result.output, result.error));
        return;
      }
      alert(t.projectCard.migrateSuccess);
    } catch (error) {
      console.error('Migration failed:', error);
      alert(t.projectCard.migrateError);
    }
  };

  const handleCollectstatic = async () => {
    try {
      const result = await api.runCollectstatic(project.id);
      if (!result.success) {
        alert(commandErrorMessage(t.projectCard.collectstaticFailed, result.output, result.error));
        return;
      }
      alert(t.projectCard.collectstaticSuccess);
    } catch (error) {
      console.error('Collectstatic failed:', error);
      alert(t.projectCard.collectstaticError);
    }
  };

  const handleOpenShell = async () => {
    try {
      await api.openShell(project.id);
    } catch (error) {
      console.error('Failed to open shell:', error);
    }
  };

  const handleOpenDbShell = async () => {
    try {
      await api.openDatabaseShell(project.id);
    } catch (error) {
      console.error('Failed to open database shell:', error);
      alert(t.projectCard.openDbShellError);
    }
  };

  const handleOpenDbAdmin = async () => {
    const dbType = (project.database.type || '').toLowerCase();
    if (dbType !== 'postgres') {
      alert(t.projectCard.dbAdminPostgresOnly);
      return;
    }

    if (project.status !== 'running') {
      alert(t.projectCard.dbAdminStartFirst);
      return;
    }

    const protocol = project.httpsEnabled ? 'https' : 'http';
    let url = `${protocol}://${project.domain}/phpmyadmin/`;

    try {
      const status = await api.getProxyStatus();
      const proxyActive = project.httpsEnabled ? status.proxyHttpsActive : status.proxyHttpActive;
      const standardActive = project.httpsEnabled ? status.standardHttpsActive : status.standardHttpActive;

      if (!proxyActive || !standardActive) {
        const port = project.httpsEnabled ? status.proxyPort : status.proxyHttpPort;
        url = `${protocol}://${project.domain}:${port}/phpmyadmin/`;
      }
    } catch (error) {
      console.error('Failed to detect proxy status for DB admin URL:', error);
    }

    try {
      const response = await api.getDatabaseAdminUrl(project.id);
      if (response?.url) {
        url = response.url;
      }
    } catch (error) {
      console.error('Failed to resolve DB admin URL from backend, using computed URL:', error);
    }

    try {
      await api.openInBrowser(url);
      return;
    } catch (error) {
      console.error('Native open failed for DB admin, trying window.open fallback:', error);
    }

    const opened = window.open(url, '_blank');
    if (opened) {
      return;
    }

    try {
      await navigator.clipboard.writeText(url);
    } catch {
      // Clipboard may be unavailable; continue with manual URL alert.
    }
    alert(t.projectCard.dbAdminManualOpen(url));
  };

  const handleOpenVSCode = async () => {
    try {
      await api.openVSCode(project.id);
    } catch (error) {
      console.error('Failed to open VS Code:', error);
    }
  };

  const handleOpenBrowser = async () => {
    if (project.status !== 'running') {
      return;
    }

    const protocol = project.httpsEnabled ? 'https' : 'http';
    let url = `${protocol}://${project.domain}`;
    try {
      const status = await api.getProxyStatus();
      const proxyActive = project.httpsEnabled ? status.proxyHttpsActive : status.proxyHttpActive;
      const standardActive = project.httpsEnabled ? status.standardHttpsActive : status.standardHttpActive;

      if (!proxyActive || !standardActive) {
        const port = project.httpsEnabled ? status.proxyPort : status.proxyHttpPort;
        url = `${protocol}://${project.domain}:${port}`;
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

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
          <h3 className="mb-2 text-sm font-medium text-gray-400">{t.projectCard.projectPath}</h3>
          <div className="flex items-center gap-2">
            <FolderOpen size={18} className="text-brand-400" />
            <span className="truncate font-mono text-sm">{project.path}</span>
          </div>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
          <h3 className="mb-2 text-sm font-medium text-gray-400">{t.projectCard.settingsModule}</h3>
          <span className="font-mono text-sm">{project.settingsModule}</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
          <h3 className="mb-2 text-sm font-medium text-gray-400">{t.projectCard.pythonVersion}</h3>
          <span className="font-mono text-sm">{project.pythonVersion}</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
          <h3 className="mb-2 text-sm font-medium text-gray-400">{t.projectCard.runtimeMode}</h3>
          <span className="font-mono text-sm">{t.common.runtimeModes[runtimeMode]}</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
          <h3 className="mb-2 text-sm font-medium text-gray-400">{t.projectCard.debugMode}</h3>
          <span
            className={`rounded px-2 py-1 text-xs font-medium ${
              project.debug ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'
            }`}
          >
            {project.debug ? t.projectCard.debugOn : t.projectCard.debugOff}
          </span>
        </div>
      </div>

      <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
        <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
          <Shield size={20} className="text-brand-400" />
          {t.projectCard.domainAndHttps}
        </h3>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-gray-400">{t.projectCard.primaryDomain}</div>
              <div className="font-mono text-lg">{project.domain}</div>
            </div>
            <button
              onClick={handleOpenBrowser}
              disabled={project.status !== 'running'}
              className="flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-white transition-colors hover:bg-brand-400 disabled:cursor-not-allowed disabled:bg-slate-700"
            >
              <ExternalLink size={18} />
              {project.status === 'running' ? t.projectCard.open : t.projectCard.startFirst}
            </button>
          </div>
          {project.aliases.length > 0 && (
            <div>
              <div className="mb-2 text-sm text-gray-400">{t.projectCard.aliases}</div>
              <div className="flex flex-wrap gap-2">
                {project.aliases.map((alias) => (
                  <span
                    key={alias}
                    className="rounded-lg border border-white/10 bg-slate-700/70 px-3 py-1 text-sm font-mono"
                  >
                    {alias}
                  </span>
                ))}
              </div>
            </div>
          )}
          <div className="flex items-center gap-2 border-t border-gray-700 pt-2">
            {project.httpsEnabled ? (
              <span className="flex items-center gap-1 text-green-400">
                <Shield size={18} />
                {t.projectCard.httpsEnabled}
              </span>
            ) : (
              <span className="flex items-center gap-1 text-yellow-400">
                <Shield size={18} />
                {t.projectCard.httpsDisabled}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
        <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
          <Database size={20} className="text-brand-400" />
          {t.projectCard.database}
        </h3>
        {project.database.type !== 'none' ? (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-sm text-gray-400">{t.projectCard.type}</div>
              <div className="font-mono text-sm">{t.common.databaseTypes[project.database.type]}</div>
            </div>
            <div>
              <div className="text-sm text-gray-400">{t.projectCard.port}</div>
              <div className="font-mono text-sm">{project.database.port}</div>
            </div>
            <div>
              <div className="text-sm text-gray-400">{t.projectCard.databaseName}</div>
              <div className="font-mono text-sm">{project.database.name}</div>
            </div>
            <div>
              <div className="text-sm text-gray-400">{t.projectCard.username}</div>
              <div className="font-mono text-sm">{project.database.username}</div>
            </div>
            <div className="col-span-2 border-t border-gray-700 pt-2">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={handleOpenDbShell}
                  disabled={project.status !== 'running'}
                  className="rounded-xl border border-white/10 bg-slate-700/65 px-3 py-2 text-white transition-colors hover:bg-slate-600/70 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <span className="flex items-center gap-2">
                    <Database size={16} className="text-brand-400" />
                    {t.projectCard.openDbShell}
                  </span>
                </button>
                <button
                  onClick={handleOpenDbAdmin}
                  disabled={project.status !== 'running' || project.database.type !== 'postgres'}
                  className="rounded-xl border border-white/10 bg-slate-700/65 px-3 py-2 text-white transition-colors hover:bg-slate-600/70 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <span className="flex items-center gap-2">
                    <ExternalLink size={16} className="text-brand-400" />
                    {t.projectCard.openDbAdmin}
                  </span>
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-gray-500">{t.projectCard.noDatabase}</div>
        )}
      </div>

      <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
        <h3 className="mb-4 text-lg font-semibold">{t.projectCard.quickActions}</h3>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <button
            onClick={handleMigrate}
            disabled={project.status !== 'running'}
            className="flex flex-col items-center gap-2 rounded-xl border border-white/10 bg-slate-700/65 p-3 text-white transition-colors hover:bg-slate-600/70 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <PlayCircle size={24} className="text-green-400" />
            <span className="text-sm font-medium">{t.projectCard.migrate}</span>
          </button>
          <button
            onClick={handleCollectstatic}
            disabled={project.status !== 'running'}
            className="flex flex-col items-center gap-2 rounded-xl border border-white/10 bg-slate-700/65 p-3 text-white transition-colors hover:bg-slate-600/70 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ExternalLink size={24} className="text-blue-400" />
            <span className="text-sm font-medium">{t.projectCard.collectstatic}</span>
          </button>
          <button
            onClick={handleOpenShell}
            disabled={project.status !== 'running'}
            className="flex flex-col items-center gap-2 rounded-xl border border-white/10 bg-slate-700/65 p-3 text-white transition-colors hover:bg-slate-600/70 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Terminal size={24} className="text-purple-400" />
            <span className="text-sm font-medium">{t.projectCard.shell}</span>
          </button>
          <button
            onClick={handleOpenDbShell}
            disabled={project.status !== 'running' || project.database.type === 'none'}
            className="flex flex-col items-center gap-2 rounded-xl border border-white/10 bg-slate-700/65 p-3 text-white transition-colors hover:bg-slate-600/70 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Database size={24} className="text-brand-400" />
            <span className="text-sm font-medium">{t.projectCard.dbShell}</span>
          </button>
          <button
            onClick={handleOpenVSCode}
            className="flex flex-col items-center gap-2 rounded-xl border border-white/10 bg-slate-700/65 p-3 text-white transition-colors hover:bg-slate-600/70"
          >
            <Code size={24} className="text-brand-400" />
            <span className="text-sm font-medium">{t.projectCard.vsCode}</span>
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-red-700/50 bg-red-950/30 p-4">
        <h3 className="mb-4 text-lg font-semibold text-red-400">{t.projectCard.dangerZone}</h3>
        <button
          onClick={onDelete}
          className="flex items-center gap-2 rounded-xl bg-red-700 px-4 py-2.5 text-white transition-colors hover:bg-red-600"
        >
          <Trash2 size={18} />
          {t.projectCard.deleteProject}
        </button>
      </div>
    </div>
  );
}
