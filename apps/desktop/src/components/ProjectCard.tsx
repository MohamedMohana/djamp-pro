import { useState, type ReactNode } from 'react';
import { Trash2, ExternalLink, PlayCircle, Database, Terminal, Code } from 'lucide-react';
import type { Project, ProxyStatus } from '../types';
import { useI18n } from '../i18n';
import { cn, computeProjectUrl, getStatusColor, statusDotClass } from '../utils';
import { api } from '../services/api';
import { useToast } from '../toast';
import Spinner from './Spinner';

type BusyAction = 'migrate' | 'collectstatic' | 'shell' | 'dbshell' | 'dbadmin' | null;

interface ProjectCardProps {
  project: Project;
  onDelete: () => void;
}

interface InspectorRowProps {
  label: string;
  value: ReactNode;
}

function InspectorRow({ label, value }: InspectorRowProps) {
  return (
    <div className="grid gap-3 py-2 md:grid-cols-[11rem_minmax(0,1fr)]">
      <div className="text-[12px] font-medium text-[var(--text-2)]">
        {label}
      </div>
      <div className="min-w-0 text-[13px] text-[var(--text-1)]">{value}</div>
    </div>
  );
}

function InspectorSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mamp-section">
      <div className="mamp-section-title">{title}</div>
      <div>{children}</div>
    </section>
  );
}

