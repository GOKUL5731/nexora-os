import tempfile, wave, os
from pathlib import Path
from piper import PiperVoice
import winsound

voice_name = 'en_US-ryan-high'
model_dir = Path('models/piper') / voice_name
model_path = model_dir / f'{voice_name}.onnx'

print('Loading voice...')
voice = PiperVoice.load(str(model_path))

tmp = tempfile.mktemp(suffix='.wav')
print('Synthesizing to', tmp)
with wave.open(tmp, 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(voice.config.sample_rate)
    voice.synthesize('Hello Sir, testing playback.', wf)

size = os.path.getsize(tmp)
print(f'Wav size: {size} bytes')

print('Playing with winsound...')
try:
    winsound.PlaySound(tmp, winsound.SND_FILENAME)
    print('Done playing with winsound.')
except Exception as e:
    print('Winsound failed:', e)

os.unlink(tmp)
