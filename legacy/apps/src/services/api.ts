import { invoke } from '@tauri-apps/api/tauri';
import type { 
  Project, 
  AppSettings, 
  CertificateInfo,
  CommandResult 
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

  startProject: async (id: string): Promise<void> => {
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

  openVSCode: async (projectId: string): Promise<void> => {
    return invoke('open_vscode', { projectId });
  },

  // Settings
  getSettings: async (): Promise<AppSettings> => {
    return invoke('get_settings');
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