export default function ProjectCard({ project, onDelete }: ProjectCardProps) {
  const { t } = useI18n();
  const toast = useToast();
  const [busyAction, setBusyAction] = useState<BusyAction>(null);
  const runtimeMode = project.runtimeMode || 'uv';
  const framework = project.framework || 'django';
  const projectUrl = `${project.httpsEnabled ? 'https' : 'http'}://${project.domain}`;

  const commandDetails = (output?: string, error?: string) =>
    [error, output].filter(Boolean).join('\n').trim() || undefined;

  const handleMigrate = async () => {
    setBusyAction('migrate');
    try {
      const result = await api.runMigrate(project.id);
      if (!result.success) {
        toast.error(t.projectCard.migrateFailed, commandDetails(result.output, result.error));
        return;
      }
      toast.success(t.projectCard.migrateSuccess);
    } catch (error) {
      console.error('Migration failed:', error);
      toast.error(t.projectCard.migrateError);
    } finally {
      setBusyAction(null);
    }
  };

  const handleCollectstatic = async () => {
    setBusyAction('collectstatic');
    try {
      const result = await api.runCollectstatic(project.id);
      if (!result.success) {
        toast.error(t.projectCard.collectstaticFailed, commandDetails(result.output, result.error));
        return;
      }
      toast.success(t.projectCard.collectstaticSuccess);
    } catch (error) {
      console.error('Collectstatic failed:', error);
      toast.error(t.projectCard.collectstaticError);
    } finally {
      setBusyAction(null);
    }
  };

  const handleOpenShell = async () => {
    setBusyAction('shell');
    try {
      await api.openShell(project.id);
    } catch (error) {
      console.error('Failed to open shell:', error);
      toast.error(t.projectCard.openDbShellError);
    } finally {
      setBusyAction(null);
    }
  };

  const handleOpenDbShell = async () => {
    setBusyAction('dbshell');
    try {
      await api.openDatabaseShell(project.id);
    } catch (error) {
      console.error('Failed to open database shell:', error);
      toast.error(t.projectCard.openDbShellError);
    } finally {
      setBusyAction(null);
    }
  };

  const handleOpenDbAdmin = async () => {
    if (project.database.type !== 'postgres') {
      toast.info(t.projectCard.dbAdminPostgresOnly);
      return;
    }

    if (project.status !== 'running') {
      toast.info(t.projectCard.dbAdminStartFirst);
      return;
    }

    setBusyAction('dbadmin');
    try {
      let proxyStatus: ProxyStatus | null = null;
      try {
        proxyStatus = await api.getProxyStatus();
      } catch (error) {
        console.error('Failed to detect proxy status for DB admin URL:', error);
      }
      let url = computeProjectUrl(project, proxyStatus, '/phpmyadmin/');

      try {
        const response = await api.getDatabaseAdminUrl(project.id);
        if (response?.url) {
          url = response.url;
        }
      } catch (error) {
        console.error('Failed to resolve DB admin URL from backend, using computed URL:', error);
      }

      try {
        await api.openInBrowser(url);
        return;
      } catch (error) {
        console.error('Native open failed for DB admin, trying window.open fallback:', error);
      }

      const opened = window.open(url, '_blank');
      if (opened) {
        return;
      }

      try {
        await navigator.clipboard.writeText(url);
      } catch {
        // Clipboard may be unavailable; continue with the manual URL toast.
      }
      toast.info(t.projectCard.dbAdminManualOpen(url));
    } finally {
      setBusyAction(null);
    }
  };

  const handleOpenVSCode = async () => {
    try {
      await api.openVSCode(project.id);
    } catch (error) {
      console.error('Failed to open VS Code:', error);
      toast.error(t.app.unknownError);
    }
  };

  return (
    <div className="space-y-5">
      <InspectorSection title={t.projectCard.sectionProject}>
        <InspectorRow
          label={t.projectCard.projectPath}
          value={<span className="block truncate font-mono text-[13px]">{project.path}</span>}
        />
        <InspectorRow label={t.projectCard.framework} value={t.common.frameworks[framework]} />
        {framework === 'django' ? (
          <InspectorRow
            label={t.projectCard.settingsModule}
            value={<span className="font-mono text-[13px]">{project.settingsModule}</span>}
          />
        ) : (
          <InspectorRow
            label={t.projectCard.appModule}
            value={<span className="font-mono text-[13px]">{project.appModule || '--'}</span>}
          />
        )}
        <InspectorRow label={t.projectCard.pythonVersion} value={project.pythonVersion} />
        <InspectorRow label={t.projectCard.runtimeMode} value={t.common.runtimeModes[runtimeMode]} />
        <InspectorRow
          label={t.projectCard.statusLabel}
          value={
            <span
              className={cn(
                'inline-flex items-center gap-2 rounded-full bg-white/[0.06] px-2.5 py-1 text-[12px]',
                getStatusColor(project.status),
              )}
            >
              <span className={statusDotClass(project.status)} />
              {t.common.status[project.status]}
            </span>
          }
        />
        <InspectorRow
          label={t.projectCard.debugMode}
          value={
            <span
              className={cn(
                'inline-flex rounded-full px-2.5 py-1 text-[12px] font-medium',
                project.debug
                  ? 'bg-emerald-500/15 text-emerald-300'
                  : 'bg-red-500/15 text-red-300',
              )}
            >
              {project.debug ? t.projectCard.debugOn : t.projectCard.debugOff}
            </span>
          }
        />
      </InspectorSection>

      <InspectorSection title={t.projectCard.sectionAccess}>
        <InspectorRow
          label={t.projectCard.primaryDomain}
          value={<span className="font-mono text-[13px]">{project.domain}</span>}
        />
        <InspectorRow
          label={t.projectCard.urlLabel}
          value={<span className="font-mono text-[13px]">{projectUrl}</span>}
        />
        <InspectorRow
          label={t.projectCard.sslLabel}
          value={project.httpsEnabled ? t.projectCard.httpsEnabled : t.projectCard.httpsDisabled}
        />
        <InspectorRow
          label={t.projectCard.aliases}
          value={
            project.aliases.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {project.aliases.map((alias) => (
                  <span
                    key={alias}
                    className="rounded-full bg-white/[0.06] px-2.5 py-1 font-mono text-[12px]"
                  >
                    {alias}
                  </span>
                ))}
              </div>
            ) : (
              <span className="text-[var(--text-2)]">{t.projectCard.noAliases}</span>
            )
          }
        />
      </InspectorSection>

      <InspectorSection title={t.projectCard.database}>
        {project.database.type !== 'none' ? (
          <>
            <InspectorRow label={t.projectCard.type} value={t.common.databaseTypes[project.database.type]} />
            <InspectorRow label={t.projectCard.port} value={project.database.port} />
            <InspectorRow label={t.projectCard.databaseName} value={project.database.name || '--'} />
            <InspectorRow label={t.projectCard.username} value={project.database.username || '--'} />
            <div className="pt-3">
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={handleOpenDbShell}
                  disabled={project.status !== 'running' || busyAction !== null}
                  className="mamp-inline-action disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {busyAction === 'dbshell' ? <Spinner size={15} /> : <Database size={15} />}
                  {t.projectCard.openDbShell}
                </button>
                <button
                  onClick={handleOpenDbAdmin}
                  disabled={
                    project.status !== 'running' ||
                    project.database.type !== 'postgres' ||
                    busyAction !== null
                  }
                  className="mamp-inline-action disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {busyAction === 'dbadmin' ? <Spinner size={15} /> : <ExternalLink size={15} />}
                  {t.projectCard.openDbAdmin}
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="text-[13px] text-[var(--text-2)]">{t.projectCard.noDatabase}</div>
        )}
      </InspectorSection>

      <InspectorSection title={t.projectCard.quickActions}>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleMigrate}
            disabled={project.status !== 'running' || busyAction !== null}
            className="mamp-inline-action disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busyAction === 'migrate' ? <Spinner size={15} /> : <PlayCircle size={15} />}
            {t.projectCard.migrate}
          </button>
          {framework === 'django' && (
            <button
              onClick={handleCollectstatic}
              disabled={project.status !== 'running' || busyAction !== null}
              className="mamp-inline-action disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busyAction === 'collectstatic' ? <Spinner size={15} /> : <ExternalLink size={15} />}
              {t.projectCard.collectstatic}
            </button>
          )}
          <button
            onClick={handleOpenShell}
            disabled={project.status !== 'running' || busyAction !== null}
            className="mamp-inline-action disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busyAction === 'shell' ? <Spinner size={15} /> : <Terminal size={15} />}
            {t.projectCard.shell}
          </button>
          <button
            onClick={handleOpenDbShell}
            disabled={
              project.status !== 'running' || project.database.type === 'none' || busyAction !== null
            }
            className="mamp-inline-action disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busyAction === 'dbshell' ? <Spinner size={15} /> : <Database size={15} />}
            {t.projectCard.dbShell}
          </button>
          <button
            onClick={handleOpenVSCode}
            className="mamp-inline-action"
          >
            <Code size={15} />
            {t.projectCard.vsCode}
          </button>
        </div>
      </InspectorSection>

      <section className="rounded-[10px] border border-red-500/20 bg-red-950/20 px-[1.1rem] py-4">
        <div className="mamp-section-title text-red-300">{t.projectCard.dangerZone}</div>
        <p className="mb-3 text-[13px] text-red-100/75">{t.app.deleteProjectNote}</p>
        <button
          onClick={onDelete}
          className="inline-flex items-center gap-2 rounded-[7px] border border-red-400/30 bg-red-500/15 px-3 py-1.5 text-[13px] font-medium text-red-100 transition hover:bg-red-500/25"
        >
          <Trash2 size={15} />
          {t.projectCard.deleteProject}
        </button>
      </section>
    </div>
  );
}
