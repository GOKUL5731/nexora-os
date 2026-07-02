import React, { useEffect, useState } from "react";
import { Settings } from "lucide-react";
import { nexoraApi } from "../../../api/client";

export function SettingsPage() {
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  useEffect(() => { nexoraApi.settings().then(setSettings).catch(() => setSettings({ error: "Backend offline" })); }, []);
  return (
    <div className="flex-1 p-8 overflow-auto">
      <h2 className="text-xl font-['Rajdhani'] text-cyan-400 tracking-widest uppercase flex items-center gap-2"><Settings className="w-5 h-5" /> Settings</h2>
      <pre className="mt-6 p-5 border border-cyan-900/40 rounded-xl bg-black/50 text-xs text-cyan-500 overflow-auto">{JSON.stringify(settings, null, 2)}</pre>
    </div>
  );
}
