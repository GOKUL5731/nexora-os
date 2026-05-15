"""JARVIS Android Agent stub — ADB bridge. Loads only if ADB is available."""
import logging, subprocess, sys
from agents.agent_registry import BaseAgent

logger = logging.getLogger("jarvis.agents.android")


class AndroidAgent(BaseAgent):
    def __init__(self, config):
        super().__init__(config)
        self.adb = config.get("android",{}).get("adb_path","adb")
        self.device = config.get("android",{}).get("device_id","")

    def supported_tools(self):
        return ["android_tap","android_swipe","android_type","android_screenshot",
                "android_launch","android_shell","android_connect"]

    async def execute(self, tool, args):
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._run(tool, args))

    def _adb(self, *cmds) -> dict:
        dev = ["-s", self.device] if self.device else []
        r = subprocess.run([self.adb] + dev + list(cmds),
                           capture_output=True, text=True, timeout=15,
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0)
        return {"ok": r.returncode==0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}

    def _run(self, tool, args):
        if tool == "android_connect":
            host = args.get("host","")
            if host: self.device = f"{host}:5555"
            return self._adb("connect", self.device)
        if tool == "android_tap":
            return self._adb("shell","input","tap", str(args["x"]), str(args["y"]))
        if tool == "android_swipe":
            return self._adb("shell","input","swipe",
                             str(args["x1"]),str(args["y1"]),str(args["x2"]),str(args["y2"]))
        if tool == "android_type":
            text = args.get("text","").replace(" ","%s")
            return self._adb("shell","input","text", text)
        if tool == "android_screenshot":
            out = args.get("path","screenshots/android.png")
            self._adb("shell","screencap","-p","/sdcard/screen.png")
            return self._adb("pull","/sdcard/screen.png", out)
        if tool == "android_launch":
            pkg = args.get("package","")
            return self._adb("shell","monkey","-p",pkg,"-c","android.intent.category.LAUNCHER","1")
        if tool == "android_shell":
            return self._adb("shell", args.get("command",""))
        raise ValueError(f"AndroidAgent: unknown '{tool}'")
