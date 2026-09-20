import React, { useEffect, useState } from "react";
import { CheckSquare, Cpu, FileCode, FolderGit2, GitBranch, Terminal } from "lucide-react";
import { nexoraApi, OrchestrationProject } from "../../../api/client";

const files = [
  { name: "nexora_os/backend/core/runtime.py", size: "25.9 KB", type: "Runtime" },
  { name: "nexora_os/backend/core/cognitive_intelligence.py", size: "11.3 KB", type: "Brain" },
  { name: "nexora_os/backend/voice/pipeline.py", size: "7.8 KB", type: "Voice" },
  { name: "nexora_os/backend/memory/conversation.py", size: "4.2 KB", type: "Memory" },
  { name: "nexora_os/backend/knowledge/manager.py", size: "9.1 KB", type: "Knowledge" },
  { name: "nexora_os/frontend/src/app/App.tsx", size: "5.1 KB", type: "UI" },
];

export function ProjectsPage() {
  const [selectedFile, setSelectedFile] = useState(files[0].name);
  const [projects, setProjects] = useState<OrchestrationProject[]>([]);
  const [projectError, setProjectError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const result = await nexoraApi.orchestrationProjects();
        if (active) {
          setProjects(result.projects ?? []);
          setProjectError(null);
        }
      } catch (error) {
        if (active) setProjectError(error instanceof Error ? error.message : "Project state unavailable");
      }
    };
    refresh();
    const timer = window.setInterval(refresh, 3000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  const activeFile = files.find((file) => file.name === selectedFile) ?? files[0];
  const taskCount = projects.reduce((total, project) => total + project.tasks.length, 0);

  return (
    <div className="g-page">
      <section className="g-page-hero">
        <div>
          <p className="g-eyebrow">Project Environment</p>
          <h1>Repository state, orchestration, and active work.</h1>
          <p>Designed as a real workspace lens: tracked files, active project tasks, and backend orchestration status.</p>
        </div>
        <span className="g-live-pill g-status-good">
          <GitBranch className="h-3.5 w-3.5" />
          jarvis_v3_complete
        </span>
      </section>

      <section className="g-metric-strip">
        <article>
          <FolderGit2 className="h-4 w-4" />
          <span>Projects</span>
          <strong>{projects.length}</strong>
        </article>
        <article>
          <CheckSquare className="h-4 w-4" />
          <span>Tasks</span>
          <strong>{taskCount}</strong>
        </article>
        <article>
          <FileCode className="h-4 w-4" />
          <span>Key files</span>
          <strong>{files.length}</strong>
        </article>
      </section>

      <section className="g-project-layout">
        <div className="g-panel">
          <div className="g-section-heading">
            <span>Repository map</span>
            <small>curated paths</small>
          </div>
          <div className="g-file-list">
            {files.map((file) => (
              <button
                key={file.name}
                onClick={() => setSelectedFile(file.name)}
                className={selectedFile === file.name ? "active" : ""}
              >
                <FileCode className="h-4 w-4" />
                <span>{file.name}</span>
                <small>{file.type}</small>
              </button>
            ))}
          </div>
        </div>

        <div className="g-panel g-project-main">
          <div className="g-section-heading">
            <span>{activeFile.name}</span>
            <small>{activeFile.size}</small>
          </div>
          <div className="g-code-preview">
            <p># Source path: {activeFile.name}</p>
            <p>class NexoraRuntime:</p>
            <p>  def __init__(self, root: Path):</p>
            <p>    self.cognition = CognitiveIntelligenceEngine(...)</p>
            <p>    self.conversation = ConversationMemory(...)</p>
            <p>    self.voice = VoiceEngine(...)</p>
          </div>

          <div className="g-section-heading g-section-heading-spaced">
            <span>Project agents & tasks</span>
            <small>{projectError ? "unavailable" : `${projects.length} tracked`}</small>
          </div>

          {projectError && <div className="g-alert-panel">{projectError}</div>}
          {!projectError && projects.length === 0 && (
            <div className="g-empty-inline">
              <Terminal className="h-6 w-6" />
              <p>No orchestrated projects have been created.</p>
            </div>
          )}
          <div className="g-task-stack">
            {projects.map((project) => (
              <article key={project.project_id}>
                <div>
                  <Cpu className="h-4 w-4" />
                  <span>{project.name}</span>
                  <small>{project.status}</small>
                </div>
                <p>{project.goal}</p>
                {project.tasks.map((task) => (
                  <div key={task.id} className="g-task-row">
                    <span>{task.worker_application}: {task.description}</span>
                    <small>{task.status}</small>
                  </div>
                ))}
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
