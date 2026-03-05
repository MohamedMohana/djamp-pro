import { FolderOpen, Trash2, ExternalLink, PlayCircle, Shield, Database, Terminal, Code } from 'lucide-react';
import { Project } from '../types';
import { api } from '../services/api';

interface ProjectCardProps {
  project: Project;
  onDelete: () => void;
}

export default function ProjectCard({ project, onDelete }: ProjectCardProps) {
  const commandErrorMessage = (fallback: string, output?: string, error?: string): string => {
    const details = [error, output].filter(Boolean).join('\n').trim();
    return details ? `${fallback}:\n\n${details}` : fallback;
  };

  const handleMigrate = async () => {
    try {
      const result = await api.runMigrate(project.id);
      if (!result.success) {
        alert(commandErrorMessage('Migrate failed', result.output, result.error));
        return;
      }
      alert('Migrations completed successfully');
    } catch (error) {
      console.error('Migration failed:', error);
      alert('Migration failed. Check logs for details.');
    }
  };

  const handleCollectstatic = async () => {
    try {
      const result = await api.runCollectstatic(project.id);
      if (!result.success) {
        alert(commandErrorMessage('Collectstatic failed', result.output, result.error));
        return;
      }
      alert('Static files collected successfully');
    } catch (error) {
      console.error('Collectstatic failed:', error);
      alert('Collectstatic failed. Check logs for details.');
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
      alert('Failed to open database shell. Ensure psql/mysql is installed and project DB is configured.');
    }
  };

  const handleOpenDbAdmin = async () => {
    const dbType = (project.database.type || '').toLowerCase();
    if (dbType !== 'postgres') {
      alert('Web DB Admin is currently supported for PostgreSQL projects only.');
      return;
    }

    if (project.status !== 'running') {
      alert('Start the project first, then open DB Admin.');
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
    alert(`Unable to open DB admin automatically. Open this URL manually:\n\n${url}`);
  };

  const handleOpenVSCode = async () => {
    try {
      await api.openVSCode(project.id);
    } catch (error) {
      console.error('Failed to open VS Code:', error);
    }
  };

  const handleOpenBrowser = async () => {
    if (project.status !== 'running') return;
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
        alert(`Unable to open browser automatically. Open this URL manually: ${url}`);
      }
    }
  };

  return (
    <div className="space-y-6">
      {/* Project Info */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Project Path</h3>
          <div className="flex items-center gap-2">
            <FolderOpen size={18} className="text-brand-400" />
            <span className="font-mono text-sm truncate">{project.path}</span>
          </div>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Settings Module</h3>
          <span className="font-mono text-sm">{project.settingsModule}</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Python Version</h3>
          <span className="font-mono text-sm">{project.pythonVersion}</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Runtime Mode</h3>
          <span className="font-mono text-sm uppercase">{project.runtimeMode || 'uv'}</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Debug Mode</h3>
          <span className={`px-2 py-1 rounded text-xs font-medium ${project.debug ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
            {project.debug ? 'ON' : 'OFF'}
          </span>
        </div>
      </div>

      {/* Domain & HTTPS */}
      <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Shield size={20} className="text-brand-400" />
          Domain & HTTPS
        </h3>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-gray-400">Primary Domain</div>
              <div className="font-mono text-lg">{project.domain}</div>
            </div>
            <button
              onClick={handleOpenBrowser}
              disabled={project.status !== 'running'}
              className="rounded-xl bg-brand-500 hover:bg-brand-400 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-4 py-2.5 flex items-center gap-2 transition-colors"
            >
              <ExternalLink size={18} />
              {project.status === 'running' ? 'Open' : 'Start First'}
            </button>
          </div>
          {project.aliases.length > 0 && (
            <div>
              <div className="text-sm text-gray-400 mb-2">Aliases</div>
              <div className="flex flex-wrap gap-2">
                {project.aliases.map((alias) => (
                  <span key={alias} className="rounded-lg border border-white/10 bg-slate-700/70 px-3 py-1 text-sm font-mono">
                    {alias}
                  </span>
                ))}
              </div>
            </div>
          )}
          <div className="flex items-center gap-2 pt-2 border-t border-gray-700">
            {project.httpsEnabled ? (
              <span className="flex items-center gap-1 text-green-400">
                <Shield size={18} />
                HTTPS Enabled
              </span>
            ) : (
              <span className="flex items-center gap-1 text-yellow-400">
                <Shield size={18} />
                HTTPS Disabled
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Database */}
      <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Database size={20} className="text-brand-400" />
          Database
        </h3>
        {project.database.type !== 'none' ? (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-sm text-gray-400">Type</div>
              <div className="font-mono text-sm uppercase">{project.database.type}</div>
            </div>
            <div>
              <div className="text-sm text-gray-400">Port</div>
              <div className="font-mono text-sm">{project.database.port}</div>
            </div>
            <div>
              <div className="text-sm text-gray-400">Database Name</div>
              <div className="font-mono text-sm">{project.database.name}</div>
            </div>
            <div>
              <div className="text-sm text-gray-400">Username</div>
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
                    Open DB Shell
                  </span>
                </button>
                <button
                  onClick={handleOpenDbAdmin}
                  disabled={project.status !== 'running' || (project.database.type || '').toLowerCase() !== 'postgres'}
                  className="rounded-xl border border-white/10 bg-slate-700/65 px-3 py-2 text-white transition-colors hover:bg-slate-600/70 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <span className="flex items-center gap-2">
                    <ExternalLink size={16} className="text-brand-400" />
                    Open DB Admin
                  </span>
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-gray-500">No database configured</div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="rounded-xl border border-white/10 bg-slate-900/65 p-4">
        <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <button
            onClick={handleMigrate}
            disabled={project.status !== 'running'}
            className="rounded-xl border border-white/10 bg-slate-700/65 hover:bg-slate-600/70 disabled:opacity-50 disabled:cursor-not-allowed text-white p-3 flex flex-col items-center gap-2 transition-colors"
          >
            <PlayCircle size={24} className="text-green-400" />
            <span className="text-sm font-medium">Migrate</span>
          </button>
          <button
            onClick={handleCollectstatic}
            disabled={project.status !== 'running'}
            className="rounded-xl border border-white/10 bg-slate-700/65 hover:bg-slate-600/70 disabled:opacity-50 disabled:cursor-not-allowed text-white p-3 flex flex-col items-center gap-2 transition-colors"
          >
            <ExternalLink size={24} className="text-blue-400" />
            <span className="text-sm font-medium">Collectstatic</span>
          </button>
          <button
            onClick={handleOpenShell}
            disabled={project.status !== 'running'}
            className="rounded-xl border border-white/10 bg-slate-700/65 hover:bg-slate-600/70 disabled:opacity-50 disabled:cursor-not-allowed text-white p-3 flex flex-col items-center gap-2 transition-colors"
          >
            <Terminal size={24} className="text-purple-400" />
            <span className="text-sm font-medium">Shell</span>
          </button>
          <button
            onClick={handleOpenDbShell}
            disabled={project.status !== 'running' || project.database.type === 'none'}
            className="rounded-xl border border-white/10 bg-slate-700/65 hover:bg-slate-600/70 disabled:opacity-50 disabled:cursor-not-allowed text-white p-3 flex flex-col items-center gap-2 transition-colors"
          >
            <Database size={24} className="text-brand-400" />
            <span className="text-sm font-medium">DB Shell</span>
          </button>
          <button
            onClick={handleOpenVSCode}
            className="rounded-xl border border-white/10 bg-slate-700/65 hover:bg-slate-600/70 text-white p-3 flex flex-col items-center gap-2 transition-colors"
          >
            <Code size={24} className="text-brand-400" />
            <span className="text-sm font-medium">VS Code</span>
          </button>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="rounded-xl border border-red-700/50 bg-red-950/30 p-4">
        <h3 className="text-lg font-semibold text-red-400 mb-4">Danger Zone</h3>
        <button
          onClick={onDelete}
          className="rounded-xl bg-red-700 hover:bg-red-600 text-white px-4 py-2.5 flex items-center gap-2 transition-colors"
        >
          <Trash2 size={18} />
          Delete Project
        </button>
      </div>
    </div>
  );
}
