import React, { useState, useRef, useEffect } from "react";
import {
  Send,
  Mic,
  Paperclip,
  Image as ImageIcon,
  Loader2,
  Sparkles,
  CheckCircle2,
  Workflow as WorkflowIcon,
  Copy,
  Check,
  Bot,
  User,
  Zap,
  Globe,
} from "lucide-react";
import { useNexora } from "../../../context/NexoraContext";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  language?: string;
  steps?: Array<{ step: number; action: string; thought: string }>;
  verified?: boolean;
};

export function ChatPage() {
  const { sendCommand, busy, connected, voiceState, startVoice, agentSteps, lastMessage, brainState } = useNexora();

  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "init",
      role: "assistant",
      content: "Hello! I am NEXORA. How can I assist you with your tasks, codebase, or research today?",
      timestamp: new Date().toLocaleTimeString(),
      language: "en",
    },
  ]);
  const [selectedModel, setSelectedModel] = useState("llama3.2:1b");
  const [workflowMode, setWorkflowMode] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, agentSteps]);

  const handleSend = async () => {
    if (!input.trim() || busy) return;

    const userText = input.trim();
    setInput("");

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: userText,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMsg]);

    try {
      const res = await sendCommand(userText, {
        model: selectedModel,
        workflow_enabled: workflowMode,
        speak: true,
      });

      const assistantMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: res?.message || "Task completed.",
        timestamp: new Date().toLocaleTimeString(),
        steps: [...agentSteps],
        verified: res?.ok,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: "assistant",
        content: `Error: ${err instanceof Error ? err.message : String(err)}`,
        timestamp: new Date().toLocaleTimeString(),
        verified: false,
      };
      setMessages((prev) => [...prev, errorMsg]);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#060911] relative overflow-hidden select-none font-mono">
      {/* 1. Header Toolbar */}
      <div className="h-12 px-6 border-b border-slate-800/80 bg-[#080d1a]/80 flex items-center justify-between z-10 shrink-0">
        <div className="flex items-center gap-3 text-xs">
          <MessageSquareIcon className="w-4 h-4 text-cyan-400" />
          <span className="text-slate-200 font-semibold tracking-wider uppercase">Chat Workspace</span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400 text-[11px]">{messages.length} messages</span>
        </div>

        {/* Model & Mode Toggles */}
        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-slate-300">
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="bg-transparent text-slate-200 outline-none cursor-pointer font-mono text-[11px]"
            >
              <option value="llama3.2:1b" className="bg-slate-900 text-slate-200">llama3.2:1b (Local)</option>
              <option value="qwen2.5-coder" className="bg-slate-900 text-slate-200">qwen2.5-coder (Code)</option>
              <option value="deepseek-r1" className="bg-slate-900 text-slate-200">deepseek-r1 (Reasoning)</option>
            </select>
          </div>

          <button
            onClick={() => setWorkflowMode(!workflowMode)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded border text-[11px] transition-colors ${
              workflowMode
                ? "bg-cyan-950/60 border-cyan-500/50 text-cyan-300"
                : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            <WorkflowIcon className="w-3.5 h-3.5" />
            <span>Workflow Mode</span>
          </button>
        </div>
      </div>

      {/* 2. Messages Stream */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 no-scrollbar">
        {messages.map((msg) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={msg.id}
              className={`flex gap-4 max-w-4xl mx-auto ${isUser ? "flex-row-reverse" : "flex-row"}`}
            >
              {/* Avatar */}
              <div
                className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border text-xs ${
                  isUser
                    ? "bg-cyan-950/50 border-cyan-500/30 text-cyan-400"
                    : "bg-slate-900 border-slate-800 text-cyan-300"
                }`}
              >
                {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              {/* Message Content Bubble */}
              <div
                className={`flex-1 rounded-xl p-4 border text-xs leading-relaxed space-y-2 relative group ${
                  isUser
                    ? "bg-cyan-950/20 border-cyan-500/25 text-slate-100"
                    : "bg-[#090d18] border-slate-800/90 text-slate-200"
                }`}
              >
                {/* Header */}
                <div className="flex items-center justify-between text-[10px] text-slate-500 pb-1 border-b border-slate-800/40">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-400">{isUser ? "YOU" : "NEXORA"}</span>
                    {msg.language && (
                      <span className="px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 uppercase text-[9px]">
                        {msg.language}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span>{msg.timestamp}</span>
                    <button
                      onClick={() => copyToClipboard(msg.content, msg.id)}
                      className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-slate-200 transition-opacity"
                      title="Copy content"
                    >
                      {copiedId === msg.id ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    </button>
                  </div>
                </div>

                {/* Body Text */}
                <div className="whitespace-pre-wrap font-sans text-xs text-slate-200">{msg.content}</div>

                {/* Execution Steps if present */}
                {msg.steps && msg.steps.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-slate-800/60 space-y-1">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Execution Steps</span>
                    {msg.steps.map((s) => (
                      <div key={s.step} className="flex items-center gap-2 text-[10px] text-slate-400">
                        <span className="text-cyan-400 font-semibold">#{s.step}</span>
                        <span className="text-amber-300 font-mono">{s.action}</span>
                        <span className="text-slate-500 truncate">{s.thought}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        <div ref={messagesEndRef} />
      </div>

      {/* 3. Task Execution Timeline Progress Indicator */}
      {busy && (
        <div className="max-w-3xl mx-auto w-full px-6 py-2">
          <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800 flex items-center justify-between text-xs text-slate-300">
            <div className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
              <span>{brainState?.stage || "Processing request..."}</span>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-slate-500 font-mono">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <span>{agentSteps.length} steps logged</span>
            </div>
          </div>
        </div>
      )}

      {/* 4. Modern Input Bar */}
      <div className="p-4 bg-[#080d19] border-t border-slate-800/80 shrink-0 z-10">
        <div className="max-w-4xl mx-auto flex items-center gap-2 bg-slate-900/90 border border-slate-800 rounded-xl px-3 py-2 focus-within:border-cyan-500/50 transition-colors shadow-xl">
          {/* Voice Mic Button */}
          <button
            type="button"
            onClick={startVoice}
            disabled={!connected || busy}
            className={`p-2 rounded-lg transition-colors ${
              voiceState === "listening"
                ? "bg-rose-500/20 text-rose-400 animate-pulse border border-rose-500/40"
                : "text-slate-400 hover:text-cyan-400 hover:bg-slate-800"
            }`}
            title="Voice Input (Tamil / Tanglish / English)"
          >
            <Mic className="w-4 h-4" />
          </button>

          {/* Attachment Button */}
          <button
            type="button"
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
            title="Attach File"
          >
            <Paperclip className="w-4 h-4" />
          </button>

          {/* Image Upload Button */}
          <button
            type="button"
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
            title="Upload Image"
          >
            <ImageIcon className="w-4 h-4" />
          </button>

          {/* Textarea Input */}
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder={connected ? "Ask NEXORA anything or type commands… (Tamil / English)" : "Backend OFFLINE"}
            disabled={!connected || busy}
            className="flex-1 bg-transparent text-xs text-slate-100 placeholder:text-slate-500 outline-none font-sans"
          />

          {/* Send Button */}
          <button
            type="button"
            disabled={!connected || busy || !input.trim()}
            onClick={handleSend}
            className="p-2 rounded-lg bg-cyan-600 text-white hover:bg-cyan-500 disabled:opacity-30 disabled:hover:bg-cyan-600 transition-colors shadow-[0_0_12px_rgba(6,182,212,0.3)]"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageSquareIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg {...props} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
  );
}
