"""
JARVIS Voice Engine — GPU-Accelerated
STT: faster-whisper (CUDA on RTX 4050) with wake word detection
TTS: Piper TTS (offline) + edge-tts fallback
Multilingual: English + Tamil
Continuous listen mode with interrupt support
"""

import asyncio
import io
import logging
import queue
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("jarvis.voice")
IS_WIN = sys.platform == "win32"
ROOT = Path(__file__).resolve().parent.parent

# ── TTS backends in priority order ───────────────────────────────────────────
TTS_PRIORITY = ["piper", "edge_tts", "pyttsx3"]

# Piper voice models (download separately)
PIPER_VOICES = {
    "en": "en_US-ryan-high",       # Premium male English
    "ta": "ta_IN-cmu-medium",      # Tamil
}


class VoiceEngine:
    """
    Unified voice engine: STT (faster-whisper GPU) + TTS (Piper/edge-tts).
    Drop-in upgrade for voice_agent.py — same interface.
    """

    def __init__(self, config: dict):
        self.config      = config
        vcfg             = config.get("voice", {})
        self.wake_word   = vcfg.get("wake_word", "jarvis").lower()
        self.stt_model   = vcfg.get("stt_model", "base")
        self.language    = vcfg.get("language", "auto")
        self.tts_backend = vcfg.get("tts_backend", "edge_tts")
        self.device      = vcfg.get("stt_device", "cuda")   # cuda | cpu
        self.compute     = vcfg.get("stt_compute", "float16")  # float16 for GPU

        self._whisper    = None          # faster-whisper model (lazy)
        self._listening  = False
        self._speaking   = False
        self._speak_proc = None          # current TTS subprocess
        self._cmd_queue: queue.Queue = queue.Queue()
        try:
            from core.event_bus import get_event_bus
            self.bus = get_event_bus()
        except Exception:
            self.bus = None
        self._publish_voice_state("idle")

    # ════════════════════════════════════════════════════════════════════════
    # TTS — Text to Speech
    # ════════════════════════════════════════════════════════════════════════

    async def speak(self, text: str, interrupt: bool = True) -> dict:
        if not text.strip():
            return {"ok": True}
        if interrupt and self._speaking:
            self.stop_speaking()
        logger.info(f"TTS: {text[:60]}")
        self._speaking = True
        self._publish_voice_state("speaking", text=text[:200], speaking=True)
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._speak_sync, text)
        finally:
            self._speaking = False
            self._publish_voice_state("idle", speaking=False)
        return {"ok": True, "text": text}

    def _speak_sync(self, text: str):
        backend = self.tts_backend
        if backend == "piper" and not self._piper(text):
            backend = "edge_tts"
        if backend == "edge_tts" and not self._edge_tts(text):
            backend = "pyttsx3"
        if backend == "pyttsx3":
            self._pyttsx3(text)

    def stop_speaking(self):
        """Interrupt current speech immediately."""
        self._speaking = False
        if self._speak_proc and self._speak_proc.poll() is None:
            try:
                self._speak_proc.terminate()
            except Exception:
                pass
        self._publish_voice_state("idle", speaking=False)

    # ── Piper TTS ─────────────────────────────────────────────────────────────
    def _piper(self, text: str) -> bool:
        """
        Piper TTS — premium offline voice (ONNX, no GPU needed).
        Install: pip install piper-tts
        Voices: https://huggingface.co/rhasspy/piper-voices
        """
        try:
            from piper import PiperVoice
            import wave

            lang = "ta" if self._is_tamil(text) else "en"
            voice_name = PIPER_VOICES.get(lang, PIPER_VOICES["en"])
            model_dir  = ROOT / "models" / "piper" / voice_name

            if not model_dir.exists():
                logger.warning(f"Piper voice model not found: {model_dir}")
                return False

            voice = PiperVoice.load(str(model_dir / f"{voice_name}.onnx"))

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp = f.name

            with wave.open(tmp, "wb") as wf:
                voice.synthesize_wav(text, wf)

            self._play_wav(tmp)
            Path(tmp).unlink(missing_ok=True)
            return True

        except ImportError:
            logger.debug("Piper not installed: pip install piper-tts")
            return False
        except Exception as e:
            logger.warning(f"Piper error: {e}")
            return False

    # ── Edge TTS (Microsoft free neural voices) ───────────────────────────────
    def _edge_tts(self, text: str) -> bool:
        try:
            import asyncio
            import edge_tts

            lang  = "ta" if self._is_tamil(text) else "en"
            voice = "ta-IN-ValluvarNeural" if lang == "ta" else "en-IN-PrabhatNeural"

            async def _gen():
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    tmp = f.name
                comm = edge_tts.Communicate(text, voice)
                await comm.save(tmp)
                return tmp

            loop = asyncio.new_event_loop()
            tmp  = loop.run_until_complete(_gen())
            loop.close()

            self._play_mp3(tmp)
            Path(tmp).unlink(missing_ok=True)
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.warning(f"edge-tts error: {e}")
            return False

    # ── pyttsx3 fallback ──────────────────────────────────────────────────────
    def _pyttsx3(self, text: str):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 165)
            voices = engine.getProperty("voices")
            for v in voices:
                if "david" in v.name.lower():
                    engine.setProperty("voice", v.id)
                    break
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            logger.error(f"pyttsx3 error: {e}")
            print(f"JARVIS: {text}")

    # ── Audio playback helpers ─────────────────────────────────────────────────
    def _play_wav(self, path: str):
        self._play_mp3(path)

    def _play_mp3(self, path: str):
        if IS_WIN:
            ps_cmd = (
                f"Add-Type -AssemblyName PresentationCore;"
                f"$p=New-Object System.Windows.Media.MediaPlayer;"
                f"$p.Open('{path}');"
                f"$p.Play();"
                f"while($p.NaturalDuration.HasTimeSpan -eq $false){{Start-Sleep -Milliseconds 50}};"
                f"Start-Sleep -Seconds ([Math]::Ceiling($p.NaturalDuration.TimeSpan.TotalSeconds));"
                f"$p.Close();"
            )
            self._speak_proc = subprocess.Popen(
                ["powershell", "-Command", ps_cmd],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._speak_proc.wait()
        else:
            subprocess.run(["mpg123", path], capture_output=True)

    # ════════════════════════════════════════════════════════════════════════
    # STT — Speech to Text (faster-whisper GPU)
    # ════════════════════════════════════════════════════════════════════════

    def _load_whisper(self):
        if self._whisper:
            return
        try:
            from faster_whisper import WhisperModel
            device  = self.device
            compute = self.compute
            # Fallback to CPU if CUDA unavailable
            try:
                import torch
                if not torch.cuda.is_available():
                    device  = "cpu"
                    compute = "int8"
                    logger.warning("CUDA unavailable — using CPU for Whisper")
                else:
                    logger.info(f"Whisper on GPU: {torch.cuda.get_device_name(0)}")
            except Exception as e:
                device  = "cpu"
                compute = "int8"
                logger.warning(f"Torch/CUDA unavailable for Whisper, using CPU settings: {e}")

            logger.info(f"Loading faster-whisper ({self.stt_model}) on {device}/{compute}...")
            self._whisper = WhisperModel(
                self.stt_model,
                device=device,
                compute_type=compute,
                download_root=str(ROOT / "models" / "whisper"),
            )
            logger.info("Whisper model loaded.")
        except Exception as e:
            logger.warning(f"faster-whisper unavailable; using fallback STT: {e}")
            self._whisper = None

    def _transcribe_bytes(self, wav_bytes: bytes) -> dict:
        self._load_whisper()
        if not self._whisper:
            return self._fallback_stt(wav_bytes)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            tmp = f.name
        try:
            lang = None if self.language == "auto" else self.language
            segments, info = self._whisper.transcribe(
                tmp,
                language=lang,
                beam_size=5,
                vad_filter=True,           # Filter silence
                vad_parameters={"min_silence_duration_ms": 500},
            )
            text = " ".join(s.text for s in segments).strip()
            return {"text": text, "language": info.language, "backend": "faster-whisper"}
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return {"text": "", "error": str(e)}
        finally:
            Path(tmp).unlink(missing_ok=True)

    def _fallback_stt(self, wav_bytes: bytes) -> dict:
        """SpeechRecognition fallback if faster-whisper not available."""
        try:
            import speech_recognition as sr, io
            r = sr.Recognizer()
            with sr.AudioFile(io.BytesIO(wav_bytes)) as src:
                audio = r.record(src)
            text = r.recognize_google(audio)
            return {"text": text, "backend": "google"}
        except Exception as e:
            return {"text": "", "error": str(e)}

    async def listen(self, timeout: float = 10) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._listen_sync, timeout)

    def _listen_sync(self, timeout: float) -> dict:
        self._publish_voice_state("listening", listening=True)
        try:
            capture = self._capture_audio(timeout)
            if capture.get("error"):
                self._publish_voice_state("error", error=capture["error"], listening=False)
                return {"text": "", "error": capture["error"]}

            self._publish_voice_state("transcribing", listening=False)
            result = self._transcribe_bytes(capture["wav_bytes"])
            if capture.get("backend") and "backend" not in result:
                result["backend"] = capture["backend"]
            self._publish_voice_state("idle", transcript=result.get("text", ""))
            return result
        finally:
            if not self._speaking:
                self._publish_voice_state("idle", listening=False)

    def _capture_audio(self, timeout: float) -> dict:
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            r.energy_threshold = 300
            r.dynamic_energy_threshold = True
            with sr.Microphone() as src:
                r.adjust_for_ambient_noise(src, duration=0.5)
                logger.info("Listening...")
                try:
                    audio = r.listen(src, timeout=timeout, phrase_time_limit=30)
                except sr.WaitTimeoutError:
                    return {"text": "", "error": "timeout"}
            return {"wav_bytes": audio.get_wav_data(), "backend": "speech_recognition"}
        except Exception as e:
            logger.warning(f"SpeechRecognition microphone failed, falling back to sounddevice: {e}")
            return self._capture_audio_sounddevice(timeout)

    def _capture_audio_sounddevice(self, timeout: float) -> dict:
        try:
            import numpy as np
            import sounddevice as sd
        except Exception as e:
            return {"error": f"Microphone unavailable: {e}"}

        sample_rate = 16000
        channels = 1
        start_threshold = 0.02
        silence_threshold = 0.01
        max_phrase_seconds = 12
        silence_seconds = 1.2
        chunks = []
        audio_queue: queue.Queue = queue.Queue()
        speech_started = False
        silence_for = 0.0
        listen_deadline = time.monotonic() + timeout
        phrase_deadline = None

        def callback(indata, frames, _time, status):
            if status:
                logger.debug(f"sounddevice status: {status}")
            audio_queue.put(indata.copy())

        try:
            with sd.InputStream(
                samplerate=sample_rate,
                channels=channels,
                dtype="float32",
                callback=callback,
                blocksize=int(sample_rate * 0.2),
            ):
                logger.info("Listening with sounddevice fallback...")
                while True:
                    if not speech_started and time.monotonic() > listen_deadline:
                        return {"error": "No speech detected"}
                    if phrase_deadline and time.monotonic() > phrase_deadline:
                        break

                    try:
                        chunk = audio_queue.get(timeout=0.25)
                    except queue.Empty:
                        continue

                    level = float(np.abs(chunk).mean())
                    self._publish_audio_level(level)
                    if not speech_started:
                        if level >= start_threshold:
                            speech_started = True
                            phrase_deadline = time.monotonic() + max_phrase_seconds
                            chunks.append(chunk)
                        continue

                    chunks.append(chunk)
                    chunk_seconds = len(chunk) / sample_rate
                    if level < silence_threshold:
                        silence_for += chunk_seconds
                        if silence_for >= silence_seconds:
                            break
                    else:
                        silence_for = 0.0
        except Exception as e:
            return {"error": f"Microphone unavailable: {e}"}

        if not chunks:
            return {"error": "No speech detected"}

        audio = np.concatenate(chunks, axis=0).reshape(-1)
        pcm = np.clip(audio, -1.0, 1.0)
        pcm = (pcm * 32767).astype(np.int16)

        with io.BytesIO() as buf:
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(pcm.tobytes())
            wav_bytes = buf.getvalue()

        return {"wav_bytes": wav_bytes, "backend": "sounddevice"}

    # ════════════════════════════════════════════════════════════════════════
    # Wake Word Detection
    # ════════════════════════════════════════════════════════════════════════

    def start_wake_word(self, callback: Callable[[str], None]) -> dict:
        if self._listening:
            return {"status": "already_running"}
        self._listening = True
        self._publish_voice_state("wake_listening", listening=True, wake_word=self.wake_word)
        t = threading.Thread(
            target=self._wake_loop, args=(callback,), daemon=True, name="jarvis-wake"
        )
        t.start()
        logger.info(f"Wake word listener started: '{self.wake_word}'")
        return {"status": "started", "wake_word": self.wake_word}

    def _wake_loop(self, callback: Callable):
        self._load_whisper()
        recognizer = None
        sr = None
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 400
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold = 0.6
        except Exception as e:
            logger.warning(f"SpeechRecognition wake capture unavailable, using sounddevice: {e}")

        while self._listening:
            try:
                if recognizer is not None and sr is not None:
                    try:
                        with sr.Microphone() as src:
                            audio = recognizer.listen(src, timeout=5, phrase_time_limit=6)
                        result = self._transcribe_bytes(audio.get_wav_data())
                    except Exception as mic_err:
                        logger.debug(f"SpeechRecognition wake capture failed: {mic_err}")
                        capture = self._capture_audio_sounddevice(5)
                        if capture.get("error"):
                            time.sleep(0.5)
                            continue
                        result = self._transcribe_bytes(capture["wav_bytes"])
                else:
                    capture = self._capture_audio_sounddevice(5)
                    if capture.get("error"):
                        time.sleep(0.5)
                        continue
                    result = self._transcribe_bytes(capture["wav_bytes"])

                text = result.get("text", "").lower().strip()
                if not text:
                    continue
                logger.debug(f"Heard: {text!r}")

                if self.wake_word in text:
                    command = text.replace(self.wake_word, "").strip(", .")
                    logger.info(f"Wake: command='{command}'")
                    self._publish_voice_state("wake_detected", transcript=command, listening=True)
                    if callback:
                        callback(command or "__wake__")
            except Exception as e:
                logger.debug(f"Wake loop retrying after error: {e}")
                time.sleep(0.2)

    def stop(self):
        self._listening = False
        self.stop_speaking()
        self._publish_voice_state("stopped", listening=False, speaking=False)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _is_tamil(self, text: str) -> bool:
        return any("\u0B80" <= c <= "\u0BFF" for c in text)

    def _publish_voice_state(self, status: str, **extra):
        if not self.bus:
            return
        listening = extra.pop("listening", self._listening)
        speaking = extra.pop("speaking", self._speaking)
        state = {
            "status": status,
            "listening": bool(listening),
            "speaking": bool(speaking),
            "wake_word": self.wake_word,
            "tts_backend": self.tts_backend,
            "stt_model": self.stt_model,
            **extra,
        }
        self.bus.set_state("voice", state, source="voice_engine")
        self.bus.publish("voice.status", state, source="voice_engine")

    def _publish_audio_level(self, level: float):
        if not self.bus:
            return
        payload = {"level": max(0.0, min(1.0, float(level) * 30.0))}
        self.bus.set_state("audio", payload, source="voice_engine", publish=False)
        self.bus.publish("audio.level", payload, source="voice_engine")
