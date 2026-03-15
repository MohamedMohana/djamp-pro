import { useCallback, useEffect, useState } from 'react';
import { X, Shield, Globe, RefreshCw, Lock } from 'lucide-react';
import { useI18n } from '../i18n';
import { api } from '../services/api';
import type { AppSettings, ProxyStatus, HelperStatus } from '../types';

interface SettingsPanelProps {
  onClose: () => void;
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
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-hidden bg-black/60 p-4 sm:items-center">
      <div className="my-4 flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl bg-gray-800 sm:my-0 sm:max-h-[90vh]">
        <div className="flex items-center justify-between border-b border-gray-700 p-6">
          <h2 className="text-2xl font-bold">{t.settingsPanel.title}</h2>
          <button onClick={onClose} className="text-gray-400 transition-colors hover:text-white">
            <X size={24} />
          </button>
        </div>

        <div className="modal-scroll min-h-0 flex-1 space-y-6 overflow-y-auto overscroll-y-contain p-6">
          <div className="rounded-lg bg-gray-900 p-6">
            <div className="mb-4 flex items-center gap-3">
              <Shield size={24} className="text-brand-400" />
              <h3 className="text-xl font-semibold">{t.settingsPanel.certificateAuthority}</h3>
            </div>
            <p className="mb-4 text-gray-400">{t.settingsPanel.certificateAuthorityDescription}</p>

            {caStatus ? (
              <div
                className={`mb-4 rounded-lg p-4 ${
                  caOk ? 'border border-green-800 bg-green-900/20' : 'border border-red-800 bg-red-900/20'
                }`}
              >
                <div className="flex items-center gap-2">
                  {caOk ? (
                    <span className="font-medium text-green-400">✓ {t.settingsPanel.rootCaTrusted}</span>
                  ) : (
                    <span className="font-medium text-red-400">✗ {t.settingsPanel.rootCaNotTrusted}</span>
                  )}
                </div>
              </div>
            ) : (
              <div className="mb-4 rounded-lg bg-gray-700 p-4">
                <span className="text-gray-400">{t.settingsPanel.loadingCaStatus}</span>
              </div>
            )}

            <div className="flex flex-wrap gap-3">
              <button
                onClick={handleInstallCA}
                disabled={busy || caOk}
                className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 font-medium text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-gray-700"
              >
                {busy ? t.common.working : caOk ? t.settingsPanel.alreadyInstalled : t.settingsPanel.installRootCa}
              </button>

              <button
                onClick={handleUninstallCA}
                disabled={busy || !caStatus?.installed}
                className="rounded-lg bg-gray-700 px-4 py-2 font-medium text-white transition-colors hover:bg-gray-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? t.common.working : t.settingsPanel.uninstallRootCa}
              </button>
            </div>
          </div>

          <div className="rounded-lg bg-gray-900 p-6">
            <div className="mb-4 flex items-center gap-3">
              <Globe size={24} className="text-brand-400" />
              <h3 className="text-xl font-semibold">{t.settingsPanel.proxyAndDomains}</h3>
            </div>

            <div className="rounded-lg border border-gray-700 bg-gray-800 p-4 text-sm text-gray-300">
              <div className="flex items-center justify-between">
                <span className="text-gray-400">{t.settingsPanel.helperLabel}</span>
                <span className={helperOk ? 'text-green-400' : 'text-yellow-400'}>
                  {helperOk
                    ? t.settingsPanel.helperRunning
                    : helperStatus?.installed
                      ? t.settingsPanel.helperInstalledNotRunning
                      : t.settingsPanel.helperNotInstalled}
                </span>
              </div>
              <div className="mt-2 text-gray-400">{t.settingsPanel.helperDescription}</div>
              <div className="mt-3 flex flex-wrap gap-3">
                <button
                  onClick={handleInstallHelper}
                  disabled={busy || helperOk}
                  className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 font-medium text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-gray-700"
                >
                  <Lock size={18} />
                  {busy ? t.common.working : helperOk ? t.settingsPanel.helperRunningButton : t.settingsPanel.installHelper}
                </button>
                <button
                  onClick={handleUninstallHelper}
                  disabled={busy || !helperStatus?.installed}
                  className="rounded-lg bg-gray-700 px-4 py-2 font-medium text-white transition-colors hover:bg-gray-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {busy ? t.common.working : t.settingsPanel.uninstallHelper}
                </button>
              </div>
            </div>

            {proxyStatus ? (
              <div className="rounded-lg border border-gray-700 bg-gray-800 p-4 text-sm text-gray-300">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">{t.settingsPanel.standardPorts}</span>
                  <span className={standardPortsOk ? 'text-green-400' : 'text-yellow-400'}>
                    {standardPortsOk ? t.settingsPanel.active : t.settingsPanel.notActive}
                  </span>
                </div>
                <div className="mt-2 text-gray-400">
                  {t.settingsPanel.proxyListening(proxyStatus.proxyHttpPort, proxyStatus.proxyPort)}
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-gray-700 bg-gray-800 p-4 text-sm text-gray-400">
                {t.settingsPanel.loadingProxyStatus}
              </div>
            )}

