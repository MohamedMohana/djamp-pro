import { useState, useEffect } from 'react';
import { Play, Square, Settings, Plus, RefreshCw, Database, Globe, Shield, Terminal } from 'lucide-react';
import { api } from './services/api';
import { Project } from './types';
import { cn, getStatusColor, getStatusIcon } from './utils';

import ProjectList from './components/ProjectList';
import ProjectCard from './components/ProjectCard';
import AddProjectModal from './components/AddProjectModal';
import SettingsPanel from './components/SettingsPanel';

function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'projects' | 'logs' | 'environment'>('projects');

  useEffect(() => {
    loadProjects();
    const interval = setInterval(loadProjects, 2000);
    return () => clearInterval(interval);
  }, []);

  const loadProjects = async () => {
    try {
      const loaded = await api.getProjects();
      setProjects(loaded);
      setLoading(false);
    } catch (error) {
      console.error('Failed to load projects:', error);
      setLoading(false);
    }
  };

  const handleStartProject = async (id: string) => {
    try {
      await api.startProject(id);
      await loadProjects();
    } catch (error) {
      console.error('Failed to start project:', error);
    }
  };

  const handleStopProject = async (id: string) => {
    try {
      await api.stopProject(id);
      await loadProjects();
    } catch (error) {
      console.error('Failed to stop project:', error);
    }
  };

  const handleRestartProject = async (id: string) => {
    try {
      await api.restartProject(id);
      await loadProjects();
    } catch (error) {
      console.error('Failed to restart project:', error);
    }
  };

  const handleDeleteProject = async (id: string) => {
    if (confirm('Are you sure you want to delete this project?')) {
      try {
        await api.deleteProject(id);
        await loadProjects();
        if (selectedProject?.id === id) {
          setSelectedProject(null);
        }
      } catch (error) {
        console.error('Failed to delete project:', error);
      }
    }
  };

  const handleAddProject = () => {
    setShowAddModal(true);
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="flex h-screen">
        {/* Sidebar */}
        <div className="w-80 bg-gray-800 border-r border-gray-700 flex flex-col">
          <div className="p-4 border-b border-gray-700">
            <h1 className="text-2xl font-bold text-brand-400">DJANGOForge</h1>
            <p className="text-sm text-gray-400 mt-1">Django Development Manager</p>
          </div>

          <div className="p-4 border-b border-gray-700">
            <button
              onClick={handleAddProject}
              className="w-full bg-brand-600 hover:bg-brand-700 text-white font-medium py-2 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors"
            >
              <Plus size={18} />
              Add Project
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            <ProjectList
              projects={projects}
              selectedId={selectedProject?.id}
              onSelect={setSelectedProject}
              loading={loading}
            />
          </div>

          <div className="p-4 border-t border-gray-700">
            <button
              onClick={() => setShowSettings(true)}
              className="w-full bg-gray-700 hover:bg-gray-600 text-white font-medium py-2 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors"
            >
              <Settings size={18} />
              Settings
            </button>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex flex-col">
          {selectedProject ? (
            <>
              {/* Project Header */}
              <div className="bg-gray-800 border-b border-gray-700 p-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-3xl font-bold">{selectedProject.name}</h2>
                    <div className="flex items-center gap-4 mt-2 text-gray-400">
                      <span className={cn('flex items-center gap-1', getStatusColor(selectedProject.status))}>
                        <span>{getStatusIcon(selectedProject.status)}</span>
                        {selectedProject.status}
                      </span>
                      <span className="flex items-center gap-1">
                        <Globe size={16} />
                        {selectedProject.httpsEnabled ? 'https://' : 'http://'}{selectedProject.domain}
                      </span>
                      {selectedProject.database.type !== 'none' && (
                        <span className="flex items-center gap-1">
                          <Database size={16} />
                          {selectedProject.database.type}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleRestartProject(selectedProject.id)}
                      className="bg-gray-700 hover:bg-gray-600 text-white p-2 rounded-lg transition-colors"
                      title="Restart"
                    >
                      <RefreshCw size={20} />
                    </button>
                    {selectedProject.status === 'running' ? (
                      <button
                        onClick={() => handleStopProject(selectedProject.id)}
                        className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors"
                      >
                        <Square size={18} />
                        Stop
                      </button>
                    ) : (
                      <button
                        onClick={() => handleStartProject(selectedProject.id)}
                        className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors"
                      >
                        <Play size={18} />
                        Start
                      </button>
                    )}
                  </div>
                </div>

                {/* Tabs */}
                <div className="flex gap-4 mt-6 border-b border-gray-700">
                  {(['projects', 'logs', 'environment'] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={cn(
                        'pb-3 px-2 font-medium transition-colors capitalize',
                        activeTab === tab
                          ? 'text-brand-400 border-b-2 border-brand-400'
                          : 'text-gray-400 hover:text-white'
                      )}
                    >
                      {tab}
                    </button>
                  ))}
                </div>
              </div>

              {/* Tab Content */}
              <div className="flex-1 overflow-y-auto p-6">
                {activeTab === 'projects' && (
                  <ProjectCard
                    project={selectedProject}
                    onDelete={() => handleDeleteProject(selectedProject.id)}
                  />
                )}
                {activeTab === 'logs' && (
                  <div className="bg-gray-800 rounded-lg p-4 h-full overflow-auto">
                    <div className="font-mono text-sm text-gray-300">
                      {/* Logs would be rendered here */}
                      <p className="text-gray-500">No logs available yet</p>
                    </div>
                  </div>
                )}
                {activeTab === 'environment' && (
                  <div className="bg-gray-800 rounded-lg p-6">
                    <h3 className="text-xl font-semibold mb-4">Environment Variables</h3>
                    <div className="space-y-3">
                      {Object.entries(selectedProject.environmentVars).map(([key, value]) => (
                        <div key={key} className="flex items-center gap-4">
                          <span className="w-48 text-gray-400 font-mono">{key}</span>
                          <span className="flex-1 bg-gray-700 px-3 py-2 rounded font-mono text-sm">
                            {value}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <Globe size={64} className="mx-auto text-gray-600 mb-4" />
                <h2 className="text-2xl font-semibold text-gray-400 mb-2">No Project Selected</h2>
                <p className="text-gray-500">Select a project from the sidebar or add a new one</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {showAddModal && (
        <AddProjectModal onClose={() => setShowAddModal(false)} onAdd={loadProjects} />
      )}

      {showSettings && (
        <SettingsPanel onClose={() => setShowSettings(false)} />
      )}
    </div>
  );
}

export default App;
