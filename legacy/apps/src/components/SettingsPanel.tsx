import { useState, useEffect } from 'react';
import { X, Shield, Key, HardDrive } from 'lucide-react';
import { api } from '../services/api';

interface SettingsPanelProps {
  onClose: () => void;
}

export default function SettingsPanel({ onClose }: SettingsPanelProps) {
  const [caStatus, setCaStatus] = useState<{ installed: boolean; valid: boolean } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadCaStatus();
  }, []);

  const loadCaStatus = async () => {
    try {
      const status = await api.checkRootCAStatus();
      setCaStatus(status);
    } catch (error) {
      console.error('Failed to load CA status:', error);
    }
  };

  const handleInstallCA = async () => {
    if (!confirm('This will install the DJANGOForge Root CA certificate. You will be prompted for administrator privileges. Continue?')) {
      return;
    }
    
    setLoading(true);
    try {
      await api.installRootCA();
      await loadCaStatus();
    } catch (error) {
      console.error('Failed to install CA:', error);
      alert('Failed to install Root CA. Please check permissions.');
    }
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b border-gray-700 flex items-center justify-between">
          <h2 className="text-2xl font-bold">Settings</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Root CA Status */}
          <div className="bg-gray-900 rounded-lg p-6">
            <div className="flex items-center gap-3 mb-4">
              <Shield size={24} className="text-brand-400" />
              <h3 className="text-xl font-semibold">Certificate Authority</h3>
            </div>
            <p className="text-gray-400 mb-4">
              The Root CA is used to generate trusted HTTPS certificates for your local .test domains. It needs to be installed once per system.
            </p>
            {caStatus ? (
              <div className={`rounded-lg p-4 mb-4 ${caStatus.installed && caStatus.valid ? 'bg-green-900/20 border border-green-800' : 'bg-red-900/20 border border-red-800'}`}>
                <div className="flex items-center gap-2">
                  {caStatus.installed && caStatus.valid ? (
                    <span className="text-green-400 font-medium">✓ Root CA is installed and trusted</span>
                  ) : (
                    <span className="text-red-400 font-medium">✗ Root CA is not installed</span>
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
              disabled={loading || caStatus?.installed}
              className="bg-brand-600 hover:bg-brand-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-medium py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
            >
              {loading ? 'Installing...' : caStatus?.installed ? 'Already Installed' : 'Install Root CA'}
            </button>
          </div>

          {/* Application Settings */}
          <div className="bg-gray-900 rounded-lg p-6">
            <div className="flex items-center gap-3 mb-4">
              <Key size={24} className="text-brand-400" />
              <h3 className="text-xl font-semibold">Application Settings</h3>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Default Python Version
                </label>
                <select className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-500">
                  <option value="3.11">Python 3.11</option>
                  <option value="3.10">Python 3.10</option>
                  <option value="3.9">Python 3.9</option>
                  <option value="3.8">Python 3.8</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Proxy Port
                </label>
                <input
                  type="number"
                  defaultValue={80}
                  min="80"
                  max="65535"
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-brand-500"
                />
              </div>
            </div>
          </div>

          {/* Storage Settings */}
          <div className="bg-gray-900 rounded-lg p-6">
            <div className="flex items-center gap-3 mb-4">
              <HardDrive size={24} className="text-brand-400" />
              <h3 className="text-xl font-semibold">Storage</h3>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Projects Directory
                </label>
                <input
                  type="text"
                  defaultValue="~/djamp-projects"
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Virtual Environments Directory
                </label>
                <input
                  type="text"
                  defaultValue="~/djamp-venvs"
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Certificates Directory
                </label>
                <input
                  type="text"
                  defaultValue="~/.djamp/certs"
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-brand-500"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-700 flex justify-end">
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
