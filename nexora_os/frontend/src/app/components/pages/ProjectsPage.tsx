import React, { useEffect, useState } from "react";
import { FolderGit2, FileCode, GitBranch, CheckSquare, Cpu, Play, Terminal } from "lucide-react";
import { useNexora } from "../../../context/NexoraContext";
import { nexoraApi, OrchestrationProject } from "../../../api/client";

export function ProjectsPage() {
  const { agents, busy } = useNexora();
  const [selectedFile, setSelectedFile] = useState("nexora_os/backend/core/runtime.py");
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

  const files = [
    { name: "nexora_os/backend/core/runtime.py", size: "25.9 KB", type: "python" },
    { name: "nexora_os/backend/core/cognitive_intelligence.py", size: "11.3 KB", type: "python" },
    { name: "nexora_os/backend/voice/pipeline.py", size: "7.8 KB", type: "python" },
    { name: "nexora_os/backend/memory/conversation.py", size: "4.2 KB", type: "python" },
    { name: "nexora_os/backend/knowledge/manager.py", size: "9.1 KB", type: "python" },
    { name: "nexora_os/frontend/src/app/App.tsx", size: "5.1 KB", type: "typescript" },
  ];

  return (
    <div className="flex-1 flex flex-col p-6 space-y-6 overflow-y-auto no-scrollbar font-mono text-xs select-none">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-base font-bold text-slate-100 uppercase tracking-widest flex items-center gap-2">
            <FolderGit2 className="w-4 h-4 text-cyan-400" />
            Project Environment — jarvis_v3_complete
          </h1>
          <p className="text-[11px] text-slate-500 font-sans mt-0.5">
            Active repository files, open agent tasks, and workspace status
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-slate-300 flex items-center gap-1.5 text-[11px]">
            <GitBranch className="w-3.5 h-3.5 text-emerald-400" />
            <span>{projects.length ? `${projects.length} tracked project${projects.length === 1 ? "" : "s"}` : "No active project"}</span>
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
        {/* Left 1 Col: File Explorer */}
        <div className="p-4 rounded-xl bg-[#090d19] border border-slate-800 space-y-3">
          <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider block border-b border-slate-800 pb-2">
            Repository Files
          </span>

          <div className="space-y-1">
            {files.map((file) => (
              <button
                key={file.name}
                onClick={() => setSelectedFile(file.name)}
                className={`w-full flex items-center justify-between p-2 rounded text-left transition-colors ${
                  selectedFile === file.name
                    ? "bg-cyan-950/60 border border-cyan-500/30 text-cyan-300"
                    : "hover:bg-slate-900 text-slate-400 hover:text-slate-200"
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  <FileCode className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                  <span className="truncate">{file.name}</span>
                </div>
                <span className="text-[10px] text-slate-600 shrink-0 ml-2">{file.size}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Right 2 Cols: File Viewer / Recent Agent Work */}
        <div className="lg:col-span-2 space-y-6">
          <div className="p-4 rounded-xl bg-[#090d19] border border-slate-800 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-200 font-semibold flex items-center gap-2">
                <FileCode className="w-4 h-4 text-cyan-400" />
                {selectedFile}
              </span>
              <span className="text-[10px] text-emerald-400 uppercase">Synchronized</span>
            </div>

            <div className="p-3 rounded bg-slate-950 border border-slate-800 font-mono text-[11px] text-slate-300 space-y-1 overflow-x-auto">
              <p className="text-slate-500"># Source path: {selectedFile}</p>
              <p className="text-cyan-400">class NexoraRuntime:</p>
              <p className="text-slate-400 pl-4">def __init__(self, root: Path):</p>
              <p className="text-slate-400 pl-8">self.cognition = CognitiveIntelligenceEngine(...)</p>
              <p className="text-slate-400 pl-8">self.conversation = ConversationMemory(...)</p>
              <p className="text-slate-400 pl-8">self.voice = VoiceEngine(...)</p>
            </div>
          </div>

          {/* Real orchestrator state */}
          <div className="p-4 rounded-xl bg-[#090d19] border border-slate-800 space-y-3">
            <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider block border-b border-slate-800 pb-2">
              Project Agents & Tasks
            </span>

            {projectError && <p className="text-rose-400">{projectError}</p>}
            {!projectError && projects.length === 0 && <p className="text-slate-500">No orchestrated projects have been created.</p>}
            <div className="space-y-3">
              {projects.map((project) => (
                <div key={project.project_id} className="p-3 rounded bg-slate-900 border border-slate-800 space-y-2">
                  <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-cyan-400" />
                    <div>
                      <span className="text-slate-200 font-medium block">{project.name}</span>
                      <span className="text-[10px] text-slate-500">{project.goal}</span>
                    </div>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800 uppercase">
                    {project.status}
                  </span>
                </div>
                  {project.tasks.map((task) => <div key={task.id} className="flex justify-between border-t border-slate-800 pt-2 text-[10px]"><span className="text-slate-400">{task.worker_application}: {task.description}</span><span className="text-slate-500 uppercase">{task.status}</span></div>)}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
