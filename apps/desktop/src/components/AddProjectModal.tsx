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

  const activeStep = steps.find((item) => item.id === step);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 p-4 backdrop-blur-sm sm:items-center">
      <div className="mamp-modal my-4 flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden sm:my-0 sm:max-h-[90vh]">
        <div className="mamp-modal-header flex items-center justify-between px-6 py-5">
          <div>
            <h2 className="text-2xl font-semibold text-white">{t.addProject.title}</h2>
            <p className="mt-1 text-sm text-[var(--mamp-text-muted)]">{activeStep?.title}</p>
          </div>
          <button
            onClick={onClose}
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-white/8 bg-white/5 text-[var(--mamp-text-muted)] transition hover:bg-white/10 hover:text-white"
          >
            <X size={20} />
          </button>
        </div>

        <div className="border-b border-white/8 px-6 py-4">
          <div className="flex flex-wrap items-center gap-3">
            {steps.map((item, index) => (
              <div key={item.id} className="flex items-center gap-3">
                <div className={`mamp-step ${step === item.id ? 'mamp-step-active' : ''}`}>
                  <div className="mamp-step-badge">
                    {step === item.id ? <Check size={16} /> : <item.icon size={16} />}
                  </div>
                  <span className="text-sm font-semibold">{item.title}</span>
                </div>
                {index < steps.length - 1 && <div className="mamp-step-line" />}
              </div>
            ))}
          </div>
        </div>

        <div className="modal-scroll min-h-0 flex-1 overflow-y-auto overscroll-y-contain px-6 py-5">
          {step === 'path' && (
            <div className="space-y-5">
              <section className="mamp-section">
                <div className="mamp-section-title">{t.addProject.steps.path}</div>
                <div className="space-y-4">
                  <div>
                    <label className="mamp-field-label">{t.addProject.projectDirectoryPath}</label>
                    <div className="flex flex-col gap-3 md:flex-row">
                      <input
                        type="text"
                        value={projectPath}
                        onChange={(event) => {
                          setProjectPath(event.target.value);
                          setHasDetected(false);
                        }}
                        placeholder="/Users/dev/projects/my-django-app"
                        className="mamp-input flex-1"
                      />
                      <button
                        type="button"
                        onClick={handleBrowseDirectory}
                        disabled={loading}
                        className="mamp-button-neutral shrink-0"
                      >
                        <FolderOpen size={17} />
                        {t.addProject.browse}
                      </button>
                    </div>
                  </div>

                  <button
                    onClick={handlePathSelect}
                    disabled={loading || !projectPath}
                    className="mamp-button-primary w-full"
                  >
                    {loading ? t.addProject.detecting : t.addProject.detectProject}
                  </button>
                </div>
              </section>

              {detectionResult.found ? (
                <div className="mamp-note mamp-note-success">
                  <div className="mb-2 flex items-center gap-2 font-semibold">
                    <Check size={18} />
                    {t.addProject.projectFound}
                  </div>
                  <div className="space-y-1 text-sm">
                    <div>
                      {t.addProject.managePy}: <span className="font-mono">{detectionResult.managePyPath}</span>
                    </div>
                    <div>
                      {t.addProject.settings}: <span className="font-mono">{detectionResult.settingsModules?.join(', ')}</span>
                    </div>
                  </div>
                </div>
              ) : hasDetected && !loading && detectionResult.found === false && projectPath ? (
                <div className="mamp-note mamp-note-danger">{t.addProject.noProjectFound}</div>
              ) : null}
            </div>
          )}

          {step === 'details' && (
            <div className="space-y-5">
              <section className="mamp-section">
                <div className="mamp-section-title">{t.addProject.steps.details}</div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="md:col-span-2">
                    <label className="mamp-field-label">{t.addProject.projectName}</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(event) => setFormData({ ...formData, name: event.target.value })}
                      className="mamp-input"
                    />
                  </div>

                  <div>
                    <label className="mamp-field-label">{t.addProject.primaryDomain}</label>
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
                      className="mamp-input"
                    />
                  </div>

                  <div>
                    <label className="mamp-field-label">{t.addProject.domainAliases}</label>
                    <input
                      type="text"
                      value={formData.aliases}
                      onChange={(event) => setFormData({ ...formData, aliases: event.target.value })}
                      placeholder="api.myapp.test, admin.myapp.test"
                      className="mamp-input"
                    />
                  </div>

                  <div>
                    <label className="mamp-field-label">{t.addProject.port}</label>
                    <input
                      type="number"
                      value={formData.port}
                      onChange={(event) => setFormData({ ...formData, port: parseInt(event.target.value, 10) })}
                      min="8000"
                      max="9999"
                      className="mamp-input"
                    />
                  </div>

                  <div>
                    <label className="mamp-field-label">{t.addProject.runtimeMode}</label>
                    <select
                      value={formData.runtimeMode}
                      onChange={(event) => setFormData({ ...formData, runtimeMode: event.target.value })}
                      className="mamp-select"
                    >
                      <option value="uv">{t.addProject.runtimeOptions.uv}</option>
                      <option value="conda">{t.addProject.runtimeOptions.conda}</option>
                      <option value="system">{t.addProject.runtimeOptions.system}</option>
                      <option value="custom">{t.addProject.runtimeOptions.custom}</option>
                    </select>
                  </div>

                  {formData.runtimeMode === 'conda' && (
                    <div className="md:col-span-2">
                      <label className="mamp-field-label">{t.addProject.condaEnvironment}</label>
                      <input
                        type="text"
                        value={formData.condaEnv}
                        onChange={(event) => setFormData({ ...formData, condaEnv: event.target.value })}
                        placeholder="blockchain"
                        className="mamp-input"
                      />
                    </div>
                  )}

                  {(formData.runtimeMode === 'system' || formData.runtimeMode === 'custom') && (
                    <div className="md:col-span-2">
                      <label className="mamp-field-label">{t.addProject.interpreter}</label>
                      <input
                        type="text"
                        value={formData.customInterpreter}
                        onChange={(event) => setFormData({ ...formData, customInterpreter: event.target.value })}
                        placeholder={formData.runtimeMode === 'custom' ? 'python /path/to/python' : 'python3'}
                        className="mamp-input"
                      />
                    </div>
                  )}

                  <div className="md:col-span-2">
                    <label className="mamp-field-label">{t.addProject.domainMode}</label>
                    <select
                      value={formData.domainMode}
                      onChange={(event) => setFormData({ ...formData, domainMode: event.target.value })}
                      className="mamp-select"
                    >
                      <option value="local_only">{t.addProject.domainModes.local_only}</option>
                      <option value="public_override">{t.addProject.domainModes.public_override}</option>
                    </select>
                  </div>
                </div>
              </section>

              {!isLocalDomain(formData.domain) && (
                <div className="mamp-note mamp-note-warning">{t.addProject.publicDomainDetected}</div>
              )}
              {formData.domainMode === 'public_override' && (
                <div className="mamp-note mamp-note-warning">{t.addProject.publicDomainWarning}</div>
              )}

              <section className="mamp-section">
                <div className="mamp-section-title">{t.addProject.steps.details}</div>
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="mamp-check-card cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.debug}
                      onChange={(event) => setFormData({ ...formData, debug: event.target.checked })}
                      className="h-5 w-5 rounded border-gray-500 bg-gray-600 text-brand-600 focus:ring-brand-500"
                    />
                    <span className="font-semibold text-[var(--mamp-text)]">{t.addProject.debugMode}</span>
                  </label>
                  <label className="mamp-check-card cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.httpsEnabled}
                      onChange={(event) => setFormData({ ...formData, httpsEnabled: event.target.checked })}
                      className="h-5 w-5 rounded border-gray-500 bg-gray-600 text-brand-600 focus:ring-brand-500"
                    />
                    <span className="font-semibold text-[var(--mamp-text)]">{t.addProject.enableHttps}</span>
                  </label>
                </div>
              </section>
            </div>
          )}

          {step === 'database' && (
            <div className="space-y-5">
              <section className="mamp-section">
                <div className="mamp-section-title">{t.addProject.steps.database}</div>
                <div className="space-y-4">
                  <div>
                    <label className="mamp-field-label">{t.addProject.databaseType}</label>
                    <select
                      value={formData.databaseType}
                      onChange={(event) => setFormData({ ...formData, databaseType: event.target.value })}
                      className="mamp-select"
                    >
                      <option value="postgres">{t.addProject.databaseOptions.postgres}</option>
                      <option value="mysql">{t.addProject.databaseOptions.mysql}</option>
                      <option value="none">{t.addProject.databaseOptions.none}</option>
                    </select>
                  </div>

                  {formData.databaseType !== 'none' && (
                    <div className="mamp-note border-white/8 bg-black/14 text-[var(--mamp-text)]">
                      <p>{t.addProject.databaseHelp}</p>
                      <div className="mt-2 text-sm text-[var(--mamp-text-muted)]">{t.addProject.databaseHelpNote}</div>
                    </div>
                  )}
                </div>
              </section>
            </div>
          )}
        </div>

        <div className="border-t border-white/8 px-6 py-5">
          {submitError && (
            <div className="mamp-note mamp-note-danger mb-4">{submitError}</div>
          )}
          <div className="flex items-center justify-between gap-3">
            {step !== 'path' ? (
              <button onClick={handleBack} className="mamp-button-neutral">
                {t.common.back}
              </button>
            ) : (
              <button onClick={onClose} className="mamp-button-neutral">
                {t.common.cancel}
              </button>
            )}

            {step === 'path' ? (
              <button
                onClick={() => setStep('details')}
                disabled={loading || !detectionResult.found}
                className="mamp-button-primary"
              >
                {t.common.next}
              </button>
            ) : step === 'details' ? (
              <button onClick={() => setStep('database')} className="mamp-button-primary">
                {t.common.next}
              </button>
            ) : (
              <button onClick={handleSubmit} disabled={loading} className="mamp-button-success">
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
