import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { X, Shield, Globe, RefreshCw, Lock, Monitor, Moon, Palette, Sun } from 'lucide-react';
import { useI18n } from '../i18n';
import { api } from '../services/api';
import type { AppSettings, ProxyStatus, HelperStatus } from '../types';
import { useTheme, type ThemePreference } from '../theme';
import { useToast } from '../toast';
import { useConfirm } from '../confirm';
import Spinner from './Spinner';
import { cn } from '../utils';

const THEME_OPTIONS: { value: ThemePreference; icon: typeof Sun }[] = [
  { value: 'system', icon: Monitor },
  { value: 'light', icon: Sun },
  { value: 'dark', icon: Moon },
];

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
        <Icon size={20} className="text-[var(--accent)]" />
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
    <label className="flex cursor-pointer items-start justify-between gap-4 rounded-lg border border-[var(--line)] bg-[var(--fill-1)] p-3.5">
      <div>
        <div className="text-[13px] font-medium text-[var(--text-1)]">{title}</div>
        <div className="mt-1 text-[12px] text-[var(--text-2)]">{description}</div>
      </div>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1 h-4 w-4 accent-[var(--accent)]"
      />
    </label>
  );
}

export default function SettingsPanel({ onClose }: SettingsPanelProps) {
  const { t } = useI18n();
  const toast = useToast();
  const theme = useTheme();
  const confirm = useConfirm();
  const [caStatus, setCaStatus] = useState<{ installed: boolean; valid: boolean } | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [proxyStatus, setProxyStatus] = useState<ProxyStatus | null>(null);
  const [helperStatus, setHelperStatus] = useState<HelperStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

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
    const ok = await confirm({
      title: t.settingsPanel.installRootCa,
      message: t.settingsPanel.confirmInstallRootCa,
    });
    if (!ok) {
      return;
    }
    setBusy('ca-install');
    try {
      await withTimeout(api.installRootCA(), 120000, 'Install Root CA timed out.');
      toast.success(t.settingsPanel.rootCaInstalled);
      await loadAll();
    } catch (error) {
      console.error('Failed to install CA:', error);
      toast.error(t.settingsPanel.installRootCaError);
    }
    setBusy(null);
  };

  const handleUninstallCA = async () => {
    const ok = await confirm({
      title: t.settingsPanel.uninstallRootCa,
      message: t.settingsPanel.confirmUninstallRootCa,
      tone: 'danger',
    });
    if (!ok) {
      return;
    }
    setBusy('ca-uninstall');
    try {
      const result = await withTimeout(api.uninstallRootCA(), 30000, 'Uninstall Root CA timed out.');
      if (!result.success) {
        toast.error(t.settingsPanel.uninstallRootCaError, result.error || result.output);
      } else {
        toast.success(t.settingsPanel.rootCaUninstalled);
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to uninstall CA:', error);
      toast.error(t.settingsPanel.uninstallRootCaError);
    }
    setBusy(null);
  };

  const handleReloadProxy = async () => {
    setBusy('proxy-reload');
    try {
      const result = await withTimeout(api.reloadProxy(), 30000, 'Proxy reload timed out.');
      if (!result.success) {
        toast.error(t.settingsPanel.proxyReloadError, result.error || result.output);
      } else {
        toast.success(t.settingsPanel.proxyReloaded);
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to reload proxy:', error);
      toast.error(t.settingsPanel.proxyReloadError);
    }
    setBusy(null);
  };

  const handleSyncHosts = async () => {
    setBusy('hosts-sync');
    try {
      const result = await withTimeout(api.syncHosts(), 30000, 'Hosts sync timed out.');
      if (!result.success) {
        toast.error(t.settingsPanel.hostsSyncError, result.error || result.output);
      } else {
        toast.success(t.settingsPanel.hostsSynced);
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to sync hosts:', error);
      toast.error(t.settingsPanel.hostsSyncError);
    }
    setBusy(null);
  };

  const handleClearHosts = async () => {
    const ok = await confirm({
      title: t.settingsPanel.clearHostsOverrides,
      message: t.settingsPanel.confirmClearHosts,
      tone: 'danger',
    });
    if (!ok) {
      return;
    }
    setBusy('hosts-clear');
    try {
      const result = await withTimeout(api.clearHosts(), 30000, 'Hosts clear timed out.');
      if (!result.success) {
        toast.error(t.settingsPanel.hostsClearError, result.error || result.output);
      } else {
        toast.success(t.settingsPanel.hostsCleared);
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to clear hosts:', error);
      toast.error(t.settingsPanel.hostsClearError);
    }
    setBusy(null);
  };

  const handleDisableStandardPorts = async () => {
    const ok = await confirm({
      title: t.settingsPanel.releaseStandardPortsNow,
      message: t.settingsPanel.confirmDisableStandardPorts,
      tone: 'danger',
    });
    if (!ok) {
      return;
    }
    setBusy('ports-release');
    try {
      const result = await withTimeout(api.disableStandardPorts(), 30000, 'Disable standard ports timed out.');
      if (!result.success) {
        toast.error(t.settingsPanel.disableStandardPortsError, result.error || result.output);
      } else {
        toast.success(t.settingsPanel.standardPortsReleased);
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to disable standard ports:', error);
      toast.error(t.settingsPanel.disableStandardPortsError);
    }
    setBusy(null);
  };

  const handleInstallHelper = async () => {
    const ok = await confirm({
      title: t.settingsPanel.installHelper,
      message: t.settingsPanel.confirmInstallHelper,
    });
    if (!ok) {
      return;
    }
    setBusy('helper-install');
    try {
      const result = await withTimeout(api.installHelper(), 180000, 'Helper install timed out.');
      if (!result.success) {
        const details = [result.error, result.output].filter(Boolean).join('\n');
        toast.error(t.settingsPanel.helperInstallError, details || undefined);
      } else {
        const helper = await withTimeout(api.getHelperStatus(), 10000, 'Helper status request timed out.');
        if (!helper.running) {
          toast.warning(t.settingsPanel.helperNotRunningYet);
        } else {
          toast.success(t.settingsPanel.helperInstalled);
        }

        const sync = await withTimeout(api.reloadProxy(), 30000, 'Proxy reload timed out.');
        if (!sync.success) {
          toast.warning(
            t.settingsPanel.helperStandardPortsActivationError,
            sync.error || sync.output,
          );
        }
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to install helper:', error);
      toast.error(t.settingsPanel.helperInstallError);
    }
    setBusy(null);
  };

  const handleUninstallHelper = async () => {
    const ok = await confirm({
      title: t.settingsPanel.uninstallHelper,
      message: t.settingsPanel.confirmUninstallHelper,
      tone: 'danger',
    });
    if (!ok) {
      return;
    }
    setBusy('helper-uninstall');
    try {
      const result = await withTimeout(api.uninstallHelper(), 60000, 'Helper uninstall timed out.');
      if (!result.success) {
        toast.error(t.settingsPanel.helperUninstallError, result.error || result.output);
      } else {
        toast.success(t.settingsPanel.helperUninstalled);
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to uninstall helper:', error);
      toast.error(t.settingsPanel.helperUninstallError);
    }
    setBusy(null);
  };

  const handleSaveAndApply = async () => {
    if (!settings) {
      return;
    }
    setBusy('save');
    try {
      await withTimeout(api.updateSettings(settings), 20000, 'Update settings timed out.');
      const result = await withTimeout(api.reloadProxy(), 30000, 'Proxy reload timed out.');
      if (!result.success) {
        toast.error(t.settingsPanel.applyFailed, result.error || result.output);
      } else {
        toast.success(t.settingsPanel.settingsSaved);
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to save settings:', error);
      toast.error(t.settingsPanel.saveSettingsError);
    }
    setBusy(null);
  };

  const caOk = Boolean(caStatus?.installed && caStatus?.valid);
  const standardPortsOk = Boolean(proxyStatus?.standardHttpActive && proxyStatus?.standardHttpsActive);
  const helperOk = Boolean(helperStatus?.running);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-[var(--scrim)] p-4 backdrop-blur-sm sm:items-center">
      <div className="mamp-modal my-4 flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden sm:my-0 sm:max-h-[90vh]">
        <div className="mamp-modal-header flex items-center justify-between px-6 py-5">
          <div>
            <h2 className="text-[17px] font-semibold text-[var(--text-1)]">{t.settingsPanel.title}</h2>
            <p className="mt-1 text-[12px] text-[var(--text-2)]">{t.settingsPanel.proxyAndDomains}</p>
          </div>
          <button
            onClick={onClose}
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--line)] bg-[var(--fill-1)] text-[var(--mamp-text-muted)] transition hover:bg-[var(--fill-2)] hover:text-[var(--text-1)]"
          >
            <X size={20} />
          </button>
        </div>

        <div className="modal-scroll min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-y-contain px-6 py-5">
          <SettingsSection icon={Palette} title={t.settingsPanel.appearance}>
            <p className="mb-3 text-[12px] text-[var(--text-2)]">
              {t.settingsPanel.appearanceDescription}
            </p>
            <div
              role="group"
              aria-label={t.settingsPanel.appearance}
              className="inline-flex rounded-lg border border-[var(--line)] bg-[var(--well)] p-0.5"
            >
              {THEME_OPTIONS.map(({ value, icon: Icon }) => {
                const isActive = theme.preference === value;
                return (
                  <button
                    key={value}
                    onClick={() => theme.setPreference(value)}
                    aria-pressed={isActive}
                    className={cn(
                      'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12.5px] font-medium transition',
                      isActive
                        ? 'bg-[var(--surface-4)] text-[var(--text-1)]'
                        : 'text-[var(--text-2)] hover:text-[var(--text-1)]',
                    )}
                  >
                    <Icon size={14} />
                    {t.common.themes[value]}
                  </button>
                );
              })}
            </div>
          </SettingsSection>

          <SettingsSection icon={Shield} title={t.settingsPanel.certificateAuthority}>
            <p className="mb-4 text-[13px] text-[var(--text-2)]">
              {t.settingsPanel.certificateAuthorityDescription}
            </p>

            {caStatus ? (
              <div className={`mamp-note mb-4 ${caOk ? 'mamp-note-success' : 'mamp-note-danger'}`}>
                {caOk ? `✓ ${t.settingsPanel.rootCaTrusted}` : `✗ ${t.settingsPanel.rootCaNotTrusted}`}
              </div>
            ) : (
              <div className="mamp-note mb-4 text-[var(--text-2)]">
                {t.settingsPanel.loadingCaStatus}
              </div>
            )}

            <div className="flex flex-wrap gap-3">
              <button
                onClick={handleInstallCA}
                disabled={busy !== null || caOk}
                className="mamp-button-primary"
              >
                {busy === 'ca-install' && <Spinner size={16} />}
                {caOk ? t.settingsPanel.alreadyInstalled : t.settingsPanel.installRootCa}
              </button>
              <button
                onClick={handleUninstallCA}
                disabled={busy !== null || !caStatus?.installed}
                className="mamp-button-neutral"
              >
                {busy === 'ca-uninstall' && <Spinner size={16} />}
                {t.settingsPanel.uninstallRootCa}
              </button>
            </div>
          </SettingsSection>

          <SettingsSection icon={Globe} title={t.settingsPanel.proxyAndDomains}>
            <div className="mb-4 rounded-lg border border-[var(--line)] bg-[var(--fill-1)] p-3.5 text-[13px] text-[var(--text-1)]">
              <div className="flex items-center justify-between gap-4">
                <span className="text-[12px] font-medium text-[var(--text-2)]">{t.settingsPanel.helperLabel}</span>
                <span className={helperOk ? 'text-[var(--success-text)]' : 'text-[var(--warning-text)]'}>
                  {helperOk
                    ? t.settingsPanel.helperRunning
                    : helperStatus?.installed
                      ? t.settingsPanel.helperInstalledNotRunning
                      : t.settingsPanel.helperNotInstalled}
                </span>
              </div>
              <div className="mt-2 text-[12px] text-[var(--text-2)]">{t.settingsPanel.helperDescription}</div>
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  onClick={handleInstallHelper}
                  disabled={busy !== null || helperOk}
                  className="mamp-button-primary"
                >
                  {busy === 'helper-install' ? <Spinner size={16} /> : <Lock size={16} />}
                  {helperOk ? t.settingsPanel.helperRunningButton : t.settingsPanel.installHelper}
                </button>
                <button
                  onClick={handleUninstallHelper}
                  disabled={busy !== null || !helperStatus?.installed}
                  className="mamp-button-neutral"
                >
                  {busy === 'helper-uninstall' && <Spinner size={16} />}
                  {t.settingsPanel.uninstallHelper}
                </button>
              </div>
            </div>

            {proxyStatus ? (
              <div className="mb-4 rounded-lg border border-[var(--line)] bg-[var(--fill-1)] p-3.5 text-[13px] text-[var(--text-1)]">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-[12px] font-medium text-[var(--text-2)]">{t.settingsPanel.standardPorts}</span>
                  <span className={standardPortsOk ? 'text-[var(--success-text)]' : 'text-[var(--warning-text)]'}>
                    {standardPortsOk ? t.settingsPanel.active : t.settingsPanel.notActive}
                  </span>
                </div>
                <div className="mt-2 text-[12px] text-[var(--text-2)]">
                  {t.settingsPanel.proxyListening(proxyStatus.proxyHttpPort, proxyStatus.proxyPort)}
                </div>
              </div>
            ) : (
              <div className="mamp-note mb-4 text-[var(--text-2)]">
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
                description={<span className="text-[var(--warning-text)]">{t.settingsPanel.publicDomainRisk}</span>}
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
                <button onClick={handleReloadProxy} disabled={busy !== null} className="mamp-button-neutral">
                  {busy === 'proxy-reload' ? <Spinner size={16} /> : <RefreshCw size={16} />}
                  {t.settingsPanel.reloadProxy}
                </button>
                <button onClick={handleSyncHosts} disabled={busy !== null} className="mamp-button-neutral">
                  {busy === 'hosts-sync' && <Spinner size={16} />}
                  {t.settingsPanel.syncHostsNow}
                </button>
                <button onClick={handleClearHosts} disabled={busy !== null} className="mamp-button-neutral">
                  {busy === 'hosts-clear' && <Spinner size={16} />}
                  {t.settingsPanel.clearHostsOverrides}
                </button>
                <button
                  onClick={handleDisableStandardPorts}
                  disabled={busy !== null}
                  className="mamp-button-neutral"
                >
                  {busy === 'ports-release' && <Spinner size={16} />}
                  {t.settingsPanel.releaseStandardPortsNow}
                </button>
              </div>
            </div>
          </SettingsSection>
        </div>

        <div className="flex items-center justify-end gap-3 border-t border-[var(--line)] px-6 py-5">
          <button
            onClick={handleSaveAndApply}
            disabled={busy !== null || !settings}
            className="mamp-button-primary"
          >
            {busy === 'save' && <Spinner size={16} />}
            {t.common.saveAndApply}
          </button>
          <button onClick={onClose} className="mamp-button-neutral">
            {t.common.close}
          </button>
        </div>
      </div>
    </div>
  );
}