            <div className="mt-4 space-y-4">
              <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-gray-700 bg-gray-800 p-4">
                <div>
                  <div className="font-medium">{t.settingsPanel.enableStandardPorts}</div>
                  <div className="text-sm text-gray-400">{t.settingsPanel.enableStandardPortsDescription}</div>
                </div>
                <input
                  type="checkbox"
                  checked={settings?.standardPortsEnabled ?? true}
                  onChange={(event) =>
                    setSettings((prev) => (prev ? { ...prev, standardPortsEnabled: event.target.checked } : prev))
                  }
                  className="h-5 w-5 rounded border-gray-500 bg-gray-600 text-brand-600 focus:ring-brand-500"
                />
              </label>

              <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-gray-700 bg-gray-800 p-4">
                <div>
                  <div className="font-medium">{t.settingsPanel.restoreOnQuit}</div>
                  <div className="text-sm text-gray-400">{t.settingsPanel.restoreOnQuitDescription}</div>
                </div>
                <input
                  type="checkbox"
                  checked={settings?.restoreOnQuit ?? true}
                  onChange={(event) =>
                    setSettings((prev) => (prev ? { ...prev, restoreOnQuit: event.target.checked } : prev))
                  }
                  className="h-5 w-5 rounded border-gray-500 bg-gray-600 text-brand-600 focus:ring-brand-500"
                />
              </label>

              <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-gray-700 bg-gray-800 p-4">
                <div>
                  <div className="font-medium">{t.settingsPanel.allowPublicDomainOverrides}</div>
                  <div className="text-sm text-yellow-300">{t.settingsPanel.publicDomainRisk}</div>
                </div>
                <input
                  type="checkbox"
                  checked={settings?.anyDomainOverrideEnabled ?? false}
                  onChange={(event) =>
                    setSettings((prev) =>
                      prev ? { ...prev, anyDomainOverrideEnabled: event.target.checked } : prev,
                    )
                  }
                  className="h-5 w-5 rounded border-gray-500 bg-gray-600 text-brand-600 focus:ring-brand-500"
                />
              </label>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-400">{t.settingsPanel.proxyHttpPort}</label>
                  <input
                    type="number"
                    value={settings?.proxyHttpPort ?? 8080}
                    min="1"
                    max="65535"
                    onChange={(event) =>
                      setSettings((prev) => (prev ? { ...prev, proxyHttpPort: Number(event.target.value) } : prev))
                    }
                    className="w-full rounded-lg border border-gray-600 bg-gray-700 px-4 py-3 text-white focus:border-brand-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-400">{t.settingsPanel.proxyHttpsPort}</label>
                  <input
                    type="number"
                    value={settings?.proxyPort ?? 8443}
                    min="1"
                    max="65535"
                    onChange={(event) =>
                      setSettings((prev) => (prev ? { ...prev, proxyPort: Number(event.target.value) } : prev))
                    }
                    className="w-full rounded-lg border border-gray-600 bg-gray-700 px-4 py-3 text-white focus:border-brand-500 focus:outline-none"
                  />
                </div>
              </div>

              <button
                onClick={handleReloadProxy}
                disabled={busy}
                className="flex items-center gap-2 rounded-lg bg-gray-700 px-4 py-2 font-medium text-white transition-colors hover:bg-gray-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw size={18} />
                {busy ? t.common.working : t.settingsPanel.reloadProxy}
              </button>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <button
                  onClick={handleSyncHosts}
                  disabled={busy}
                  className="rounded-lg bg-gray-700 px-4 py-2 font-medium text-white transition-colors hover:bg-gray-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {t.settingsPanel.syncHostsNow}
                </button>
                <button
                  onClick={handleClearHosts}
                  disabled={busy}
                  className="rounded-lg bg-gray-700 px-4 py-2 font-medium text-white transition-colors hover:bg-gray-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {t.settingsPanel.clearHostsOverrides}
                </button>
                <button
                  onClick={handleDisableStandardPorts}
                  disabled={busy}
                  className="rounded-lg bg-gray-700 px-4 py-2 font-medium text-white transition-colors hover:bg-gray-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {t.settingsPanel.releaseStandardPortsNow}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 border-t border-gray-700 p-6">
          <button
            onClick={handleSaveAndApply}
            disabled={busy || !settings}
            className="rounded-lg bg-brand-600 px-6 py-2 font-medium text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-gray-700"
          >
            {busy ? t.common.working : t.common.saveAndApply}
          </button>
          <button
            onClick={onClose}
            className="rounded-lg bg-gray-700 px-6 py-2 font-medium text-white transition-colors hover:bg-gray-600"
          >
            {t.common.close}
          </button>
        </div>
      </div>
    </div>
  );
}
