import { FolderOpen, Trash2, ExternalLink, PlayCircle, Shield, Database, Terminal, Code } from 'lucide-react';
import { Project } from '../types';
import { api } from '../services/api';

interface ProjectCardProps {
  project: Project;
  onDelete: () => void;
}

export default function ProjectCard({ project, onDelete }: ProjectCardProps) {
  const handleMigrate = async () => {
    try {
      await api.runMigrate(project.id);
      alert('Migrations completed successfully');
    } catch (error) {
      console.error('Migration failed:', error);
      alert('Migration failed. Check logs for details.');
    }
  };

  const handleCollectstatic = async () => {
    try {
      await api.runCollectstatic(project.id);
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

  const handleOpenVSCode = async () => {
    try {
      await api.openVSCode(project.id);
    } catch (error) {
      console.error('Failed to open VS Code:', error);
    }
  };

  const handleOpenBrowser = () => {
    const protocol = project.httpsEnabled ? 'https' : 'http';
    window.open(`${protocol}://${project.domain}`, '_blank');
  };

  return (
    <div className="space-y-6">
      {/* Project Info */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Project Path</h3>
          <div className="flex items-center gap-2">
            <FolderOpen size={18} className="text-brand-400" />
            <span className="font-mono text-sm truncate">{project.path}</span>
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Settings Module</h3>
          <span className="font-mono text-sm">{project.settingsModule}</span>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Python Version</h3>
          <span className="font-mono text-sm">{project.pythonVersion}</span>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Debug Mode</h3>
          <span className={`px-2 py-1 rounded text-xs font-medium ${project.debug ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
            {project.debug ? 'ON' : 'OFF'}
          </span>
        </div>
      </div>

      {/* Domain & HTTPS */}
      <div className="bg-gray-800 rounded-lg p-4">
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
              className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors"
            >
              <ExternalLink size={18} />
              Open
            </button>
          </div>
          {project.aliases.length > 0 && (
            <div>
              <div className="text-sm text-gray-400 mb-2">Aliases</div>
              <div className="flex flex-wrap gap-2">
                {project.aliases.map((alias) => (
                  <span key={alias} className="bg-gray-700 px-3 py-1 rounded text-sm font-mono">
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
      <div className="bg-gray-800 rounded-lg p-4">
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
          </div>
        ) : (
          <div className="text-gray-500">No database configured</div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <button
            onClick={handleMigrate}
            disabled={project.status !== 'running'}
            className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-white p-3 rounded-lg flex flex-col items-center gap-2 transition-colors"
          >
            <PlayCircle size={24} className="text-green-400" />
            <span className="text-sm font-medium">Migrate</span>
          </button>
          <button
            onClick={handleCollectstatic}
            disabled={project.status !== 'running'}
            className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-white p-3 rounded-lg flex flex-col items-center gap-2 transition-colors"
          >
            <ExternalLink size={24} className="text-blue-400" />
            <span className="text-sm font-medium">Collectstatic</span>
          </button>
          <button
            onClick={handleOpenShell}
            disabled={project.status !== 'running'}
            className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-white p-3 rounded-lg flex flex-col items-center gap-2 transition-colors"
          >
            <Terminal size={24} className="text-purple-400" />
            <span className="text-sm font-medium">Shell</span>
          </button>
          <button
            onClick={handleOpenVSCode}
            className="bg-gray-700 hover:bg-gray-600 text-white p-3 rounded-lg flex flex-col items-center gap-2 transition-colors"
          >
            <Code size={24} className="text-brand-400" />
            <span className="text-sm font-medium">VS Code</span>
          </button>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="bg-red-900/20 border border-red-800 rounded-lg p-4">
        <h3 className="text-lg font-semibold text-red-400 mb-4">Danger Zone</h3>
        <button
          onClick={onDelete}
          className="bg-red-700 hover:bg-red-600 text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors"
        >
          <Trash2 size={18} />
          Delete Project
        </button>
      </div>
    </div>
  );
}
