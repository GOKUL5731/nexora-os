import tempfile, wave, os
from pathlib import Path
from piper import PiperVoice

voice_name = 'en_US-ryan-high'
model_dir = Path('models/piper') / voice_name
model_path = model_dir / f'{voice_name}.onnx'

voice = PiperVoice.load(str(model_path))
tmp = tempfile.mktemp(suffix='.wav')

with wave.open(tmp, 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(voice.config.sample_rate)
    voice.synthesize('Testing stream raw', wf)

print('Method 1 (wave open) size:', os.path.getsize(tmp))
os.unlink(tmp)

tmp2 = tempfile.mktemp(suffix='.wav')
with wave.open(tmp2, 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(voice.config.sample_rate)
    for audio_bytes in voice.synthesize_stream_raw('Testing stream raw'):
        wf.writeframes(audio_bytes)
print('Method 2 (stream_raw) size:', os.path.getsize(tmp2))
os.unlink(tmp2)

tmp3 = tempfile.mktemp(suffix='.wav')
with open(tmp3, 'wb') as f:
    # Does synthesize support writing directly to a normal file?
    try:
        voice.synthesize('Testing file open', f)
        print('Method 3 (file write) size:', os.path.getsize(tmp3))
    except Exception as e:
        print('Method 3 error:', e)
os.unlink(tmp3)
