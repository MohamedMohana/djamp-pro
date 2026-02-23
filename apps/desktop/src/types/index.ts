export interface Project {
  id: string;
  name: string;
  path: string;
  settingsModule: string;
  domain: string;
  aliases: string[];
  port: number;
  pythonVersion: string;
  venvPath: string;
  debug: boolean;
  allowedHosts: string[];
  httpsEnabled: boolean;
  certificatePath: string;
  staticPath: string;
  mediaPath: string;
  database: DatabaseConfig;
  cache: CacheConfig;
  status: ProjectStatus;
  environmentVars: Record<string, string>;
  createdAt: string;
  runtimeMode?: 'uv' | 'conda' | 'system' | 'custom';
  condaEnv?: string;
  customInterpreter?: string;
  domainMode?: 'local_only' | 'public_override';
}

export type ProjectStatus = 'stopped' | 'starting' | 'running' | 'stopping' | 'error';

export interface DatabaseConfig {
  type: 'postgres' | 'mysql' | 'none';
  port: number;
  name: string;
  username: string;
  password: string;
}

export interface CacheConfig {
  type: 'redis' | 'none';
  port: number;
}

export interface AppSettings {
  caInstalled: boolean;
  defaultPython: string;
  autoStartProjects: string[];
  proxyPort: number;
  proxyHttpPort: number;
  anyDomainOverrideEnabled: boolean;
  standardPortsEnabled: boolean;
  restoreOnQuit: boolean;
}

export interface ProxyStatus {
  proxyHttpPort: number;
  proxyPort: number;
  standardPortsEnabled: boolean;
  standardHttpActive: boolean;
  standardHttpsActive: boolean;
  proxyHttpActive: boolean;
  proxyHttpsActive: boolean;
}

export interface CertificateInfo {
  domain: string;
  certificatePath: string;
  keyPath: string;
  expiresAt: string;
  isValid: boolean;
}

export interface LogEntry {
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'debug';
  source: 'django' | 'proxy' | 'database' | 'system';
  message: string;
  projectId?: string;
}

export interface CommandResult {
  success: boolean;
  output: string;
  error?: string;
}

export interface HelperStatus {
  installed: boolean;
  running: boolean;
  socketPath: string;
  label: string;
  standardHttpActive: boolean;
  standardHttpsActive: boolean;
}
