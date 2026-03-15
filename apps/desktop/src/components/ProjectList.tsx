import { Globe, Folder } from 'lucide-react';
import { Project } from '../types';
import { useI18n } from '../i18n';
import { getStatusIcon, getStatusColor } from '../utils';
import ProjectAvatar from './ProjectAvatar';

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
      <div className="flex items-center justify-center py-8">
        <div className="text-slate-400">{t.projectList.loading}</div>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div className="rounded-xl border border-white/10 bg-slate-900/40 px-4 py-8 text-center">
        <Folder size={44} className="mx-auto mb-3 text-slate-500" />
        <p className="text-slate-300">{t.projectList.emptyTitle}</p>
        <p className="mt-1 text-sm text-slate-500">{t.projectList.emptyDescription}</p>
      </div>
    );
  }

  return (
    <div className="space-y-2.5">
      {projects.map((project) => {
        const isSelected = selectedId === project.id;
        return (
          <button
            key={project.id}
            onClick={() => onSelect(project)}
            className={`w-full rounded-xl border p-3 text-start transition ${
              isSelected
                ? 'border-brand-400/60 bg-gradient-to-r from-brand-600/55 to-brand-500/40 text-white shadow-[0_10px_26px_rgba(36,105,224,0.35)]'
                : 'border-white/10 bg-slate-800/65 text-slate-100 hover:border-white/20 hover:bg-slate-700/70'
            }`}
          >
            <div className="flex items-center gap-3">
              <ProjectAvatar name={project.name} />
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="truncate font-semibold tracking-tight">{project.name}</span>
                  <span className={getStatusColor(project.status)}>{getStatusIcon(project.status)}</span>
                </div>
                <div className="flex items-center gap-1 truncate text-xs opacity-80">
                  <Globe size={12} />
                  {project.domain}
                </div>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
