import { Folder, Globe } from 'lucide-react';
import type { Project } from '../types';
import { useI18n } from '../i18n';
import { cn, getStatusColor, getStatusIcon } from '../utils';

interface ProjectListProps {
  projects: Project[];
  selectedId?: string;
  onSelect: (project: Project) => void;
  loading: boolean;
}

export default function ProjectList({ projects, selectedId, onSelect, loading }: ProjectListProps) {
  const { t } = useI18n();

  if (loading) {
    return (
      <div className="flex items-center justify-center px-4 py-10">
        <div className="text-sm text-[var(--mamp-text-muted)]">{t.projectList.loading}</div>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div className="mx-3 my-4 rounded-xl border border-white/8 bg-black/10 px-4 py-8 text-center">
        <Folder size={36} className="mx-auto mb-3 text-[var(--mamp-text-dim)]" />
        <p className="text-sm font-semibold text-[var(--mamp-text)]">{t.projectList.emptyTitle}</p>
        <p className="mt-1 text-xs text-[var(--mamp-text-muted)]">{t.projectList.emptyDescription}</p>
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
                  className={cn(
                    'text-[11px]',
                    isSelected ? 'text-white' : getStatusColor(project.status),
                  )}
                >
                  {getStatusIcon(project.status)}
                </span>
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
