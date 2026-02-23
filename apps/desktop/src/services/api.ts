import { invoke } from '@tauri-apps/api/tauri';
import type { 
  Project, 
  AppSettings, 
  ProxyStatus,
  CertificateInfo,
  CommandResult,
  HelperStatus,
} from '../types';

export const api = {
  // Projects
  getProjects: async (): Promise<Project[]> => {
    return invoke('get_projects');
  },

  addProject: async (project: Omit<Project, 'id' | 'createdAt' | 'status'>): Promise<void> => {
    return invoke('add_project', { project });
  },

  updateProject: async (id: string, updates: Partial<Project>): Promise<void> => {
    return invoke('update_project', { id, updates });
  },

  deleteProject: async (id: string): Promise<void> => {
    return invoke('delete_project', { id });
  },

  startProject: async (id: string): Promise<{
    message?: string;
    hosts?: CommandResult;
    proxy?: CommandResult;
  }> => {
    return invoke('start_project', { id });
  },

  stopProject: async (id: string): Promise<void> => {
    return invoke('stop_project', { id });
  },

  restartProject: async (id: string): Promise<void> => {
    return invoke('restart_project', { id });
  },

  // Django Commands
  runMigrate: async (projectId: string): Promise<CommandResult> => {
    return invoke('run_migrate', { projectId });
  },

  runCollectstatic: async (projectId: string): Promise<CommandResult> => {
    return invoke('run_collectstatic', { projectId });
  },

  runCreateSuperuser: async (projectId: string, username: string, email: string): Promise<CommandResult> => {
    return invoke('create_superuser', { projectId, username, email });
  },

  runTests: async (projectId: string): Promise<CommandResult> => {
    return invoke('run_tests', { projectId });
  },

  openShell: async (projectId: string): Promise<void> => {
    return invoke('open_shell', { projectId });
  },

  openDatabaseShell: async (projectId: string): Promise<void> => {
    return invoke('open_db_shell', { projectId });
  },

  openVSCode: async (projectId: string): Promise<void> => {
    return invoke('open_vscode', { projectId });
  },

  openInBrowser: async (url: string): Promise<void> => {
    return invoke('open_in_browser', { url });
  },

  // Settings
  getSettings: async (): Promise<AppSettings> => {
    return invoke('get_settings');
  },

  getProxyStatus: async (): Promise<ProxyStatus> => {
    return invoke('get_proxy_status');
  },

  reloadProxy: async (): Promise<CommandResult> => {
    return invoke('reload_proxy');
  },

  disableStandardPorts: async (): Promise<CommandResult> => {
    return invoke('disable_standard_ports');
  },

  // Helper (macOS privileged helper)
  getHelperStatus: async (): Promise<HelperStatus> => {
    return invoke('get_helper_status');
  },

  installHelper: async (): Promise<CommandResult> => {
    return invoke('install_helper');
  },

  uninstallHelper: async (): Promise<CommandResult> => {
    return invoke('uninstall_helper');
  },

  updateSettings: async (settings: Partial<AppSettings>): Promise<void> => {
    return invoke('update_settings', { settings });
  },

  // Domains & Certificates
  addDomain: async (domain: string): Promise<void> => {
    return invoke('add_domain', { domain });
  },

  removeDomain: async (domain: string): Promise<void> => {
    return invoke('remove_domain', { domain });
  },

  syncHosts: async (): Promise<CommandResult> => {
    return invoke('sync_domains');
  },

  clearHosts: async (): Promise<CommandResult> => {
    return invoke('clear_domains');
  },

  generateCertificate: async (domain: string): Promise<CertificateInfo> => {
    return invoke('generate_certificate', { domain });
  },

  checkCertificateStatus: async (domain: string): Promise<CertificateInfo> => {
    return invoke('check_certificate_status', { domain });
  },

  // Root CA
  installRootCA: async (): Promise<void> => {
    return invoke('install_root_ca');
  },

  uninstallRootCA: async (): Promise<CommandResult> => {
    return invoke('uninstall_root_ca');
  },

  checkRootCAStatus: async (): Promise<{ installed: boolean; valid: boolean }> => {
    return invoke('check_root_ca_status');
  },

  // Database
  startDatabase: async (projectId: string): Promise<void> => {
    return invoke('start_database', { projectId });
  },

  stopDatabase: async (projectId: string): Promise<void> => {
    return invoke('stop_database', { projectId });
  },

  testDatabaseConnection: async (projectId: string): Promise<CommandResult> => {
    return invoke('test_database_connection', { projectId });
  },

  // Logs
  getLogs: async (projectId: string, source: 'django' | 'proxy' | 'database'): Promise<string> => {
    return invoke('get_logs', { projectId, source });
  },

  // Utilities
  detectDjangoProject: async (path: string): Promise<{
    found: boolean;
    managePyPath?: string;
    settingsModules?: string[];
  }> => {
    return invoke('detect_django_project', { path });
  },

  createVenv: async (path: string, pythonVersion: string): Promise<void> => {
    return invoke('create_venv', { path, pythonVersion });
  },

  installDependencies: async (projectId: string): Promise<CommandResult> => {
    return invoke('install_dependencies', { projectId });
  },
};
