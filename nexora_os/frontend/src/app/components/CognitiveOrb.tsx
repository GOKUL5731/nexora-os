import React, { useMemo } from "react";
import { motion } from "motion/react";
import { useNexora } from "../../context/NexoraContext";

export function CognitiveOrb() {
  const { voiceState, lastMessage, connected, busy } = useNexora();
  const speaking = voiceState === "speaking";
  const listening = voiceState === "listening" || busy;

  const waveform = useMemo(() => Array.from({ length: 16 }, (_, i) => {
    if (!listening && !speaking) return 12 + (i % 3) * 2;
    return 24 + (i % 5) * 7;
  }), [listening, speaking]);

  return (
    <div className="relative w-full h-[60%] min-h-[400px] flex items-center justify-center overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(0,180,255,0.06)_0%,rgba(0,0,0,0)_60%)] pointer-events-none" />

      <div className="relative w-[min(70vw,380px)] h-[min(70vw,380px)] min-w-[240px] min-h-[240px] flex items-center justify-center">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
          className="absolute inset-[-24px] md:inset-[-60px] rounded-full border border-cyan-800/40"
          style={{ borderStyle: "dashed", borderWidth: "1px" }}
        />

        <motion.div
          animate={{
            scale: speaking || listening ? [1, 1.06, 1] : [1, 1.02, 1],
            opacity: connected ? [0.5, 0.9, 0.5] : [0.2, 0.4, 0.2],
          }}
          transition={{ duration: speaking ? 1.2 : 3, repeat: Infinity, ease: "easeInOut" }}
          className="absolute inset-0 rounded-full border-[3px] border-cyan-500/30 shadow-[0_0_60px_rgba(0,255,255,0.3),inset_0_0_40px_rgba(0,255,255,0.2)]"
        />

        <motion.div
          className="absolute inset-6 rounded-full bg-[radial-gradient(circle_at_center,rgba(0,255,255,0.2)_0%,rgba(0,0,0,0.4)_80%)] backdrop-blur-md border border-cyan-300/30 shadow-[inset_0_0_50px_rgba(0,255,255,0.2)] flex items-center justify-center flex-col z-10"
        >
          <div className="flex flex-col items-center z-20 font-['Rajdhani'] relative px-6 text-center">
            <h1 className="text-3xl md:text-5xl font-bold tracking-[0.25em] text-transparent bg-clip-text bg-gradient-to-b from-white via-cyan-100 to-cyan-500 mb-2">
              NEXORA
            </h1>
            <div className="flex items-center gap-2 mb-6">
              <div
                className={`w-2 h-2 rounded-full ${connected ? "bg-cyan-400 animate-pulse" : "bg-red-500/80"}`}
              />
              <p className="text-cyan-400 text-xs tracking-[0.3em] uppercase font-semibold">
                {connected ? (busy ? "Processing…" : "System Online") : "Backend Offline"}
              </p>
            </div>

            <div className="flex items-end justify-center gap-1 md:gap-1.5 h-12 md:h-16 w-32 md:w-40 mb-4">
              {waveform.map((height, i) => (
                <motion.div
                  key={i}
                  animate={{ height }}
                  transition={{ type: "spring", bounce: 0, duration: 0.2 }}
                  className="w-1.5 bg-gradient-to-t from-cyan-600 to-cyan-300 rounded-full shadow-[0_0_8px_rgba(0,255,255,0.8)]"
                  style={{ minHeight: "6px" }}
                />
              ))}
            </div>

            <p className="text-white/90 text-xs md:text-sm tracking-wider font-light max-w-[220px] md:max-w-[280px] line-clamp-3">
              "{lastMessage}"
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
