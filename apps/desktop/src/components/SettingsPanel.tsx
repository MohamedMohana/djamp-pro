import { useEffect, useState } from 'react';
import { X, Shield, Globe, RefreshCw, Lock } from 'lucide-react';
import { api } from '../services/api';
import type { AppSettings, ProxyStatus, HelperStatus } from '../types';

interface SettingsPanelProps {
  onClose: () => void;
}

export default function SettingsPanel({ onClose }: SettingsPanelProps) {
  const [caStatus, setCaStatus] = useState<{ installed: boolean; valid: boolean } | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [proxyStatus, setProxyStatus] = useState<ProxyStatus | null>(null);
  const [helperStatus, setHelperStatus] = useState<HelperStatus | null>(null);
  const [busy, setBusy] = useState(false);

  const withTimeout = async <T,>(promise: Promise<T>, ms: number, timeoutMessage: string): Promise<T> => {
    return await Promise.race([
      promise,
      new Promise<T>((_, reject) =>
        setTimeout(() => reject(new Error(timeoutMessage)), ms),
      ),
    ]);
  };

  const loadAll = async () => {
    const [ca, s, p, h] = await Promise.allSettled([
      withTimeout(api.checkRootCAStatus(), 8000, 'CA status request timed out.'),
      withTimeout(api.getSettings(), 8000, 'Settings request timed out.'),
      withTimeout(api.getProxyStatus(), 8000, 'Proxy status request timed out.'),
      withTimeout(api.getHelperStatus(), 8000, 'Helper status request timed out.'),
    ]);

    if (ca.status === 'fulfilled') {
      setCaStatus(ca.value);
    }
    if (s.status === 'fulfilled') {
      setSettings(s.value);
    }
    if (p.status === 'fulfilled') {
      setProxyStatus(p.value);
    }
    if (h.status === 'fulfilled') {
      setHelperStatus(h.value);
    }

    if ([ca, s, p, h].some((result) => result.status === 'rejected')) {
      console.error('Failed to load one or more settings sections', { ca, s, p, h });
    }
  };

  useEffect(() => {
    void loadAll();
  }, []);

  const handleInstallCA = async () => {
    if (
      !confirm(
        'This will install the DJAMP PRO Root CA certificate into your trusted keychains. You will be prompted for administrator privileges. Continue?',
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      await withTimeout(api.installRootCA(), 120000, 'Install Root CA timed out.');
      await loadAll();
    } catch (error) {
      console.error('Failed to install CA:', error);
      alert('Failed to install Root CA. Check permissions and try again.');
    }
    setBusy(false);
  };

  const handleUninstallCA = async () => {
    if (
      !confirm(
        'This will remove the DJAMP PRO Root CA from your keychains. You may be prompted for administrator privileges. Continue?',
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      const result = await withTimeout(api.uninstallRootCA(), 30000, 'Uninstall Root CA timed out.');
      if (!result.success) {
        alert(result.error || result.output || 'Failed to uninstall Root CA');
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to uninstall CA:', error);
      alert('Failed to uninstall Root CA. Check permissions and try again.');
    }
    setBusy(false);
  };

  const handleReloadProxy = async () => {
    setBusy(true);
    try {
      const result = await withTimeout(api.reloadProxy(), 30000, 'Proxy reload timed out.');
      if (!result.success) {
        alert(result.error || result.output || 'Proxy reload failed');
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to reload proxy:', error);
      alert('Failed to reload proxy. Check logs for details.');
    }
    setBusy(false);
  };

  const handleSyncHosts = async () => {
    setBusy(true);
    try {
      const result = await withTimeout(api.syncHosts(), 30000, 'Hosts sync timed out.');
      if (!result.success) {
        alert(result.error || result.output || 'Hosts sync failed');
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to sync hosts:', error);
      alert('Failed to sync hosts. Check permissions and try again.');
    }
    setBusy(false);
  };

  const handleClearHosts = async () => {
    if (!confirm('This will remove all DJAMP PRO entries from your hosts file (/etc/hosts). Continue?')) {
      return;
    }
    setBusy(true);
    try {
      const result = await withTimeout(api.clearHosts(), 30000, 'Hosts clear timed out.');
      if (!result.success) {
        alert(result.error || result.output || 'Hosts clear failed');
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to clear hosts:', error);
      alert('Failed to clear hosts. Check permissions and try again.');
    }
    setBusy(false);
  };

  const handleDisableStandardPorts = async () => {
    if (
      !confirm(
        'This will release ports 80/443 (standard HTTPS/HTTP). Your projects will be accessible only via the proxy ports (e.g. :8443). Continue?',
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      const result = await withTimeout(api.disableStandardPorts(), 30000, 'Disable standard ports timed out.');
      if (!result.success) {
        alert(result.error || result.output || 'Disable standard ports failed');
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to disable standard ports:', error);
      alert('Failed to disable standard ports. Check permissions and try again.');
    }
    setBusy(false);
  };

  const handleInstallHelper = async () => {
    if (
      !confirm(
        'This will install the DJAMP Helper (a small system service) to manage /etc/hosts and bind ports 80/443 like MAMP PRO. You will be prompted for your password once. Continue?',
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      const result = await withTimeout(api.installHelper(), 180000, 'Helper install timed out.');
      if (!result.success) {
        const details = [result.error, result.output].filter(Boolean).join('\n');
        alert(details || 'Helper install failed');
      } else {
        const helper = await withTimeout(api.getHelperStatus(), 10000, 'Helper status request timed out.');
        if (!helper.running) {
          alert('Helper files were installed but helper is not running yet. Open Settings again and click Install Helper once more.');
        }

        const sync = await withTimeout(api.reloadProxy(), 30000, 'Proxy reload timed out.');
        if (!sync.success) {
          alert(sync.error || sync.output || 'Helper installed, but failed to activate standard ports.');
        }
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to install helper:', error);
      alert('Failed to install helper. Check logs for details.');
    }
    setBusy(false);
  };

  const handleUninstallHelper = async () => {
    if (
      !confirm(
        'This will uninstall the DJAMP Helper and release ports 80/443. DJAMP will fall back to using high ports (e.g. :8443) and may prompt for password when editing /etc/hosts. Continue?',
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      const result = await withTimeout(api.uninstallHelper(), 60000, 'Helper uninstall timed out.');
      if (!result.success) {
        alert(result.error || result.output || 'Helper uninstall failed');
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to uninstall helper:', error);
      alert('Failed to uninstall helper. Check logs for details.');
    }
    setBusy(false);
  };

  const handleSaveAndApply = async () => {
    if (!settings) return;
    setBusy(true);
    try {
      await withTimeout(api.updateSettings(settings), 20000, 'Update settings timed out.');
      const result = await withTimeout(api.reloadProxy(), 30000, 'Proxy reload timed out.');
      if (!result.success) {
        alert(result.error || result.output || 'Apply failed');
      }
      await loadAll();
    } catch (error) {
      console.error('Failed to save settings:', error);
      alert('Failed to save settings.');
    }
    setBusy(false);
  };

  const caOk = Boolean(caStatus?.installed && caStatus?.valid);
  const standardPortsOk = Boolean(proxyStatus?.standardHttpActive && proxyStatus?.standardHttpsActive);
  const helperOk = Boolean(helperStatus?.running);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-hidden bg-black/60 p-4 sm:items-center">
      <div className="my-4 flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl bg-gray-800 sm:my-0 sm:max-h-[90vh]">
        <div className="p-6 border-b border-gray-700 flex items-center justify-between">
          <h2 className="text-2xl font-bold">Settings</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X size={24} />
          </button>
        </div>

        <div className="modal-scroll min-h-0 flex-1 overflow-y-auto overscroll-y-contain space-y-6 p-6 pr-4">
          <div className="bg-gray-900 rounded-lg p-6">
            <div className="flex items-center gap-3 mb-4">
              <Shield size={24} className="text-brand-400" />
              <h3 className="text-xl font-semibold">Certificate Authority</h3>
            </div>
            <p className="text-gray-400 mb-4">
              DJAMP PRO uses a local Root CA to issue trusted HTTPS certificates for your development domains.
            </p>

            {caStatus ? (
              <div
                className={`rounded-lg p-4 mb-4 ${
                  caOk ? 'bg-green-900/20 border border-green-800' : 'bg-red-900/20 border border-red-800'
                }`}
              >
                <div className="flex items-center gap-2">
                  {caOk ? (
                    <span className="text-green-400 font-medium">✓ Root CA is trusted</span>
                  ) : (
                    <span className="text-red-400 font-medium">✗ Root CA is not trusted</span>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-gray-700 rounded-lg p-4 mb-4">
                <span className="text-gray-400">Loading CA status...</span>
              </div>
            )}

            <button
              onClick={handleInstallCA}
              disabled={busy || caOk}
              className="bg-brand-600 hover:bg-brand-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
            >
              {busy ? 'Working...' : caOk ? 'Already Installed' : 'Install Root CA'}
            </button>

            <button
              onClick={handleUninstallCA}
              disabled={busy || !caStatus?.installed}
              className="ml-3 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded-lg transition-colors"
            >
              {busy ? 'Working...' : 'Uninstall Root CA'}
            </button>
          </div>

          <div className="bg-gray-900 rounded-lg p-6">
            <div className="flex items-center gap-3 mb-4">
              <Globe size={24} className="text-brand-400" />
              <h3 className="text-xl font-semibold">Proxy & Domains</h3>
            </div>

            <div className="rounded-lg border border-gray-700 bg-gray-800 p-4 text-sm text-gray-300">
              <div className="flex items-center justify-between">
                <span className="text-gray-400">DJAMP Helper (recommended)</span>
                <span className={helperOk ? 'text-green-400' : 'text-yellow-400'}>
                  {helperOk ? 'Running' : helperStatus?.installed ? 'Installed (not running)' : 'Not Installed'}
                </span>
              </div>
              <div className="mt-2 text-gray-400">
                The helper lets DJAMP update <code>/etc/hosts</code> and bind ports <code>80</code>/<code>443</code>{' '}
                like MAMP PRO, without repeated password prompts.
              </div>
              <div className="mt-3 flex flex-wrap gap-3">
                <button
                  onClick={handleInstallHelper}
                  disabled={busy || helperOk}
                  className="bg-brand-600 hover:bg-brand-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
                >
                  <Lock size={18} />
                  {busy ? 'Working...' : helperOk ? 'Helper Running' : 'Install Helper'}
                </button>
                <button
                  onClick={handleUninstallHelper}
                  disabled={busy || !helperStatus?.installed}
                  className="bg-gray-700 hover:bg-gray-600 disabled:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded-lg transition-colors"
                >
                  {busy ? 'Working...' : 'Uninstall Helper'}
                </button>
              </div>
            </div>

            {proxyStatus ? (
              <div className="rounded-lg border border-gray-700 bg-gray-800 p-4 text-sm text-gray-300">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Standard Ports (80/443)</span>
                  <span className={standardPortsOk ? 'text-green-400' : 'text-yellow-400'}>
                    {standardPortsOk ? 'Active' : 'Not Active'}
                  </span>
                </div>
                <div className="mt-2 text-gray-400">
                  Proxy listens on HTTP {proxyStatus.proxyHttpPort} and HTTPS {proxyStatus.proxyPort}
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-gray-700 bg-gray-800 p-4 text-sm text-gray-400">
                Loading proxy status...
              </div>
            )}

            <div className="mt-4 space-y-4">
              <label className="flex items-center justify-between gap-3 bg-gray-800 border border-gray-700 rounded-lg p-4 cursor-pointer">
                <div>
                  <div className="font-medium">Enable Standard Ports (80/443)</div>
                  <div className="text-sm text-gray-400">
                    Requires DJAMP Helper (one-time admin install). Otherwise use <code>:8443</code>.
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={settings?.standardPortsEnabled ?? true}
                  onChange={(e) =>
                    setSettings((prev) => (prev ? { ...prev, standardPortsEnabled: e.target.checked } : prev))
                  }
                  className="w-5 h-5 rounded bg-gray-600 border-gray-500 text-brand-600 focus:ring-brand-500"
                />
              </label>

              <label className="flex items-center justify-between gap-3 bg-gray-800 border border-gray-700 rounded-lg p-4 cursor-pointer">
                <div>
                  <div className="font-medium">Restore System Changes on Quit</div>
                  <div className="text-sm text-gray-400">
                    On app quit, remove DJAMP entries from <code>/etc/hosts</code> and release ports 80/443.
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={settings?.restoreOnQuit ?? true}
                  onChange={(e) =>
                    setSettings((prev) => (prev ? { ...prev, restoreOnQuit: e.target.checked } : prev))
                  }
                  className="w-5 h-5 rounded bg-gray-600 border-gray-500 text-brand-600 focus:ring-brand-500"
                />
              </label>

              <label className="flex items-center justify-between gap-3 bg-gray-800 border border-gray-700 rounded-lg p-4 cursor-pointer">
                <div>
                  <div className="font-medium">Allow Public-Domain Overrides</div>
                  <div className="text-sm text-yellow-300">Risky: can break normal browsing until removed.</div>
                </div>
                <input
                  type="checkbox"
                  checked={settings?.anyDomainOverrideEnabled ?? false}
                  onChange={(e) =>
                    setSettings((prev) =>
                      prev ? { ...prev, anyDomainOverrideEnabled: e.target.checked } : prev,
                    )
                  }
                  className="w-5 h-5 rounded bg-gray-600 border-gray-500 text-brand-600 focus:ring-brand-500"
                />
              </label>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">Proxy HTTP Port</label>
                  <input
                    type="number"
                    value={settings?.proxyHttpPort ?? 8080}
                    min="1"
                    max="65535"
                    onChange={(e) =>
                      setSettings((prev) => (prev ? { ...prev, proxyHttpPort: Number(e.target.value) } : prev))
                    }
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">Proxy HTTPS Port</label>
                  <input
                    type="number"
                    value={settings?.proxyPort ?? 8443}
                    min="1"
                    max="65535"
                    onChange={(e) =>
                      setSettings((prev) => (prev ? { ...prev, proxyPort: Number(e.target.value) } : prev))
                    }
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-500"
                  />
                </div>
              </div>

              <button
                onClick={handleReloadProxy}
                disabled={busy}
                className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
              >
                <RefreshCw size={18} />
                {busy ? 'Working...' : 'Reload Proxy'}
              </button>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <button
                  onClick={handleSyncHosts}
                  disabled={busy}
                  className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded-lg transition-colors"
                >
                  Sync Hosts Now
                </button>
                <button
                  onClick={handleClearHosts}
                  disabled={busy}
                  className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded-lg transition-colors"
                >
                  Clear Hosts Overrides
                </button>
                <button
                  onClick={handleDisableStandardPorts}
                  disabled={busy}
                  className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded-lg transition-colors"
                >
                  Release 80/443 Now
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="p-6 border-t border-gray-700 flex items-center justify-end gap-3">
          <button
            onClick={handleSaveAndApply}
            disabled={busy || !settings}
            className="px-6 py-2 rounded-lg bg-brand-600 hover:bg-brand-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-medium transition-colors"
          >
            {busy ? 'Working...' : 'Save & Apply'}
          </button>
          <button
            onClick={onClose}
            className="px-6 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
