import { useState } from 'react';
import { X, FolderOpen, Plus, Globe, Database, Check } from 'lucide-react';
import { open as openDialog } from '@tauri-apps/plugin-dialog';
import { useI18n } from '../i18n';
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
  const { t } = useI18n();
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
      new Promise<T>((_, reject) => setTimeout(() => reject(new Error(timeoutMessage)), ms)),
    ]);
  };

  const handlePathSelect = async () => {
    const normalizedPath = projectPath.trim();
    if (!normalizedPath) {
      return;
    }

    setLoading(true);
    setSubmitError('');
    setHasDetected(false);
    try {
      const result = await withTimeout(
        api.detectDjangoProject(normalizedPath),
        12000,
        t.addProject.detectionTimedOut,
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
      const message = error instanceof Error ? error.message : t.addProject.detectionFailed;
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
        title: t.addProject.selectDirectoryTitle,
      });

      if (typeof selected === 'string' && selected.trim()) {
        setProjectPath(selected.trim());
        setHasDetected(false);
      }
    } catch (error) {
      console.error('Folder picker failed:', error);
      const message = error instanceof Error ? error.message : t.addProject.folderPickerFailed;
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
        throw new Error(t.addProject.condaRequired);
      }

      const normalizedDomain = formData.domain.trim();
      const hasPublicDomain = !isLocalDomain(normalizedDomain);
      let domainMode = formData.domainMode as 'local_only' | 'public_override';

      if (hasPublicDomain) {
        domainMode = 'public_override';
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
          .map((alias) => alias.trim())
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
            .map((alias) => alias.trim())
            .filter(Boolean),
        ],
        httpsEnabled: formData.httpsEnabled,
        certificatePath: '',
        staticPath: formData.staticPath,
        mediaPath: formData.mediaPath,
        database: {
          type: formData.databaseType as 'postgres' | 'mysql' | 'none',
          port: dbPort,
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
      alert(t.addProject.failedToAdd(message));
      setLoading(false);
    }
  };

  const steps = [
    { id: 'path', title: t.addProject.steps.path, icon: FolderOpen },
    { id: 'details', title: t.addProject.steps.details, icon: Globe },
    { id: 'database', title: t.addProject.steps.database, icon: Database },
  ] as const;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-hidden bg-black/60 p-4 sm:items-center">
      <div className="my-4 flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl bg-gray-800 sm:my-0 sm:max-h-[90vh]">
        <div className="flex items-center justify-between border-b border-gray-700 p-6">
          <h2 className="text-2xl font-bold">{t.addProject.title}</h2>
          <button onClick={onClose} className="text-gray-400 transition-colors hover:text-white">
            <X size={24} />
          </button>
        </div>

        <div className="border-b border-gray-700 p-6">
          <div className="flex items-center justify-between">
            {steps.map((item, index) => (
              <div key={item.id} className="flex items-center gap-2">
                <div className={`flex items-center gap-2 ${step === item.id ? 'text-brand-400' : 'text-gray-500'}`}>
                  <div
                    className={`flex h-8 w-8 items-center justify-center rounded-full ${
                      step === item.id ? 'bg-brand-600' : 'bg-gray-700'
                    }`}
                  >
                    {step === item.id ? <Check size={18} /> : <item.icon size={18} />}
                  </div>
                  <span className="font-medium">{item.title}</span>
                </div>
                {index < steps.length - 1 && (
                  <div
                    className={`h-0.5 w-12 ${
                      index < steps.findIndex((currentStep) => currentStep.id === step) ? 'bg-brand-600' : 'bg-gray-700'
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="modal-scroll min-h-0 flex-1 overflow-y-auto overscroll-y-contain p-6">
          {step === 'path' && (
            <div className="space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-400">{t.addProject.projectDirectoryPath}</label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={projectPath}
                    onChange={(event) => {
                      setProjectPath(event.target.value);
                      setHasDetected(false);
                    }}
                    placeholder="/Users/dev/projects/my-django-app"
                    className="flex-1 rounded-lg border border-gray-600 bg-gray-700 px-4 py-3 text-white placeholder-gray-500 focus:border-brand-500 focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={handleBrowseDirectory}
                    disabled={loading}
                    className="shrink-0 rounded-lg border border-gray-600 bg-gray-700 px-4 py-3 text-white transition-colors hover:bg-gray-600 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <span className="flex items-center gap-2">
                      <FolderOpen size={18} />
                      {t.addProject.browse}
                    </span>
                  </button>
                </div>
              </div>
              <button
                onClick={handlePathSelect}
                disabled={loading || !projectPath}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 py-3 font-medium text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-gray-700"
              >
                {loading ? t.addProject.detecting : t.addProject.detectProject}
              </button>
              {detectionResult.found ? (
                <div className="rounded-lg border border-green-800 bg-green-900/20 p-4">
                  <div className="mb-2 flex items-center gap-2 text-green-400">
                    <Check size={20} />
                    <span className="font-medium">{t.addProject.projectFound}</span>
                  </div>
                  <div className="text-sm text-gray-300">
                    <div>
                      {t.addProject.managePy}: {detectionResult.managePyPath}
                    </div>
                    <div>
                      {t.addProject.settings}: {detectionResult.settingsModules?.join(', ')}
                    </div>
                  </div>
                </div>
              ) : hasDetected && !loading && detectionResult.found === false && projectPath ? (
                <div className="rounded-lg border border-red-800 bg-red-900/20 p-4 text-red-400">
                  {t.addProject.noProjectFound}
                </div>
              ) : null}
            </div>
          )}

          {step === 'details' && (
            <div className="space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-400">{t.addProject.projectName}</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(event) => setFormData({ ...formData, name: event.target.value })}
                  className="w-full rounded-lg border border-gray-600 bg-gray-700 px-4 py-3 text-white placeholder-gray-500 focus:border-brand-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-400">{t.addProject.primaryDomain}</label>
                <input
                  type="text"
                  value={formData.domain}
                  onChange={(event) => {
                    const value = event.target.value;
                    setFormData((prev) => ({
                      ...prev,
                      domain: value,
                      domainMode: isLocalDomain(value) ? 'local_only' : 'public_override',
                    }));
                  }}
                  placeholder="myapp.test"
                  className="w-full rounded-lg border border-gray-600 bg-gray-700 px-4 py-3 text-white placeholder-gray-500 focus:border-brand-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-400">{t.addProject.domainAliases}</label>
                <input
                  type="text"
                  value={formData.aliases}
                  onChange={(event) => setFormData({ ...formData, aliases: event.target.value })}
                  placeholder="api.myapp.test, admin.myapp.test"
                  className="w-full rounded-lg border border-gray-600 bg-gray-700 px-4 py-3 text-white placeholder-gray-500 focus:border-brand-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-400">{t.addProject.port}</label>
                <input
                  type="number"
                  value={formData.port}
                  onChange={(event) => setFormData({ ...formData, port: parseInt(event.target.value, 10) })}
                  min="8000"
                  max="9999"
                  className="w-full rounded-lg border border-gray-600 bg-gray-700 px-4 py-3 text-white placeholder-gray-500 focus:border-brand-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-400">{t.addProject.runtimeMode}</label>
                <select
                  value={formData.runtimeMode}
                  onChange={(event) => setFormData({ ...formData, runtimeMode: event.target.value })}
                  className="w-full rounded-lg border border-gray-600 bg-gray-700 px-4 py-3 text-white focus:border-brand-500 focus:outline-none"
                >
                  <option value="uv">{t.addProject.runtimeOptions.uv}</option>
                  <option value="conda">{t.addProject.runtimeOptions.conda}</option>
                  <option value="system">{t.addProject.runtimeOptions.system}</option>
                  <option value="custom">{t.addProject.runtimeOptions.custom}</option>
                </select>
              </div>
              {formData.runtimeMode === 'conda' && (
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-400">{t.addProject.condaEnvironment}</label>
                  <input
                    type="text"
                    value={formData.condaEnv}
                    onChange={(event) => setFormData({ ...formData, condaEnv: event.target.value })}
                    placeholder="blockchain"
                    className="w-full rounded-lg border border-gray-600 bg-gray-700 px-4 py-3 text-white placeholder-gray-500 focus:border-brand-500 focus:outline-none"
                  />
                </div>
              )}
              {(formData.runtimeMode === 'system' || formData.runtimeMode === 'custom') && (
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-400">{t.addProject.interpreter}</label>
                  <input
                    type="text"
                    value={formData.customInterpreter}
                    onChange={(event) => setFormData({ ...formData, customInterpreter: event.target.value })}
                    placeholder={formData.runtimeMode === 'custom' ? 'python /path/to/python' : 'python3'}
                    className="w-full rounded-lg border border-gray-600 bg-gray-700 px-4 py-3 text-white placeholder-gray-500 focus:border-brand-500 focus:outline-none"
                  />
                </div>
              )}
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-400">{t.addProject.domainMode}</label>
                <select
                  value={formData.domainMode}
                  onChange={(event) => setFormData({ ...formData, domainMode: event.target.value })}
                  className="w-full rounded-lg border border-gray-600 bg-gray-700 px-4 py-3 text-white focus:border-brand-500 focus:outline-none"
                >
                  <option value="local_only">{t.addProject.domainModes.local_only}</option>
                  <option value="public_override">{t.addProject.domainModes.public_override}</option>
                </select>
              </div>
              {!isLocalDomain(formData.domain) && (
                <div className="rounded-lg border border-yellow-700 bg-yellow-900/20 p-3 text-sm text-yellow-300">
                  {t.addProject.publicDomainDetected}
                </div>
              )}
              {formData.domainMode === 'public_override' && (
                <div className="rounded-lg border border-yellow-700 bg-yellow-900/20 p-3 text-sm text-yellow-300">
                  {t.addProject.publicDomainWarning}
                </div>
              )}
              <div className="grid grid-cols-2 gap-4">
                <label className="flex cursor-pointer items-center gap-3 rounded-lg bg-gray-700 p-3">
                  <input
                    type="checkbox"
                    checked={formData.debug}
                    onChange={(event) => setFormData({ ...formData, debug: event.target.checked })}
                    className="h-5 w-5 rounded border-gray-500 bg-gray-600 text-brand-600 focus:ring-brand-500"
                  />
                  <span className="font-medium">{t.addProject.debugMode}</span>
                </label>
                <label className="flex cursor-pointer items-center gap-3 rounded-lg bg-gray-700 p-3">
                  <input
                    type="checkbox"
                    checked={formData.httpsEnabled}
                    onChange={(event) => setFormData({ ...formData, httpsEnabled: event.target.checked })}
                    className="h-5 w-5 rounded border-gray-500 bg-gray-600 text-brand-600 focus:ring-brand-500"
                  />
                  <span className="font-medium">{t.addProject.enableHttps}</span>
                </label>
              </div>
            </div>
          )}

          {step === 'database' && (
            <div className="space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-400">{t.addProject.databaseType}</label>
                <select
                  value={formData.databaseType}
                  onChange={(event) => setFormData({ ...formData, databaseType: event.target.value })}
                  className="w-full rounded-lg border border-gray-600 bg-gray-700 px-4 py-3 text-white focus:border-brand-500 focus:outline-none"
                >
                  <option value="postgres">{t.addProject.databaseOptions.postgres}</option>
                  <option value="mysql">{t.addProject.databaseOptions.mysql}</option>
                  <option value="none">{t.addProject.databaseOptions.none}</option>
                </select>
              </div>
              {formData.databaseType !== 'none' && (
                <div className="rounded-lg border border-gray-700 bg-gray-900 p-4 text-sm text-gray-300">
                  <p>{t.addProject.databaseHelp}</p>
                  <div className="mt-2 text-gray-400">{t.addProject.databaseHelpNote}</div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="space-y-3 border-t border-gray-700 p-6">
          {submitError && (
            <div className="rounded-lg border border-red-800 bg-red-900/20 px-3 py-2 text-sm text-red-300">
              {submitError}
            </div>
          )}
          <div className="flex items-center justify-between">
            {step !== 'path' ? (
              <button
                onClick={handleBack}
                className="rounded-lg bg-gray-700 px-6 py-2 font-medium text-white transition-colors hover:bg-gray-600"
              >
                {t.common.back}
              </button>
            ) : (
              <button
                onClick={onClose}
                className="rounded-lg bg-gray-700 px-6 py-2 font-medium text-white transition-colors hover:bg-gray-600"
              >
                {t.common.cancel}
              </button>
            )}
            {step === 'path' ? (
              <button
                onClick={() => setStep('details')}
                disabled={loading || !detectionResult.found}
                className="rounded-lg bg-brand-600 px-6 py-2 font-medium text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-gray-700"
              >
                {t.common.next}
              </button>
            ) : step === 'details' ? (
              <button
                onClick={() => setStep('database')}
                className="rounded-lg bg-brand-600 px-6 py-2 font-medium text-white transition-colors hover:bg-brand-700"
              >
                {t.common.next}
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={loading}
                className="flex items-center gap-2 rounded-lg bg-green-600 px-6 py-2 font-medium text-white transition-colors hover:bg-green-700 disabled:cursor-not-allowed disabled:bg-gray-700"
              >
                <Plus size={18} />
                {loading ? t.addProject.creating : t.addProject.createProject}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
