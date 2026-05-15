import asyncio
import tempfile
import subprocess
import os
from pathlib import Path
import edge_tts

async def test_edge():
    tmp = tempfile.mktemp(suffix='.mp3')
    print("Generating audio to:", tmp)
    comm = edge_tts.Communicate('Hello Sir, JARVIS speaking test.', 'en-IN-PrabhatNeural')
    await comm.save(tmp)
    size = Path(tmp).stat().st_size
    print(f'MP3 generated: {tmp} ({size} bytes)')
    
    ps = (
        f"Add-Type -AssemblyName PresentationCore;"
        f"$p=New-Object System.Windows.Media.MediaPlayer;"
        f"$p.Open('{tmp}');"
        f"$p.Play();"
        f"while($p.NaturalDuration.HasTimeSpan -eq $false){{Start-Sleep -Milliseconds 50}};"
        f"Start-Sleep -Seconds ([Math]::Ceiling($p.NaturalDuration.TimeSpan.TotalSeconds));"
        f"$p.Close();"
    )
    print("Running powershell...")
    r = subprocess.run(["powershell", "-Command", ps], capture_output=True, text=True, timeout=15)
    print('Powershell exit:', r.returncode)
    if r.stderr: print('Stderr:', r.stderr[:200])
    os.unlink(tmp)

asyncio.run(test_edge())
print('Done')
