import { Folder, Globe, Plus } from 'lucide-react';
import type { Project } from '../types';
import { useI18n } from '../i18n';
import { cn, statusDotClass } from '../utils';

interface ProjectListProps {
  projects: Project[];
  selectedId?: string;
  onSelect: (project: Project) => void;
  onAddProject: () => void;
  loading: boolean;
}

function SkeletonRow() {
  return (
    <div className="flex w-full items-center gap-3 px-3 py-3" aria-hidden>
      <div className="skeleton h-8 w-8 shrink-0" />
      <div className="min-w-0 flex-1 space-y-2">
        <div className="skeleton h-3.5 w-2/3" />
        <div className="skeleton h-3 w-1/2" />
      </div>
    </div>
  );
}

export default function ProjectList({
  projects,
  selectedId,
  onSelect,
  onAddProject,
  loading,
}: ProjectListProps) {
  const { t } = useI18n();

  if (loading) {
    return (
      <div className="divide-y divide-white/5" role="status" aria-label={t.projectList.loading}>
        <SkeletonRow />
        <SkeletonRow />
        <SkeletonRow />
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div className="mx-3 my-4 rounded-xl border border-dashed border-white/12 bg-black/10 px-4 py-8 text-center">
        <Folder size={36} className="mx-auto mb-3 text-[var(--mamp-text-dim)]" />
        <p className="text-sm font-semibold text-[var(--mamp-text)]">{t.projectList.emptyTitle}</p>
        <p className="mt-1 text-xs text-[var(--mamp-text-muted)]">{t.projectList.emptyDescription}</p>
        <button onClick={onAddProject} className="mamp-button-primary mx-auto mt-4 !px-3 !py-2 text-sm">
          <Plus size={15} />
          {t.projectList.addFirstProject}
        </button>
      </div>
    );
  }

  return (
    <div className="divide-y divide-white/5">
      {projects.map((project) => {
        const isSelected = selectedId === project.id;

        return (
          <button
            key={project.id}
            onClick={() => onSelect(project)}
            aria-current={isSelected || undefined}
            className={cn(
              'group flex w-full items-center gap-3 px-3 py-3 text-start transition',
              isSelected
                ? 'bg-[var(--mamp-accent)] text-white'
                : 'text-[var(--mamp-text)] hover:bg-white/5',
            )}
          >
            <div
              className={cn(
                'flex h-8 w-8 items-center justify-center rounded-md border text-xs',
                isSelected
                  ? 'border-white/15 bg-white/10 text-white'
                  : 'border-white/8 bg-white/5 text-[var(--mamp-text-muted)]',
              )}
            >
              <Globe size={14} />
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-3">
                <span className="truncate text-sm font-semibold">{project.name}</span>
                <span
                  className={statusDotClass(project.status)}
                  title={t.common.status[project.status]}
                />
              </div>
              <div
                className={cn(
                  'mt-0.5 truncate text-xs',
                  isSelected ? 'text-white/80' : 'text-[var(--mamp-text-muted)]',
                )}
              >
                {project.domain}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
