import type { ReactNode } from 'react';
import { Trash2, ExternalLink, PlayCircle, Database, Terminal, Code } from 'lucide-react';
import type { Project } from '../types';
import { useI18n } from '../i18n';
import { cn, getStatusColor, getStatusIcon } from '../utils';
import { api } from '../services/api';

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
    <div className="grid gap-3 border-b border-white/6 py-3 last:border-b-0 md:grid-cols-[10rem_minmax(0,1fr)]">
      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--mamp-text-dim)]">
        {label}
      </div>
      <div className="min-w-0 text-sm text-[var(--mamp-text)]">{value}</div>
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
  const runtimeMode = project.runtimeMode || 'uv';
  const projectUrl = `${project.httpsEnabled ? 'https' : 'http'}://${project.domain}`;

  const commandErrorMessage = (fallback: string, output?: string, error?: string): string => {
    const details = [error, output].filter(Boolean).join('\n').trim();
    return details ? `${fallback}:\n\n${details}` : fallback;
  };

  const handleMigrate = async () => {
    try {
      const result = await api.runMigrate(project.id);
      if (!result.success) {
        alert(commandErrorMessage(t.projectCard.migrateFailed, result.output, result.error));
        return;
      }
      alert(t.projectCard.migrateSuccess);
    } catch (error) {
      console.error('Migration failed:', error);
      alert(t.projectCard.migrateError);
    }
  };

  const handleCollectstatic = async () => {
    try {
      const result = await api.runCollectstatic(project.id);
      if (!result.success) {
        alert(commandErrorMessage(t.projectCard.collectstaticFailed, result.output, result.error));
        return;
      }
      alert(t.projectCard.collectstaticSuccess);
    } catch (error) {
      console.error('Collectstatic failed:', error);
      alert(t.projectCard.collectstaticError);
    }
  };

  const handleOpenShell = async () => {
    try {
      await api.openShell(project.id);
    } catch (error) {
      console.error('Failed to open shell:', error);
    }
  };

  const handleOpenDbShell = async () => {
    try {
      await api.openDatabaseShell(project.id);
    } catch (error) {
      console.error('Failed to open database shell:', error);
      alert(t.projectCard.openDbShellError);
    }
  };

  const handleOpenDbAdmin = async () => {
    if (project.database.type !== 'postgres') {
      alert(t.projectCard.dbAdminPostgresOnly);
      return;
    }

    if (project.status !== 'running') {
      alert(t.projectCard.dbAdminStartFirst);
      return;
    }

    const protocol = project.httpsEnabled ? 'https' : 'http';
    let url = `${protocol}://${project.domain}/phpmyadmin/`;

    try {
      const status = await api.getProxyStatus();
      const proxyActive = project.httpsEnabled ? status.proxyHttpsActive : status.proxyHttpActive;
      const standardActive = project.httpsEnabled ? status.standardHttpsActive : status.standardHttpActive;

      if (!proxyActive || !standardActive) {
        const port = project.httpsEnabled ? status.proxyPort : status.proxyHttpPort;
        url = `${protocol}://${project.domain}:${port}/phpmyadmin/`;
      }
    } catch (error) {
      console.error('Failed to detect proxy status for DB admin URL:', error);
    }

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
      // Clipboard may be unavailable; continue with manual URL alert.
    }
    alert(t.projectCard.dbAdminManualOpen(url));
  };

  const handleOpenVSCode = async () => {
    try {
      await api.openVSCode(project.id);
    } catch (error) {
      console.error('Failed to open VS Code:', error);
    }
  };

  return (
    <div className="space-y-5">
      <InspectorSection title={t.projectCard.sectionProject}>
        <InspectorRow
          label={t.projectCard.projectPath}
          value={<span className="block truncate font-mono text-[13px]">{project.path}</span>}
        />
        <InspectorRow
          label={t.projectCard.settingsModule}
          value={<span className="font-mono text-[13px]">{project.settingsModule}</span>}
        />
        <InspectorRow label={t.projectCard.pythonVersion} value={project.pythonVersion} />
        <InspectorRow label={t.projectCard.runtimeMode} value={t.common.runtimeModes[runtimeMode]} />
        <InspectorRow
          label={t.projectCard.statusLabel}
          value={
            <span
              className={cn(
                'inline-flex items-center gap-2 rounded-full border border-white/8 bg-black/15 px-3 py-1',
                getStatusColor(project.status),
              )}
            >
              <span>{getStatusIcon(project.status)}</span>
              {t.common.status[project.status]}
            </span>
          }
        />
        <InspectorRow
          label={t.projectCard.debugMode}
          value={
            <span
              className={cn(
                'inline-flex rounded-full px-3 py-1 text-xs font-semibold',
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
                    className="rounded-md border border-white/8 bg-black/15 px-2.5 py-1 font-mono text-[12px]"
                  >
                    {alias}
                  </span>
                ))}
              </div>
            ) : (
              <span className="text-[var(--mamp-text-muted)]">{t.projectCard.noAliases}</span>
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
            <div className="border-t border-white/6 pt-4">
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={handleOpenDbShell}
                  disabled={project.status !== 'running'}
                  className="mamp-inline-action disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Database size={15} />
                  {t.projectCard.openDbShell}
                </button>
                <button
                  onClick={handleOpenDbAdmin}
                  disabled={project.status !== 'running' || project.database.type !== 'postgres'}
                  className="mamp-inline-action disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <ExternalLink size={15} />
                  {t.projectCard.openDbAdmin}
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="text-sm text-[var(--mamp-text-muted)]">{t.projectCard.noDatabase}</div>
        )}
      </InspectorSection>

      <InspectorSection title={t.projectCard.quickActions}>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleMigrate}
            disabled={project.status !== 'running'}
            className="mamp-inline-action disabled:cursor-not-allowed disabled:opacity-50"
          >
            <PlayCircle size={15} />
            {t.projectCard.migrate}
          </button>
          <button
            onClick={handleCollectstatic}
            disabled={project.status !== 'running'}
            className="mamp-inline-action disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ExternalLink size={15} />
            {t.projectCard.collectstatic}
          </button>
          <button
            onClick={handleOpenShell}
            disabled={project.status !== 'running'}
            className="mamp-inline-action disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Terminal size={15} />
            {t.projectCard.shell}
          </button>
          <button
            onClick={handleOpenDbShell}
            disabled={project.status !== 'running' || project.database.type === 'none'}
            className="mamp-inline-action disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Database size={15} />
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

      <section className="rounded-xl border border-red-500/20 bg-red-950/20 p-4">
        <div className="mamp-section-title text-red-300">{t.projectCard.dangerZone}</div>
        <p className="mb-4 text-sm text-red-100/75">{t.app.deleteProjectNote}</p>
        <button
          onClick={onDelete}
          className="inline-flex items-center gap-2 rounded-md border border-red-400/30 bg-red-500/15 px-3 py-2 text-sm font-semibold text-red-100 transition hover:bg-red-500/25"
        >
          <Trash2 size={15} />
          {t.projectCard.deleteProject}
        </button>
      </section>
    </div>
  );
}
