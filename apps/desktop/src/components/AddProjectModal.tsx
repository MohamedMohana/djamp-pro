import { useState } from 'react';
import { X, FolderOpen, Plus, Globe, Database, Check } from 'lucide-react';
import { open as openDialog } from '@tauri-apps/plugin-dialog';
import { api } from '../services/api';

interface AddProjectModalProps {
  onClose: () => void;
  onAdd: () => void;
}

function isLocalDomain(value: string): boolean {
  const domain = value.trim().toLowerCase();
  if (!domain) return true;
  if (domain === 'localhost' || domain === '127.0.0.1') return true;
  return domain.endsWith('.test') || domain.endsWith('.localhost');
}

export default function AddProjectModal({ onClose, onAdd }: AddProjectModalProps) {
  const [step, setStep] = useState<'path' | 'details' | 'database'>('path');
  const [loading, setLoading] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [hasDetected, setHasDetected] = useState(false);

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
    runtimeMode: 'uv',
    condaEnv: '',
    customInterpreter: '',
    domainMode: 'local_only',
  });

  const withTimeout = async <T,>(promise: Promise<T>, ms: number, timeoutMessage: string): Promise<T> => {
    return await Promise.race([
      promise,
      new Promise<T>((_, reject) =>
        setTimeout(() => reject(new Error(timeoutMessage)), ms),
      ),
    ]);
  };

  const handlePathSelect = async () => {
    const normalizedPath = projectPath.trim();
    if (!normalizedPath) return;

    setLoading(true);
    setSubmitError('');
    setHasDetected(false);
    try {
      const result = await withTimeout(
        api.detectDjangoProject(normalizedPath),
        12000,
        'Project detection timed out. Ensure DJAMP controller is running, then retry.',
      );
      setDetectionResult(result);
      setHasDetected(true);
      if (result.found && result.settingsModules && result.settingsModules.length > 0) {
        const inferredName = normalizedPath.split('/').pop() || normalizedPath.split('\\').pop() || 'My Django Project';
        setFormData((prev) => ({
          ...prev,
          settingsModule: result.settingsModules![0],
          name: inferredName,
          domain: `${inferredName.toLowerCase().replace(/[^a-z0-9]/g, '')}.test`,
          domainMode: 'local_only',
        }));
      }
    } catch (error) {
      console.error('Detection failed:', error);
      setDetectionResult({ found: false });
      setHasDetected(true);
      const message = error instanceof Error ? error.message : 'Detection failed.';
      setSubmitError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleBrowseDirectory = async () => {
    setSubmitError('');
    try {
      const selected = await openDialog({
        directory: true,
        multiple: false,
        title: 'Select Django Project Directory',
      });

      if (typeof selected === 'string' && selected.trim()) {
        setProjectPath(selected.trim());
        setHasDetected(false);
      }
    } catch (error) {
      console.error('Folder picker failed:', error);
      const message = error instanceof Error ? error.message : 'Could not open folder picker.';
      setSubmitError(message);
    }
  };

  const handleBack = () => {
    if (step === 'database') {
      setStep('details');
      return;
    }
    setStep('path');
  };

  const handleSubmit = async () => {
    setLoading(true);
    setSubmitError('');
    try {
      if (formData.runtimeMode === 'conda' && !formData.condaEnv.trim()) {
        throw new Error('Conda environment is required when runtime mode is set to Conda.');
      }

      const normalizedDomain = formData.domain.trim();
      const hasPublicDomain = !isLocalDomain(normalizedDomain);
      let domainMode = formData.domainMode as 'local_only' | 'public_override';

      if (hasPublicDomain) {
        domainMode = 'public_override';
        // MAMP-like behavior: if user chose a public-looking domain, auto-enable override guardrail.
        const settings = await api.getSettings();
        if (!settings.anyDomainOverrideEnabled) {
          await api.updateSettings({ anyDomainOverrideEnabled: true });
        }
      }

      const dbPort = formData.databaseType === 'postgres' ? 54329 : formData.databaseType === 'mysql' ? 33069 : 0;
      await api.addProject({
        ...formData,
        domain: normalizedDomain,
        path: projectPath,
        settingsModule: formData.settingsModule,
        aliases: formData.aliases
          .split(',')
          .map((a) => a.trim())
          .filter(Boolean),
        port: formData.port,
        pythonVersion: formData.pythonVersion,
        venvPath: `${projectPath}/.venv`,
        debug: formData.debug,
        allowedHosts: [
          normalizedDomain,
          `www.${normalizedDomain}`,
          ...formData.aliases
            .split(',')
            .map((a) => a.trim())
            .filter(Boolean),
        ],
        httpsEnabled: formData.httpsEnabled,
        certificatePath: '',
        staticPath: formData.staticPath,
        mediaPath: formData.mediaPath,
        database: {
          type: formData.databaseType as 'postgres' | 'mysql' | 'none',
          port: dbPort,
          // DJAMP will hydrate credentials from the project's .env on add/start.
          name: '',
          username: '',
          password: '',
        },
        cache: { type: 'none', port: 6389 },
        environmentVars: {},
        runtimeMode: formData.runtimeMode as 'uv' | 'conda' | 'system' | 'custom',
        condaEnv: formData.condaEnv,
        customInterpreter: formData.customInterpreter,
        domainMode,
      });
      onAdd();
      onClose();
    } catch (error) {
      console.error('Failed to add project:', error);
      const message = error instanceof Error ? error.message : String(error);
      setSubmitError(message);
      alert(`Failed to add project: ${message}`);
      setLoading(false);
    }
  };

  const steps = [
    { id: 'path', title: 'Project Path', icon: FolderOpen },
    { id: 'details', title: 'Project Details', icon: Globe },
    { id: 'database', title: 'Database', icon: Database },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-hidden bg-black/60 p-4 sm:items-center">
      <div className="my-4 flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl bg-gray-800 sm:my-0 sm:max-h-[90vh]">
        <div className="p-6 border-b border-gray-700 flex items-center justify-between">
          <h2 className="text-2xl font-bold">Add Django Project</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X size={24} />
          </button>
        </div>

        <div className="p-6 border-b border-gray-700">
          <div className="flex items-center justify-between">
            {steps.map((s, i) => (
              <div key={s.id} className="flex items-center gap-2">
                <div className={`flex items-center gap-2 ${step === s.id ? 'text-brand-400' : 'text-gray-500'}`}>
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      step === s.id ? 'bg-brand-600' : 'bg-gray-700'
                    }`}
                  >
                    {step === s.id ? <Check size={18} /> : <s.icon size={18} />}
                  </div>
                  <span className="font-medium">{s.title}</span>
                </div>
                {i < steps.length - 1 && (
                  <div
                    className={`w-12 h-0.5 ${
                      i < steps.findIndex((st) => st.id === step) ? 'bg-brand-600' : 'bg-gray-700'
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="modal-scroll min-h-0 flex-1 overflow-y-auto overscroll-y-contain p-6 pr-4">
          {step === 'path' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Project Directory Path</label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={projectPath}
                    onChange={(e) => { setProjectPath(e.target.value); setHasDetected(false); }}
                    placeholder="/Users/dev/projects/my-django-app"
                    className="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                  />
                  <button
                    type="button"
                    onClick={handleBrowseDirectory}
                    disabled={loading}
                    className="shrink-0 rounded-lg border border-gray-600 bg-gray-700 px-4 py-3 text-white transition-colors hover:bg-gray-600 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <span className="flex items-center gap-2">
                      <FolderOpen size={18} />
                      Browse
                    </span>
                  </button>
                </div>
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
              ) : hasDetected && !loading && detectionResult.found === false && projectPath ? (
                <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-400">
                  No Django project found in this directory
                </div>
              ) : null}
            </div>
          )}

          {step === 'details' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Project Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Primary Domain (.test recommended)</label>
                <input
                  type="text"
                  value={formData.domain}
                  onChange={(e) => {
                    const value = e.target.value;
                    setFormData((prev) => ({
                      ...prev,
                      domain: value,
                      domainMode: isLocalDomain(value) ? 'local_only' : 'public_override',
                    }));
                  }}
                  placeholder="myapp.test"
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Domain Aliases (comma-separated)</label>
                <input
                  type="text"
                  value={formData.aliases}
                  onChange={(e) => setFormData({ ...formData, aliases: e.target.value })}
                  placeholder="api.myapp.test, admin.myapp.test"
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Port</label>
                <input
                  type="number"
                  value={formData.port}
                  onChange={(e) => setFormData({ ...formData, port: parseInt(e.target.value, 10) })}
                  min="8000"
                  max="9999"
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Runtime Mode</label>
                <select
                  value={formData.runtimeMode}
                  onChange={(e) => setFormData({ ...formData, runtimeMode: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-500"
                >
                  <option value="uv">uv (recommended)</option>
                  <option value="conda">Conda environment</option>
                  <option value="system">System Python</option>
                  <option value="custom">Custom interpreter command</option>
                </select>
              </div>
              {formData.runtimeMode === 'conda' && (
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">Conda Environment</label>
                  <input
                    type="text"
                    value={formData.condaEnv}
                    onChange={(e) => setFormData({ ...formData, condaEnv: e.target.value })}
                    placeholder="blockchain"
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                  />
                </div>
              )}
              {(formData.runtimeMode === 'system' || formData.runtimeMode === 'custom') && (
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Interpreter (optional for system, required for custom)
                  </label>
                  <input
                    type="text"
                    value={formData.customInterpreter}
                    onChange={(e) => setFormData({ ...formData, customInterpreter: e.target.value })}
                    placeholder={formData.runtimeMode === 'custom' ? 'python /path/to/python' : 'python3'}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                  />
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Domain Mode</label>
                <select
                  value={formData.domainMode}
                  onChange={(e) => setFormData({ ...formData, domainMode: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-500"
                >
                  <option value="local_only">Local domains only (.test recommended)</option>
                  <option value="public_override">Public-domain override (advanced/risky)</option>
                </select>
              </div>
              {!isLocalDomain(formData.domain) && (
                <div className="rounded-lg border border-yellow-700 bg-yellow-900/20 p-3 text-sm text-yellow-300">
                  Public domain detected. DJAMP will enable public-domain override automatically during create.
                </div>
              )}
              {formData.domainMode === 'public_override' && (
                <div className="rounded-lg border border-yellow-700 bg-yellow-900/20 p-3 text-sm text-yellow-300">
                  Public-domain overrides can break normal browsing for that domain until removed and may be blocked by browser HSTS/policy.
                </div>
              )}
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
                <label className="block text-sm font-medium text-gray-400 mb-2">Database Type</label>
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
                <div className="rounded-lg border border-gray-700 bg-gray-900 p-4 text-sm text-gray-300">
                  DJAMP reads database credentials from your project&apos;s <code>.env</code> (for example:
                  <code className="ml-2">DB_NAME</code>, <code>DB_USER</code>, <code>DB_PASSWORD</code> or{' '}
                  <code>DATABASE_URL</code>). If the database/user does not exist, DJAMP will create them automatically.
                  <div className="mt-2 text-gray-400">
                    DJAMP will override <code>DB_HOST</code> and <code>DB_PORT</code> to point to the local managed
                    database (via a DJAMP-managed block appended to <code>.env</code>).
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="p-6 border-t border-gray-700 space-y-3">
          {submitError && (
            <div className="rounded-lg border border-red-800 bg-red-900/20 px-3 py-2 text-sm text-red-300">
              {submitError}
            </div>
          )}
          <div className="flex items-center justify-between">
            {step !== 'path' ? (
              <button
                onClick={handleBack}
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
                disabled={loading || !detectionResult.found}
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
    </div>
  );
}
