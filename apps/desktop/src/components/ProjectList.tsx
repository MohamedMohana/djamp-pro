import { Globe, Folder } from 'lucide-react';
import { Project } from '../types';
import { getStatusIcon, getStatusColor } from '../utils';
import ProjectAvatar from './ProjectAvatar';

interface ProjectListProps {
  projects: Project[];
  selectedId?: string;
  onSelect: (project: Project) => void;
  loading: boolean;
}

export default function ProjectList({ projects, selectedId, onSelect, loading }: ProjectListProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-gray-500">Loading projects...</div>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div className="text-center py-8">
        <Folder size={48} className="mx-auto text-gray-600 mb-3" />
        <p className="text-gray-500">No projects yet</p>
        <p className="text-sm text-gray-600 mt-1">Add your first Django project</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {projects.map((project) => (
        <button
          key={project.id}
          onClick={() => onSelect(project)}
          className={`w-full text-left p-3 rounded-lg transition-colors ${
            selectedId === project.id
              ? 'bg-brand-600 text-white'
              : 'bg-gray-700 hover:bg-gray-600'
          }`}
        >
          <div className="flex items-center gap-3">
            <ProjectAvatar name={project.name} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-medium truncate">{project.name}</span>
                <span className={getStatusColor(project.status)}>
                  {getStatusIcon(project.status)}
                </span>
              </div>
              <div className="flex items-center gap-1 text-xs opacity-80 truncate">
                <Globe size={12} />
                {project.domain}
              </div>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}
