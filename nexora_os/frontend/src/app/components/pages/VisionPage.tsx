import React, { useEffect, useState, useRef } from "react";
import { Eye, Camera, Scan, MousePointer2 } from "lucide-react";
import { nexoraApi } from "../../../api/client";
import { useNexora } from "../../../context/NexoraContext";
import { CommandBar } from "../CommandBar";

export function VisionPage() {
  const { visionStart, visionStop, connected } = useNexora();
  const [visionStatus, setVisionStatus] = useState<Record<string, unknown>>({});
  const [cameraFrame, setCameraFrame] = useState<string>("");
  const [mouseControlEnabled, setMouseControlEnabled] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const streamRef = useRef<number | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setVisionStatus(await nexoraApi.visionStatus());
      } catch {
        setVisionStatus({});
      }
    };
    load();
    const id = setInterval(load, 2000);
    return () => clearInterval(id);
  }, []);

  const startCameraStream = async () => {
    if (isStreaming) return;
    setIsStreaming(true);
    
    const streamFrame = async () => {
      try {
        const endpoint = mouseControlEnabled ? '/vision/frame/mouse' : '/vision/frame';
        const response = await fetch(`http://127.0.0.1:7474${endpoint}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (data.ok && data.frame) {
          setCameraFrame(`data:image/jpeg;base64,${data.frame}`);
        }
      } catch (error) {
        console.error('Error fetching frame:', error);
      }
    };

    streamFrame();
    streamRef.current = window.setInterval(streamFrame, 100); // 10 FPS
  };

  const stopCameraStream = () => {
    if (streamRef.current) {
      clearInterval(streamRef.current);
      streamRef.current = null;
    }
    setIsStreaming(false);
    setCameraFrame("");
  };

  const toggleMouseControl = async () => {
    try {
      if (mouseControlEnabled) {
        await fetch('http://127.0.0.1:7474/vision/mouse/disable', { method: 'POST' });
        setMouseControlEnabled(false);
      } else {
        await fetch('http://127.0.0.1:7474/vision/mouse/enable', { method: 'POST' });
        setMouseControlEnabled(true);
      }
    } catch (error) {
      console.error('Error toggling mouse control:', error);
    }
  };

  useEffect(() => {
    return () => {
      stopCameraStream();
    };
  }, []);

  return (
    <div className="flex-1 flex flex-col p-8 gap-6 overflow-auto">
      <h2 className="text-xl font-['Rajdhani'] text-cyan-400 tracking-widest uppercase">Vision Matrix</h2>
      <div className="flex flex-wrap gap-3">
        <button
          disabled={!connected}
          onClick={async () => {
            await visionStart();
            startCameraStream();
          }}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-cyan-500/40 text-cyan-200 hover:bg-cyan-950/30 disabled:opacity-40"
        >
          <Camera className="w-4 h-4" /> Start Webcam
        </button>
        <button
          disabled={!connected}
          onClick={async () => {
            await visionStop();
            stopCameraStream();
          }}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-cyan-900/40 text-cyan-500 hover:bg-black/40 disabled:opacity-40"
        >
          Stop Webcam
        </button>
        <button
          disabled={!connected}
          onClick={() => nexoraApi.visionScreen(false).then(setVisionStatus)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-cyan-900/40 text-cyan-500 hover:bg-black/40 disabled:opacity-40"
        >
          <Scan className="w-4 h-4" /> Screenshot
        </button>
        <button
          disabled={!connected}
          onClick={() => nexoraApi.visionScreen(true).then(setVisionStatus)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-cyan-900/40 text-cyan-500 hover:bg-black/40 disabled:opacity-40"
        >
          <Eye className="w-4 h-4" /> OCR Screen
        </button>
        <button
          disabled={!connected}
          onClick={toggleMouseControl}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg border ${mouseControlEnabled ? 'border-green-500/40 text-green-200 hover:bg-green-950/30' : 'border-cyan-900/40 text-cyan-500 hover:bg-black/40'} disabled:opacity-40`}
        >
          <MousePointer2 className="w-4 h-4" /> {mouseControlEnabled ? 'Mouse Control ON' : 'Mouse Control OFF'}
        </button>
      </div>
      
      {cameraFrame && (
        <div className="relative bg-black/50 border border-cyan-900/30 rounded-xl overflow-hidden">
          <img 
            src={cameraFrame} 
            alt="Camera Feed" 
            className="w-full max-w-2xl mx-auto"
            style={{ maxHeight: '480px', objectFit: 'contain' }}
          />
          {mouseControlEnabled && (
            <div className="absolute top-2 right-2 bg-green-500/20 border border-green-500/40 text-green-300 px-3 py-1 rounded text-xs">
              Mouse Control Active
            </div>
          )}
        </div>
      )}
      <pre className="text-xs font-mono text-cyan-600/80 bg-black/50 border border-cyan-900/30 rounded-xl p-4 overflow-auto max-h-48">
        {JSON.stringify(visionStatus, null, 2)}
      </pre>
      <CommandBar />
    </div>
  );
}
