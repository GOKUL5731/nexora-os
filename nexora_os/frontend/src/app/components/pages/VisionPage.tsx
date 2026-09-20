import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Camera,
  Eye,
  FileText,
  Hand,
  Monitor,
  MousePointer2,
  Play,
  RefreshCw,
  Scan,
  Square,
} from "lucide-react";
import { nexoraApi } from "../../../api/client";
import { useNexora } from "../../../context/NexoraContext";

type VisionFrame = {
  ok?: boolean;
  frame?: string;
  width?: number;
  height?: number;
  faces?: Array<{ x: number; y: number; width: number; height: number }>;
  objects?: Array<{ label?: string; confidence?: number }>;
  gesture?: string | null;
  controls?: { pan_x?: number; pan_y?: number; zoom?: number };
  gesture_action?: string | null;
  mouse_control?: boolean;
  mouse_state?: { x?: number; y?: number; click?: boolean; scroll?: number };
  error?: string;
  webcam?: string;
};

export function VisionPage() {
  const { busy } = useNexora();
  const [activeTab, setActiveTab] = useState<"camera" | "screen" | "ocr">("camera");
  const [ocrText, setOcrText] = useState("");
  const [capturing, setCapturing] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [gestureEnabled, setGestureEnabled] = useState(false);
  const [mouseEnabled, setMouseEnabled] = useState(false);
  const [frame, setFrame] = useState<VisionFrame | null>(null);
  const [status, setStatus] = useState("Camera idle");
  const [error, setError] = useState<string | null>(null);

  const imageSrc = useMemo(() => {
    if (!frame?.frame) return "";
    return `data:image/jpeg;base64,${frame.frame}`;
  }, [frame]);

  const refreshFrame = useCallback(async () => {
    try {
      const next = mouseEnabled
        ? await nexoraApi.visionFrameWithMouse()
        : await nexoraApi.visionFrame();
      const typed = next as VisionFrame;
      if (!typed.ok) {
        setError(typed.error || "Camera frame unavailable.");
        setStatus(typed.webcam === "unavailable" ? "Camera unavailable" : "Waiting for camera frame");
        return;
      }
      setFrame(typed);
      setError(null);
      setStatus("Live camera stream");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStatus("Camera stream error");
    }
  }, [mouseEnabled]);

  useEffect(() => {
    if (!streaming || activeTab !== "camera") return;
    let cancelled = false;

    const tick = async () => {
      if (!cancelled) {
        await refreshFrame();
      }
    };

    tick();
    const id = window.setInterval(tick, mouseEnabled ? 700 : 900);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [activeTab, mouseEnabled, refreshFrame, streaming]);

  const startStream = async () => {
    setStatus("Starting camera...");
    setError(null);
    const result = (await nexoraApi.visionStart()) as VisionFrame;
    if (!result.ok) {
      setStreaming(false);
      setError(result.error || "Camera could not start.");
      setStatus("Camera unavailable");
      return;
    }
    setStreaming(true);
    setStatus("Live camera stream");
    await refreshFrame();
  };

  const stopStream = async () => {
    await nexoraApi.visionStop();
    setStreaming(false);
    setFrame(null);
    setStatus("Camera stopped");
  };

  const toggleGestures = async () => {
    const next = !gestureEnabled;
    const result = next
      ? await nexoraApi.visionGesturesEnable()
      : await nexoraApi.visionGesturesDisable();
    if (result.ok === false) {
      setError(String(result.error || "Gesture control unavailable."));
      return;
    }
    setGestureEnabled(next);
    setStatus(next ? "Gesture detection enabled" : "Gesture detection disabled");
  };

  const toggleMouseControl = async () => {
    const next = !mouseEnabled;
    const result = next
      ? await nexoraApi.visionMouseEnable()
      : await nexoraApi.visionMouseDisable();
    if (result.ok === false) {
      setError(String(result.error || "Mouse control unavailable."));
      return;
    }
    setMouseEnabled(next);
    setStatus(next ? "Hand mouse control enabled" : "Hand mouse control disabled");
  };

  const handleCaptureOCR = async () => {
    setCapturing(true);
    setError(null);
    try {
      const res = await nexoraApi.visionScreen(true);
      const text = String(res.ocr_text || "").trim();
      setOcrText(text || String(res.error || "No text extracted from screen."));
      setActiveTab("ocr");
    } catch (err) {
      setOcrText(`OCR failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setCapturing(false);
    }
  };

  const runScreenCapture = async () => {
    setCapturing(true);
    setError(null);
    try {
      const res = await nexoraApi.visionScreen(false);
      setOcrText(res.ok ? `Screen captured: ${res.width}x${res.height}` : String(res.error || "Screen capture failed."));
      setActiveTab("screen");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCapturing(false);
    }
  };

  const objects = frame?.objects ?? [];
  const faces = frame?.faces ?? [];

  return (
    <div className="flex-1 flex flex-col p-6 space-y-6 overflow-y-auto no-scrollbar font-mono text-xs select-none">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-base font-bold text-slate-100 uppercase tracking-widest flex items-center gap-2">
            <Eye className="w-4 h-4 text-cyan-400" />
            Vision AI Engine — Object Detection & OCR
          </h1>
          <p className="text-[11px] text-slate-500 font-sans mt-0.5">
            Realtime webcam feed, desktop screen capture, object recognition, OCR, gestures, and hand mouse control
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={startStream}
            disabled={streaming}
            className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium flex items-center gap-1.5 disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5" />
            <span>Start Vision Stream</span>
          </button>
          <button
            onClick={stopStream}
            disabled={!streaming}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center gap-1.5 disabled:opacity-50"
          >
            <Square className="w-3.5 h-3.5" />
            <span>Stop</span>
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-2">
        <ModeButton active={activeTab === "camera"} icon={<Camera className="w-3.5 h-3.5" />} label="Camera Stream" onClick={() => setActiveTab("camera")} />
        <ModeButton active={activeTab === "screen"} icon={<Monitor className="w-3.5 h-3.5" />} label="Screen Capture" onClick={runScreenCapture} />
        <ModeButton active={activeTab === "ocr"} icon={<FileText className="w-3.5 h-3.5" />} label="OCR & Text Extraction" onClick={() => setActiveTab("ocr")} />
        <ToggleButton active={gestureEnabled} icon={<Hand className="w-3.5 h-3.5" />} label="Gestures" onClick={toggleGestures} />
        <ToggleButton active={mouseEnabled} icon={<MousePointer2 className="w-3.5 h-3.5" />} label="Hand Mouse" onClick={toggleMouseControl} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 p-4 rounded-xl bg-[#090d19] border border-slate-800 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="text-slate-200 font-semibold uppercase tracking-wider flex items-center gap-2">
              <Scan className="w-4 h-4 text-cyan-400" />
              Viewport Stream — {activeTab.toUpperCase()}
            </span>
            <span className={`text-[10px] font-mono ${streaming ? "text-emerald-400" : "text-slate-500"}`}>
              {frame?.width && frame?.height ? `${frame.width}x${frame.height}` : "Camera idle"}
            </span>
          </div>

          <div className="w-full h-80 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center relative overflow-hidden group">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(6,182,212,0.05)_0%,transparent_70%)] pointer-events-none" />

            {imageSrc ? (
              <img
                src={imageSrc}
                alt="Live camera preview"
                className="h-full w-full object-contain bg-black"
                draggable={false}
              />
            ) : (
              <div className="flex flex-col items-center justify-center">
                <Eye className="w-12 h-12 text-slate-700 mb-3 group-hover:text-cyan-500 transition-colors" />
                <span className="text-slate-400 font-medium text-xs">{status}</span>
                <span className="text-[10px] text-slate-600 mt-1">Start the stream to display the webcam feed</span>
              </div>
            )}

            {error && (
              <div className="absolute left-3 right-3 bottom-3 rounded-lg border border-rose-500/40 bg-rose-950/70 px-3 py-2 text-[11px] text-rose-100">
                {error}
              </div>
            )}
          </div>
        </div>

        <div className="p-4 rounded-xl bg-[#090d19] border border-slate-800 space-y-4">
          <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider block border-b border-slate-800 pb-2">
            Vision Analytics
          </span>

          <div className="grid grid-cols-2 gap-2">
            <Metric label="Status" value={streaming ? "LIVE" : "IDLE"} tone={streaming ? "text-emerald-300" : "text-slate-400"} />
            <Metric label="Faces" value={String(faces.length)} />
            <Metric label="Objects" value={String(objects.length)} />
            <Metric label="Gesture" value={frame?.gesture || frame?.gesture_action || "none"} />
          </div>

          <div className="rounded-lg bg-slate-950 border border-slate-800 p-3 space-y-2">
            <span className="text-[10px] text-slate-500 uppercase block border-b border-slate-800 pb-1">
              Detected Objects
            </span>
            {objects.length > 0 ? (
              objects.slice(0, 6).map((obj, index) => (
                <div key={`${obj.label}-${index}`} className="flex items-center justify-between text-[11px] text-slate-300">
                  <span>{obj.label || "object"}</span>
                  <span className="text-cyan-300">{obj.confidence ?? "--"}</span>
                </div>
              ))
            ) : (
              <p className="text-[11px] text-slate-500 font-sans">No objects detected in the latest frame.</p>
            )}
          </div>

          <button
            onClick={handleCaptureOCR}
            disabled={capturing || busy}
            className="w-full py-2.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium disabled:opacity-40 transition-colors flex items-center justify-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${capturing ? "animate-spin" : ""}`} />
            <span>Run Screen OCR Scan</span>
          </button>

          <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 min-h-[150px] text-slate-300 space-y-2">
            <span className="text-[10px] text-slate-500 uppercase block border-b border-slate-800 pb-1">
              OCR / Screen Result
            </span>
            <p className="whitespace-pre-wrap text-[11px] leading-relaxed text-slate-300 font-sans">
              {ocrText || "No OCR or screen capture result yet."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function ModeButton({ active, icon, label, onClick }: { active: boolean; icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg font-medium flex items-center gap-1.5 ${
        active
          ? "bg-cyan-950 border border-cyan-500/40 text-cyan-300"
          : "bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200"
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

function ToggleButton({ active, icon, label, onClick }: { active: boolean; icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg font-medium flex items-center gap-1.5 ${
        active
          ? "bg-emerald-950 border border-emerald-500/40 text-emerald-300"
          : "bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200"
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

function Metric({ label, value, tone = "text-cyan-300" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg bg-slate-950 border border-slate-800 p-2">
      <div className="flex items-center gap-1.5 text-[9px] uppercase text-slate-500">
        <Activity className="w-3 h-3" />
        {label}
      </div>
      <div className={`mt-1 text-[11px] font-semibold ${tone}`}>{value}</div>
    </div>
  );
}
