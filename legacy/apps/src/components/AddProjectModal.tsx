import { useState } from 'react';
import { X, FolderOpen, Plus, Globe, Database, Check } from 'lucide-react';
import { api } from '../services/api';
import { Project } from '../types';

interface AddProjectModalProps {
  onClose: () => void;
  onAdd: () => void;
}

export default function AddProjectModal({ onClose, onAdd }: AddProjectModalProps) {
  const [step, setStep] = useState<'path' | 'details' | 'database'>('path');
  const [loading, setLoading] = useState(false);
  
  const [projectPath, setProjectPath] = useState('');
  const [detectionResult, setDetectionResult] = useState<{
    found: boolean;
    managePyPath?: string;
    settingsModules?: string[];
  }>({ found: false });

  const [formData, setFormData] = useState({
    name: '',
    domain: '',
    aliases: '',
    port: 8001,
    pythonVersion: '3.11',
    debug: true,
    httpsEnabled: true,
    staticPath: 'static',
    mediaPath: 'media',
    settingsModule: '',
    databaseType: 'postgres',
    databaseName: '',
    databaseUsername: '',
    databasePassword: '',
  });

  const handlePathSelect = async () => {
    setLoading(true);
    try {
      const result = await api.detectDjangoProject(projectPath);
      setDetectionResult(result);
      if (result.found && result.settingsModules && result.settingsModules.length > 0) {
        setFormData(prev => ({
          ...prev,
          settingsModule: result.settingsModules![0],
          name: projectPath.split('/').pop() || projectPath.split('\\').pop() || 'My Django Project',
          domain: `${(projectPath.split('/').pop() || '').toLowerCase().replace(/[^a-z0-9]/g, '')}.test`,
          databaseName: `${(projectPath.split('/').pop() || '').toLowerCase().replace(/[^a-z0-9]/g, '')}_db`,
          databaseUsername: `${(projectPath.split('/').pop() || '').toLowerCase().replace(/[^a-z0-9]/g, '')}_user`,
        }));
      }
      setLoading(false);
    } catch (error) {
      console.error('Detection failed:', error);
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      await api.addProject({
        ...formData,
        path: projectPath,
        settingsModule: formData.settingsModule,
        aliases: formData.aliases.split(',').map(a => a.trim()).filter(Boolean),
        port: formData.port,
        pythonVersion: formData.pythonVersion,
        venvPath: `${projectPath}/.venv`,
        debug: formData.debug,
        allowedHosts: [formData.domain, ...formData.aliases.split(',').map(a => a.trim()).filter(Boolean)],
        httpsEnabled: formData.httpsEnabled,
        certificatePath: '',
        staticPath: formData.staticPath,
        mediaPath: formData.mediaPath,
        database: {
          type: formData.databaseType as 'postgres' | 'mysql' | 'none',
          port: formData.databaseType === 'postgres' ? 5432 : 3306,
          name: formData.databaseName,
          username: formData.databaseUsername,
          password: formData.databasePassword,
        },
        cache: { type: 'none', port: 6379 },
        status: 'stopped',
        environmentVars: {
          DEBUG: formData.debug.toString(),
          SECRET_KEY: 'change-me-in-production',
          DATABASE_URL: `${formData.databaseType}://${formData.databaseUsername}:${formData.databasePassword}@localhost:${formData.databaseType === 'postgres' ? 5432 : 3306}/${formData.databaseName}`,
        },
      });
      onAdd();
      onClose();
    } catch (error) {
      console.error('Failed to add project:', error);
      setLoading(false);
    }
  };

  const steps = [
    { id: 'path', title: 'Project Path', icon: FolderOpen },
    { id: 'details', title: 'Project Details', icon: Globe },
    { id: 'database', title: 'Database', icon: Database },
  ];

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b border-gray-700 flex items-center justify-between">
          <h2 className="text-2xl font-bold">Add Django Project</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X size={24} />
          </button>
        </div>

        {/* Steps */}
        <div className="p-6 border-b border-gray-700">
          <div className="flex items-center justify-between">
            {steps.map((s, i) => (
              <div key={s.id} className="flex items-center gap-2">
                <div className={`flex items-center gap-2 ${step === s.id ? 'text-brand-400' : 'text-gray-500'}`}>
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${step === s.id ? 'bg-brand-600' : 'bg-gray-700'}`}>
                    {step === s.id ? <Check size={18} /> : <s.icon size={18} />}
                  </div>
                  <span className="font-medium">{s.title}</span>
                </div>
                {i < steps.length - 1 && <div className={`w-12 h-0.5 ${i < steps.findIndex(st => st.id === step) ? 'bg-brand-600' : 'bg-gray-700'}`} />}
              </div>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto">
          {step === 'path' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Project Directory Path
                </label>
                <input
                  type="text"
                  value={projectPath}
                  onChange={(e) => setProjectPath(e.target.value)}
                  placeholder="/Users/dev/projects/my-django-app"
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                />
              </div>
              <button
                onClick={handlePathSelect}
                disabled={loading || !projectPath}
                className="w-full bg-brand-600 hover:bg-brand-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-medium py-3 rounded-lg flex items-center justify-center gap-2 transition-colors"
              >
                {loading ? 'Detecting...' : 'Detect Django Project'}
              </button>
              {detectionResult.found ? (
                <div className="bg-green-900/20 border border-green-800 rounded-lg p-4">
                  <div className="flex items-center gap-2 text-green-400 mb-2">
                    <Check size={20} />
                    <span className="font-medium">Django Project Found!</span>
                  </div>
                  <div className="text-sm text-gray-300">
                    <div>manage.py: {detectionResult.managePyPath}</div>
                    <div>Settings: {detectionResult.settingsModules?.join(', ')}</div>
                  </div>
                </div>
              ) : detectionResult.found === false && projectPath ? (
                <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-400">
                  No Django project found in this directory
                </div>
              ) : null}
            </div>
          )}

          {step === 'details' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Project Name
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Primary Domain (.test recommended)
                </label>
                <input
                  type="text"
                  value={formData.domain}
                  onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
                  placeholder="myapp.test"
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Domain Aliases (comma-separated)
                </label>
                <input
                  type="text"
                  value={formData.aliases}
                  onChange={(e) => setFormData({ ...formData, aliases: e.target.value })}
                  placeholder="api.myapp.test, admin.myapp.test"
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Port
                </label>
                <input
                  type="number"
                  value={formData.port}
                  onChange={(e) => setFormData({ ...formData, port: parseInt(e.target.value) })}
                  min="8000"
                  max="9999"
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <label className="flex items-center gap-3 bg-gray-700 rounded-lg p-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.debug}
                    onChange={(e) => setFormData({ ...formData, debug: e.target.checked })}
                    className="w-5 h-5 rounded bg-gray-600 border-gray-500 text-brand-600 focus:ring-brand-500"
                  />
                  <span className="font-medium">Debug Mode</span>
                </label>
                <label className="flex items-center gap-3 bg-gray-700 rounded-lg p-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.httpsEnabled}
                    onChange={(e) => setFormData({ ...formData, httpsEnabled: e.target.checked })}
                    className="w-5 h-5 rounded bg-gray-600 border-gray-500 text-brand-600 focus:ring-brand-500"
                  />
                  <span className="font-medium">Enable HTTPS</span>
                </label>
              </div>
            </div>
          )}

          {step === 'database' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Database Type
                </label>
                <select
                  value={formData.databaseType}
                  onChange={(e) => setFormData({ ...formData, databaseType: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-500"
                >
                  <option value="postgres">PostgreSQL</option>
                  <option value="mysql">MySQL</option>
                  <option value="none">None (Use SQLite or external)</option>
                </select>
              </div>
              {formData.databaseType !== 'none' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Database Name
                    </label>
                    <input
                      type="text"
                      value={formData.databaseName}
                      onChange={(e) => setFormData({ ...formData, databaseName: e.target.value })}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Username
                    </label>
                    <input
                      type="text"
                      value={formData.databaseUsername}
                      onChange={(e) => setFormData({ ...formData, databaseUsername: e.target.value })}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Password
                    </label>
                    <input
                      type="password"
                      value={formData.databasePassword}
                      onChange={(e) => setFormData({ ...formData, databasePassword: e.target.value })}
                      className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                    />
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-700 flex items-center justify-between">
          {step !== 'path' ? (
            <button
              onClick={() => setStep('path')}
              className="px-6 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white font-medium transition-colors"
            >
              Back
            </button>
          ) : (
            <button
              onClick={onClose}
              className="px-6 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white font-medium transition-colors"
            >
              Cancel
            </button>
          )}
          {step === 'path' ? (
            <button
              onClick={() => setStep('details')}
              disabled={!detectionResult.found}
              className="px-6 py-2 rounded-lg bg-brand-600 hover:bg-brand-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-medium transition-colors"
            >
              Next
            </button>
          ) : step === 'details' ? (
            <button
              onClick={() => setStep('database')}
              className="px-6 py-2 rounded-lg bg-brand-600 hover:bg-brand-700 text-white font-medium transition-colors"
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="px-6 py-2 rounded-lg bg-green-600 hover:bg-green-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-medium transition-colors flex items-center gap-2"
            >
              <Plus size={18} />
              {loading ? 'Creating...' : 'Create Project'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
