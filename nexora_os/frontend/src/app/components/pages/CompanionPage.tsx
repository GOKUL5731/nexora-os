import React, { useState, useEffect, useCallback } from "react";
import { nexoraApi } from "../../../api/client";
import {
  Smartphone,
  Wifi,
  WifiOff,
  Link2,
  Link2Off,
  RefreshCw,
  Clipboard,
  MapPin,
  Bell,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Shield,
  Zap,
  Activity,
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";

type CompanionStatusData = {
  active_devices?: number;
  supported_features?: string[];
  desktop_status?: Record<string, unknown>;
};

type PairedDevice = {
  device_id: string;
  device_name: string;
  platform: string;
  auth_token: string;
  paired_at: number;
  desktop_brain: string;
};

const FEATURE_ICONS: Record<string, React.ElementType> = {
  voice_streaming: Wifi,
  camera_streaming: Activity,
  photo_upload: Smartphone,
  file_upload: Clipboard,
  location_relay: MapPin,
  clipboard_sync: Clipboard,
  conversation_sync: Link2,
  notifications: Bell,
};

function StatusBadge({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[10px] font-mono px-2 py-0.5 rounded-full border ${
        ok
          ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
          : "text-red-400 border-red-500/30 bg-red-500/10"
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? "bg-emerald-400 animate-pulse" : "bg-red-400"}`} />
      {ok ? "ONLINE" : "OFFLINE"}
    </span>
  );
}

function FeaturePill({ feature }: { feature: string }) {
  const Icon = FEATURE_ICONS[feature] ?? Zap;
  const label = feature.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <div className="flex items-center gap-1.5 text-[10px] font-mono bg-slate-800/60 border border-slate-700/60 rounded-lg px-2.5 py-1.5 text-slate-300">
      <Icon className="w-3 h-3 text-cyan-400 shrink-0" />
      <span>{label}</span>
    </div>
  );
}

export function CompanionPage() {
  const [status, setStatus] = useState<CompanionStatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [pairedDevice, setPairedDevice] = useState<PairedDevice | null>(null);
  const [pairing, setPairing] = useState(false);
  const [pairError, setPairError] = useState("");
  const [deviceId, setDeviceId] = useState("");
  const [deviceName, setDeviceName] = useState("My iPhone");
  const [clipboardText, setClipboardText] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await nexoraApi.companionStatus();
      setStatus(data as CompanionStatusData);
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 15000);
    return () => clearInterval(id);
  }, [fetchStatus]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchStatus();
  };

  const handlePair = async () => {
    if (!deviceId.trim()) {
      setPairError("Device ID is required.");
      return;
    }
    setPairing(true);
    setPairError("");
    try {
      const res = await nexoraApi.companionPair(deviceId.trim(), deviceName.trim() || "My iPhone");
      setPairedDevice(res as PairedDevice);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Pairing failed.";
      setPairError(msg);
    } finally {
      setPairing(false);
    }
  };

  const handleUnpair = () => {
    setPairedDevice(null);
    setSyncResult(null);
  };

  const handleSync = async () => {
    if (!pairedDevice) return;
    setSyncing(true);
    setSyncResult(null);
    try {
      await nexoraApi.companionSync(pairedDevice.device_id, pairedDevice.auth_token, clipboardText);
      setSyncResult("Sync successful! Data pushed to NEXORA Brain.");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Sync failed.";
      setSyncResult(`Error: ${msg}`);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[#060912] text-slate-100">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/70 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500/20 to-cyan-500/20 border border-violet-500/30 flex items-center justify-center shadow-[0_0_20px_rgba(139,92,246,0.15)]">
            <Smartphone className="w-5 h-5 text-violet-400" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-100 tracking-wide">iPhone Companion</h1>
            <p className="text-[11px] text-slate-500 font-mono">Pair your iPhone to extend NEXORA AI</p>
          </div>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-1.5 text-[11px] font-mono px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700 text-slate-400 hover:text-slate-200 hover:bg-slate-700/60 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Status Panel */}
        <div className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-mono font-semibold text-slate-300 uppercase tracking-widest">
              Server Status
            </span>
            <StatusBadge ok={!loading && status !== null} />
          </div>

          {loading ? (
            <div className="flex items-center gap-2 text-slate-500 text-xs font-mono">
              <Loader2 className="w-4 h-4 animate-spin" />
              Connecting to NEXORA backend…
            </div>
          ) : status ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/40">
                  <div className="text-[10px] font-mono text-slate-500 uppercase mb-1">Active Devices</div>
                  <div className="text-2xl font-bold text-cyan-400">{status.active_devices ?? 0}</div>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/40">
                  <div className="text-[10px] font-mono text-slate-500 uppercase mb-1">Brain</div>
                  <div className="text-sm font-mono text-emerald-400 truncate">
                    {pairedDevice ? pairedDevice.desktop_brain : "NEXORA OS"}
                  </div>
                </div>
              </div>

              {status.supported_features && status.supported_features.length > 0 && (
                <div>
                  <div className="text-[10px] font-mono text-slate-500 uppercase mb-2 tracking-widest">
                    Supported Features
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {status.supported_features.map((f) => (
                      <FeaturePill key={f} feature={f} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-red-400 text-xs font-mono">
              <WifiOff className="w-4 h-4" />
              Cannot reach NEXORA backend. Is the server running?
            </div>
          )}
        </div>

        {/* Pairing Panel */}
        <AnimatePresence mode="wait">
          {!pairedDevice ? (
            <motion.div
              key="pair-form"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-5"
            >
              <div className="flex items-center gap-2 mb-4">
                <Shield className="w-4 h-4 text-violet-400" />
                <span className="text-xs font-mono font-semibold text-slate-300 uppercase tracking-widest">
                  Pair New Device
                </span>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-[10px] font-mono text-slate-500 uppercase mb-1.5">Device ID *</label>
                  <input
                    type="text"
                    value={deviceId}
                    onChange={(e) => setDeviceId(e.target.value)}
                    placeholder="e.g. iphone-gokul-001"
                    className="w-full bg-slate-800/60 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-600 font-mono focus:outline-none focus:border-violet-500/60 focus:ring-1 focus:ring-violet-500/20 transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-mono text-slate-500 uppercase mb-1.5">
                    Device Name
                  </label>
                  <input
                    type="text"
                    value={deviceName}
                    onChange={(e) => setDeviceName(e.target.value)}
                    placeholder="My iPhone"
                    className="w-full bg-slate-800/60 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-600 font-mono focus:outline-none focus:border-violet-500/60 focus:ring-1 focus:ring-violet-500/20 transition-colors"
                  />
                </div>

                {pairError && (
                  <div className="flex items-center gap-2 text-red-400 text-xs font-mono bg-red-950/20 border border-red-500/20 rounded-lg px-3 py-2">
                    <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                    {pairError}
                  </div>
                )}

                <button
                  onClick={handlePair}
                  disabled={pairing || !status}
                  className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-violet-600 to-cyan-600 hover:from-violet-500 hover:to-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold py-2.5 rounded-lg transition-all duration-200 shadow-[0_0_20px_rgba(139,92,246,0.3)] hover:shadow-[0_0_30px_rgba(139,92,246,0.5)]"
                >
                  {pairing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Pairing…
                    </>
                  ) : (
                    <>
                      <Link2 className="w-4 h-4" />
                      Pair Device
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="pair-success"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="bg-slate-900/50 border border-emerald-500/30 rounded-xl p-5 shadow-[0_0_30px_rgba(16,185,129,0.08)]"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-mono font-semibold text-emerald-300 uppercase tracking-widest">
                    Device Paired
                  </span>
                </div>
                <button
                  onClick={handleUnpair}
                  className="flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-lg bg-red-950/30 border border-red-500/20 text-red-400 hover:bg-red-950/50 transition-colors"
                >
                  <Link2Off className="w-3 h-3" />
                  Unpair
                </button>
              </div>

              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/40">
                  <div className="text-[10px] font-mono text-slate-500 uppercase mb-1">Device Name</div>
                  <div className="text-sm font-mono text-slate-200 truncate">{pairedDevice.device_name}</div>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/40">
                  <div className="text-[10px] font-mono text-slate-500 uppercase mb-1">Platform</div>
                  <div className="text-sm font-mono text-violet-400">{pairedDevice.platform}</div>
                </div>
                <div className="col-span-2 bg-slate-800/50 rounded-lg p-3 border border-slate-700/40">
                  <div className="text-[10px] font-mono text-slate-500 uppercase mb-1">Auth Token</div>
                  <div className="text-xs font-mono text-cyan-400 break-all">{pairedDevice.auth_token}</div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Sync Panel — only when paired */}
        <AnimatePresence>
          {pairedDevice && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25, delay: 0.05 }}
              className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-5"
            >
              <div className="flex items-center gap-2 mb-4">
                <RefreshCw className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-mono font-semibold text-slate-300 uppercase tracking-widest">
                  Sync Data
                </span>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-[10px] font-mono text-slate-500 uppercase mb-1.5">
                    Clipboard Content (optional)
                  </label>
                  <textarea
                    value={clipboardText}
                    onChange={(e) => setClipboardText(e.target.value)}
                    placeholder="Paste text to sync from iPhone clipboard…"
                    rows={3}
                    className="w-full bg-slate-800/60 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-600 font-mono resize-none focus:outline-none focus:border-cyan-500/60 focus:ring-1 focus:ring-cyan-500/20 transition-colors"
                  />
                </div>

                {syncResult && (
                  <div
                    className={`flex items-start gap-2 text-xs font-mono rounded-lg px-3 py-2 border ${
                      syncResult.startsWith("Error")
                        ? "text-red-400 bg-red-950/20 border-red-500/20"
                        : "text-emerald-400 bg-emerald-950/20 border-emerald-500/20"
                    }`}
                  >
                    {syncResult.startsWith("Error") ? (
                      <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    ) : (
                      <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    )}
                    <span>{syncResult}</span>
                  </div>
                )}

                <button
                  onClick={handleSync}
                  disabled={syncing}
                  className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-cyan-700 to-cyan-600 hover:from-cyan-600 hover:to-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold py-2.5 rounded-lg transition-all duration-200 shadow-[0_0_16px_rgba(6,182,212,0.25)] hover:shadow-[0_0_24px_rgba(6,182,212,0.4)]"
                >
                  {syncing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Syncing…
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4" />
                      Push Sync to Brain
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Architecture Info */}
        <div className="bg-slate-900/30 border border-slate-800/40 rounded-xl p-4">
          <div className="text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-3">
            Architecture
          </div>
          <div className="flex items-center gap-3 justify-center text-xs font-mono text-slate-400">
            <div className="flex flex-col items-center gap-1">
              <Smartphone className="w-6 h-6 text-violet-400" />
              <span className="text-[10px]">iPhone</span>
            </div>
            <div className="flex-1 h-px border-t border-dashed border-slate-700 relative">
              <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 text-[9px] text-cyan-500 bg-[#060912] px-1">
                REST / WebSocket
              </span>
            </div>
            <div className="flex flex-col items-center gap-1">
              <Activity className="w-6 h-6 text-cyan-400" />
              <span className="text-[10px]">NEXORA Brain</span>
            </div>
          </div>
          <p className="text-[10px] font-mono text-slate-600 mt-3 text-center leading-relaxed">
            Your Desktop is the AI Brain. The iPhone is the Companion.
            <br />
            Pair your device to enable voice streaming, camera AI, and cross-device memory sync.
          </p>
        </div>
      </div>
    </div>
  );
}
