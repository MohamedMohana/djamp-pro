import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { X, Shield, Globe, RefreshCw, Lock } from 'lucide-react';
import { useI18n } from '../i18n';
import { api } from '../services/api';
import type { AppSettings, ProxyStatus, HelperStatus } from '../types';

interface SettingsPanelProps {
  onClose: () => void;
}

function SettingsSection({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof Shield;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="mamp-section">
      <div className="mb-4 flex items-center gap-3">
        <Icon size={20} className="text-[var(--mamp-accent-strong)]" />
        <div className="mamp-section-title mb-0">{title}</div>
      </div>
      {children}
    </section>
  );
}

function ToggleCard({
  title,
  description,
  checked,
  onChange,
}: {
  title: string;
  description: ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4 rounded-xl border border-white/8 bg-black/12 p-4">
      <div>
        <div className="font-semibold text-[var(--mamp-text)]">{title}</div>
        <div className="mt-1 text-sm text-[var(--mamp-text-muted)]">{description}</div>
      </div>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1 h-5 w-5 rounded border-gray-500 bg-gray-600 text-brand-600 focus:ring-brand-500"
      />
    </label>
  );
}

export default function SettingsPanel({ onClose }: SettingsPanelProps) {
  const { t } = useI18n();
  const [caStatus, setCaStatus] = useState<{ installed: boolean; valid: boolean } | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [proxyStatus, setProxyStatus] = useState<ProxyStatus | null>(null);
  const [helperStatus, setHelperStatus] = useState<HelperStatus | null>(null);
  const [busy, setBusy] = useState(false);

  const withTimeout = async <T,>(promise: Promise<T>, ms: number, timeoutMessage: string): Promise<T> => {
    return await Promise.race([
      promise,
      new Promise<T>((_, reject) => setTimeout(() => reject(new Error(timeoutMessage)), ms)),
    ]);
  };

  const loadAll = useCallback(async () => {
    const [ca, currentSettings, proxy, helper] = await Promise.allSettled([
      withTimeout(api.checkRootCAStatus(), 8000, 'CA status request timed out.'),
      withTimeout(api.getSettings(), 8000, 'Settings request timed out.'),
      withTimeout(api.getProxyStatus(), 8000, 'Proxy status request timed out.'),
      withTimeout(api.getHelperStatus(), 8000, 'Helper status request timed out.'),
    ]);

    if (ca.status === 'fulfilled') {
      setCaStatus(ca.value);
    }
    if (currentSettings.status === 'fulfilled') {
      setSettings(currentSettings.value);
    }
    if (proxy.status === 'fulfilled') {
      setProxyStatus(proxy.value);
    }
    if (helper.status === 'fulfilled') {
      setHelperStatus(helper.value);
    }

    if ([ca, currentSettings, proxy, helper].some((result) => result.status === 'rejected')) {
      console.error('Failed to load one or more settings sections', { ca, currentSettings, proxy, helper });
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data fetch on mount
    void loadAll();
  }, [loadAll]);

  const handleInstallCA = async () => {
    if (!confirm(t.settingsPanel.confirmInstallRootCa)) {
      return;
    }
    setBusy(true);
    try {
      await withTimeout(api.installRootCA(), 120000, 'Install Root CA timed out.');
      await loadAll();
    } catch (error) {
      console.error('Failed to install CA:', error);
      alert(t.settingsPanel.installRootCaError);
    }
    setBusy(false);
  };

  const handleUninstallCA = async () => {
    if (!confirm(t.settingsPanel.confirmUninstallRootCa)) {
      return;
    }
    setBusy(true);
    try {
      const result = await withTimeout(api.uninstallRootCA(), 30000, 'Uninstall Root CA timed out.');
      if (!result.success) {
        alert(result.error || result.output || t.settingsPanel.uninstallRootCaError);
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to uninstall CA:', error);
      alert(t.settingsPanel.uninstallRootCaError);
    }
    setBusy(false);
  };

  const handleReloadProxy = async () => {
    setBusy(true);
    try {
      const result = await withTimeout(api.reloadProxy(), 30000, 'Proxy reload timed out.');
      if (!result.success) {
        alert(result.error || result.output || t.settingsPanel.proxyReloadError);
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to reload proxy:', error);
      alert(t.settingsPanel.proxyReloadError);
    }
    setBusy(false);
  };

  const handleSyncHosts = async () => {
    setBusy(true);
    try {
      const result = await withTimeout(api.syncHosts(), 30000, 'Hosts sync timed out.');
      if (!result.success) {
        alert(result.error || result.output || t.settingsPanel.hostsSyncError);
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to sync hosts:', error);
      alert(t.settingsPanel.hostsSyncError);
    }
    setBusy(false);
  };

  const handleClearHosts = async () => {
    if (!confirm(t.settingsPanel.confirmClearHosts)) {
      return;
    }
    setBusy(true);
    try {
      const result = await withTimeout(api.clearHosts(), 30000, 'Hosts clear timed out.');
      if (!result.success) {
        alert(result.error || result.output || t.settingsPanel.hostsClearError);
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to clear hosts:', error);
      alert(t.settingsPanel.hostsClearError);
    }
    setBusy(false);
  };

  const handleDisableStandardPorts = async () => {
    if (!confirm(t.settingsPanel.confirmDisableStandardPorts)) {
      return;
    }
    setBusy(true);
    try {
      const result = await withTimeout(api.disableStandardPorts(), 30000, 'Disable standard ports timed out.');
      if (!result.success) {
        alert(result.error || result.output || t.settingsPanel.disableStandardPortsError);
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to disable standard ports:', error);
      alert(t.settingsPanel.disableStandardPortsError);
    }
    setBusy(false);
  };

  const handleInstallHelper = async () => {
    if (!confirm(t.settingsPanel.confirmInstallHelper)) {
      return;
    }
    setBusy(true);
    try {
      const result = await withTimeout(api.installHelper(), 180000, 'Helper install timed out.');
      if (!result.success) {
        const details = [result.error, result.output].filter(Boolean).join('\n');
        alert(details || t.settingsPanel.helperInstallError);
      } else {
        const helper = await withTimeout(api.getHelperStatus(), 10000, 'Helper status request timed out.');
        if (!helper.running) {
          alert(t.settingsPanel.helperNotRunningYet);
        }

        const sync = await withTimeout(api.reloadProxy(), 30000, 'Proxy reload timed out.');
        if (!sync.success) {
          alert(sync.error || sync.output || t.settingsPanel.helperStandardPortsActivationError);
        }
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to install helper:', error);
      alert(t.settingsPanel.helperInstallError);
    }
    setBusy(false);
  };

  const handleUninstallHelper = async () => {
    if (!confirm(t.settingsPanel.confirmUninstallHelper)) {
      return;
    }
    setBusy(true);
    try {
      const result = await withTimeout(api.uninstallHelper(), 60000, 'Helper uninstall timed out.');
      if (!result.success) {
        alert(result.error || result.output || t.settingsPanel.helperUninstallError);
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to uninstall helper:', error);
      alert(t.settingsPanel.helperUninstallError);
    }
    setBusy(false);
  };

  const handleSaveAndApply = async () => {
    if (!settings) {
      return;
    }
    setBusy(true);
    try {
      await withTimeout(api.updateSettings(settings), 20000, 'Update settings timed out.');
      const result = await withTimeout(api.reloadProxy(), 30000, 'Proxy reload timed out.');
      if (!result.success) {
        alert(result.error || result.output || t.settingsPanel.applyFailed);
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to save settings:', error);
      alert(t.settingsPanel.saveSettingsError);
    }
    setBusy(false);
  };

  const caOk = Boolean(caStatus?.installed && caStatus?.valid);
  const standardPortsOk = Boolean(proxyStatus?.standardHttpActive && proxyStatus?.standardHttpsActive);
  const helperOk = Boolean(helperStatus?.running);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 p-4 backdrop-blur-sm sm:items-center">
      <div className="mamp-modal my-4 flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden sm:my-0 sm:max-h-[90vh]">
        <div className="mamp-modal-header flex items-center justify-between px-6 py-5">
          <div>
            <h2 className="text-2xl font-semibold text-white">{t.settingsPanel.title}</h2>
            <p className="mt-1 text-sm text-[var(--mamp-text-muted)]">{t.settingsPanel.proxyAndDomains}</p>
          </div>
          <button
            onClick={onClose}
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-white/8 bg-white/5 text-[var(--mamp-text-muted)] transition hover:bg-white/10 hover:text-white"
          >
            <X size={20} />
          </button>
        </div>

        <div className="modal-scroll min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-y-contain px-6 py-5">
          <SettingsSection icon={Shield} title={t.settingsPanel.certificateAuthority}>
            <p className="mb-4 text-sm text-[var(--mamp-text-muted)]">
              {t.settingsPanel.certificateAuthorityDescription}
            </p>

            {caStatus ? (
              <div className={`mamp-note mb-4 ${caOk ? 'mamp-note-success' : 'mamp-note-danger'}`}>
                {caOk ? `✓ ${t.settingsPanel.rootCaTrusted}` : `✗ ${t.settingsPanel.rootCaNotTrusted}`}
              </div>
            ) : (
              <div className="mamp-note mb-4 border-white/8 bg-black/12 text-[var(--mamp-text-muted)]">
                {t.settingsPanel.loadingCaStatus}
              </div>
            )}

            <div className="flex flex-wrap gap-3">
              <button
                onClick={handleInstallCA}
                disabled={busy || caOk}
                className="mamp-button-primary"
              >
                {busy ? t.common.working : caOk ? t.settingsPanel.alreadyInstalled : t.settingsPanel.installRootCa}
              </button>
              <button
                onClick={handleUninstallCA}
                disabled={busy || !caStatus?.installed}
                className="mamp-button-neutral"
              >
                {busy ? t.common.working : t.settingsPanel.uninstallRootCa}
              </button>
            </div>
          </SettingsSection>

          <SettingsSection icon={Globe} title={t.settingsPanel.proxyAndDomains}>
            <div className="mb-4 rounded-xl border border-white/8 bg-black/12 p-4 text-sm text-[var(--mamp-text)]">
              <div className="flex items-center justify-between gap-4">
                <span className="font-semibold text-[var(--mamp-text-muted)]">{t.settingsPanel.helperLabel}</span>
                <span className={helperOk ? 'text-green-300' : 'text-yellow-300'}>
                  {helperOk
                    ? t.settingsPanel.helperRunning
                    : helperStatus?.installed
                      ? t.settingsPanel.helperInstalledNotRunning
                      : t.settingsPanel.helperNotInstalled}
                </span>
              </div>
              <div className="mt-2 text-[var(--mamp-text-muted)]">{t.settingsPanel.helperDescription}</div>
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  onClick={handleInstallHelper}
                  disabled={busy || helperOk}
                  className="mamp-button-primary"
                >
                  <Lock size={16} />
                  {busy ? t.common.working : helperOk ? t.settingsPanel.helperRunningButton : t.settingsPanel.installHelper}
                </button>
                <button
                  onClick={handleUninstallHelper}
                  disabled={busy || !helperStatus?.installed}
                  className="mamp-button-neutral"
                >
                  {busy ? t.common.working : t.settingsPanel.uninstallHelper}
                </button>
              </div>
            </div>

            {proxyStatus ? (
              <div className="mb-4 rounded-xl border border-white/8 bg-black/12 p-4 text-sm text-[var(--mamp-text)]">
                <div className="flex items-center justify-between gap-4">
                  <span className="font-semibold text-[var(--mamp-text-muted)]">{t.settingsPanel.standardPorts}</span>
                  <span className={standardPortsOk ? 'text-green-300' : 'text-yellow-300'}>
                    {standardPortsOk ? t.settingsPanel.active : t.settingsPanel.notActive}
                  </span>
                </div>
                <div className="mt-2 text-[var(--mamp-text-muted)]">
                  {t.settingsPanel.proxyListening(proxyStatus.proxyHttpPort, proxyStatus.proxyPort)}
                </div>
              </div>
            ) : (
              <div className="mamp-note mb-4 border-white/8 bg-black/12 text-[var(--mamp-text-muted)]">
                {t.settingsPanel.loadingProxyStatus}
              </div>
            )}

            <div className="space-y-4">
              <ToggleCard
                title={t.settingsPanel.enableStandardPorts}
                description={t.settingsPanel.enableStandardPortsDescription}
                checked={settings?.standardPortsEnabled ?? true}
                onChange={(checked) =>
                  setSettings((prev) => (prev ? { ...prev, standardPortsEnabled: checked } : prev))
                }
              />

              <ToggleCard
                title={t.settingsPanel.restoreOnQuit}
                description={t.settingsPanel.restoreOnQuitDescription}
                checked={settings?.restoreOnQuit ?? true}
                onChange={(checked) =>
                  setSettings((prev) => (prev ? { ...prev, restoreOnQuit: checked } : prev))
                }
              />

              <ToggleCard
                title={t.settingsPanel.allowPublicDomainOverrides}
                description={<span className="text-yellow-300">{t.settingsPanel.publicDomainRisk}</span>}
                checked={settings?.anyDomainOverrideEnabled ?? false}
                onChange={(checked) =>
                  setSettings((prev) => (prev ? { ...prev, anyDomainOverrideEnabled: checked } : prev))
                }
              />

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mamp-field-label">{t.settingsPanel.proxyHttpPort}</label>
                  <input
                    type="number"
                    value={settings?.proxyHttpPort ?? 8080}
                    min="1"
                    max="65535"
                    onChange={(event) =>
                      setSettings((prev) => (prev ? { ...prev, proxyHttpPort: Number(event.target.value) } : prev))
                    }
                    className="mamp-input"
                  />
                </div>
                <div>
                  <label className="mamp-field-label">{t.settingsPanel.proxyHttpsPort}</label>
                  <input
                    type="number"
                    value={settings?.proxyPort ?? 8443}
                    min="1"
                    max="65535"
                    onChange={(event) =>
                      setSettings((prev) => (prev ? { ...prev, proxyPort: Number(event.target.value) } : prev))
                    }
                    className="mamp-input"
                  />
                </div>
              </div>

              <div className="flex flex-wrap gap-3 pt-2">
                <button onClick={handleReloadProxy} disabled={busy} className="mamp-button-neutral">
                  <RefreshCw size={16} />
                  {busy ? t.common.working : t.settingsPanel.reloadProxy}
                </button>
                <button onClick={handleSyncHosts} disabled={busy} className="mamp-button-neutral">
                  {t.settingsPanel.syncHostsNow}
                </button>
                <button onClick={handleClearHosts} disabled={busy} className="mamp-button-neutral">
                  {t.settingsPanel.clearHostsOverrides}
                </button>
                <button onClick={handleDisableStandardPorts} disabled={busy} className="mamp-button-neutral">
                  {t.settingsPanel.releaseStandardPortsNow}
                </button>
              </div>
            </div>
          </SettingsSection>
        </div>

        <div className="flex items-center justify-end gap-3 border-t border-white/8 px-6 py-5">
          <button
            onClick={handleSaveAndApply}
            disabled={busy || !settings}
            className="mamp-button-primary"
          >
            {busy ? t.common.working : t.common.saveAndApply}
          </button>
          <button onClick={onClose} className="mamp-button-neutral">
            {t.common.close}
          </button>
        </div>
      </div>
    </div>
  );
}
