import type { Project, ProxyStatus } from '../types';
import type { DjampApi } from './api';

// In-memory stand-in for the Tauri bridge so the UI can be developed and
// visually reviewed in a plain browser (`npm run dev` outside Tauri).

type Api = DjampApi;

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

function makeProject(overrides: Partial<Project>): Project {
  return {
    id: crypto.randomUUID(),
    name: 'Demo Project',
    path: '/Users/dev/projects/demo',
    settingsModule: 'config.settings',
    domain: 'demo.test',
    aliases: [],
    port: 8001,
    pythonVersion: '3.12',
    venvPath: '/Users/dev/projects/demo/.venv',
    debug: true,
    allowedHosts: ['demo.test', 'localhost', '127.0.0.1'],
    httpsEnabled: true,
    certificatePath: '',
    staticPath: 'static',
    mediaPath: 'media',
    database: { type: 'postgres', port: 54329, name: 'demo', username: 'demo', password: '' },
    cache: { type: 'none', port: 6389 },
    status: 'stopped',
    environmentVars: {
      DEBUG: 'True',
      DB_NAME: 'demo',
      DB_PASSWORD: '********',
      SECRET_KEY: '********',
    },
    createdAt: new Date().toISOString(),
    runtimeMode: 'uv',
    ...overrides,
  };
}

const projects: Project[] = [
  makeProject({
    name: 'Acme Blog',
    domain: 'blog.test',
    path: '/Users/dev/projects/acme-blog',
    aliases: ['api.blog.test'],
    status: 'running',
  }),
  makeProject({
    name: 'Storefront',
    domain: 'store.test',
    path: '/Users/dev/projects/storefront',
    port: 8002,
    database: { type: 'mysql', port: 33069, name: 'store', username: 'store', password: '' },
  }),
  makeProject({
    name: 'Intranet Portal',
    domain: 'portal.test',
    path: '/Users/dev/projects/portal',
    port: 8003,
    httpsEnabled: false,
    database: { type: 'none', port: 0, name: '', username: '', password: '' },
  }),
];

const proxyStatus: ProxyStatus = {
  proxyHttpPort: 8080,
  proxyPort: 8443,
  standardPortsEnabled: true,
  standardHttpActive: true,
  standardHttpsActive: true,
  proxyHttpActive: true,
  proxyHttpsActive: true,
};

const settings = {
  caInstalled: true,
  defaultPython: '3.12',
  autoStartProjects: [] as string[],
  proxyPort: 8443,
  proxyHttpPort: 8080,
  anyDomainOverrideEnabled: false,
  standardPortsEnabled: true,
  restoreOnQuit: true,
};

const ok = { success: true, output: 'ok', error: undefined };

function find(id: string): Project {
  const project = projects.find((item) => item.id === id);
  if (!project) {
    throw new Error('Project not found');
  }
  return project;
}

