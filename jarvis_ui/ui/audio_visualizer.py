import numpy as np
import sounddevice as sd
from PySide6.QtCore import QThread, Signal

class AudioVisualizerThread(QThread):
    audio_level_signal = Signal(float)

    def __init__(self):
        super().__init__()
        self.running = True

    def run(self):
        try:
            # Open default input stream
            with sd.InputStream(callback=self.audio_callback, channels=1, samplerate=44100, blocksize=2048):
                while self.running:
                    self.msleep(50)
        except Exception as e:
            print(f"Audio init failed, generating mock data: {e}")
            # Mock audio for fallback if no microphone is available
            while self.running:
                val = np.random.uniform(0.1, 0.5)
                self.audio_level_signal.emit(val)
                self.msleep(100)

    def audio_callback(self, indata, frames, time, status):
        if not self.running:
            return
        # Calculate RMS volume and normalize to 0.0 - 1.0 range
        volume_norm = np.linalg.norm(indata) * 10
        level = min(1.0, volume_norm / 50.0)
        self.audio_level_signal.emit(level)

    def stop(self):
        self.running = False
        self.wait()