export function createMockApi(): Api {
  return {
    getProjects: async () => {
      await delay(200);
      return projects.map((project) => ({ ...project }));
    },
    addProject: async (project) => {
      await delay(500);
      projects.push(makeProject({ ...project, status: 'stopped' } as Partial<Project>));
    },
    updateProject: async (id, updates) => {
      await delay(200);
      Object.assign(find(id), updates);
    },
    deleteProject: async (id) => {
      await delay(300);
      const index = projects.findIndex((item) => item.id === id);
      if (index >= 0) projects.splice(index, 1);
    },
    startProject: async (id) => {
      const project = find(id);
      project.status = 'starting';
      await delay(900);
      project.status = 'running';
      return { message: 'Project started' };
    },
    stopProject: async (id) => {
      const project = find(id);
      project.status = 'stopping';
      await delay(600);
      project.status = 'stopped';
    },
    restartProject: async (id) => {
      const project = find(id);
      project.status = 'starting';
      await delay(900);
      project.status = 'running';
    },
    runMigrate: async () => {
      await delay(1200);
      return { ...ok, output: 'Operations to perform:\n  Apply all migrations: OK' };
    },
    runCollectstatic: async () => {
      await delay(1000);
      return { ...ok, output: '128 static files copied.' };
    },
    runCreateSuperuser: async () => {
      await delay(800);
      return { ...ok };
    },
    runTests: async () => {
      await delay(1500);
      return { ...ok };
    },
    openShell: async () => {
      await delay(300);
    },
    openDatabaseShell: async () => {
      await delay(300);
    },
    openVSCode: async () => {
      await delay(300);
    },
    openInBrowser: async () => {
      await delay(150);
    },
    getSettings: async () => {
      await delay(150);
      return { ...settings };
    },
    getProxyStatus: async () => {
      await delay(120);
      return { ...proxyStatus };
    },
    reloadProxy: async () => {
      await delay(700);
      return { ...ok, output: 'Caddy reloaded' };
    },
    disableStandardPorts: async () => {
      await delay(500);
      return { ...ok };
    },
    getHelperStatus: async () => {
      await delay(150);
      return {
        installed: true,
        running: true,
        socketPath: '/var/run/djamp-pro/helper.sock',
        label: 'com.djamppro.helper',
        standardHttpActive: true,
        standardHttpsActive: true,
      };
    },
    installHelper: async () => {
      await delay(1200);
      return { ...ok };
    },
    uninstallHelper: async () => {
      await delay(800);
      return { ...ok };
    },
    updateSettings: async (updates) => {
      await delay(250);
      Object.assign(settings, updates);
    },
    addDomain: async () => {
      await delay(200);
    },
    removeDomain: async () => {
      await delay(200);
    },
    syncHosts: async () => {
      await delay(600);
      return { ...ok, output: 'Hosts file updated' };
    },
    clearHosts: async () => {
      await delay(600);
      return { ...ok, output: 'Hosts file cleared' };
    },
    generateCertificate: async (domain) => {
      await delay(900);
      return {
        domain,
        certificatePath: `~/certs/${domain}.crt`,
        keyPath: `~/certs/${domain}.key`,
        expiresAt: new Date(Date.now() + 365 * 24 * 3600 * 1000).toISOString(),
        isValid: true,
      };
    },
    checkCertificateStatus: async (domain) => {
      await delay(300);
      return {
        domain,
        certificatePath: `~/certs/${domain}.crt`,
        keyPath: `~/certs/${domain}.key`,
        expiresAt: new Date(Date.now() + 365 * 24 * 3600 * 1000).toISOString(),
        isValid: true,
      };
    },
    installRootCA: async () => {
      await delay(1000);
    },
    uninstallRootCA: async () => {
      await delay(700);
      return { ...ok };
    },
    checkRootCAStatus: async () => {
      await delay(200);
      return { installed: true, valid: true };
    },
    startDatabase: async () => {
      await delay(700);
    },
    stopDatabase: async () => {
      await delay(500);
    },
    testDatabaseConnection: async () => {
      await delay(600);
      return { ...ok, output: 'accepting connections' };
    },
    getDatabaseAdminUrl: async (projectId) => {
      const project = find(projectId);
      return { url: `https://${project.domain}/phpmyadmin/` };
    },
    getLogs: async (_projectId, source) => {
      await delay(180);
      const now = new Date().toISOString();
      return [
        `[${now}] [${source}] Watching for file changes with StatReloader`,
        `[${now}] [${source}] "GET / HTTP/1.1" 200 12403`,
        `[${now}] [${source}] "GET /static/app.css HTTP/1.1" 200 5210`,
        `[${now}] [${source}] "POST /api/login HTTP/1.1" 302 0`,
      ].join('\n');
    },
    detectDjangoProject: async (path) => {
      await delay(700);
      return {
        found: true,
        managePyPath: `${path}/manage.py`,
        settingsModules: ['config.settings', 'config.settings.local'],
      };
    },
    createVenv: async () => {
      await delay(1500);
    },
    installDependencies: async () => {
      await delay(2000);
      return { ...ok };
    },
  };
}
