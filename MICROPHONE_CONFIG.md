# Microphone Configuration Guide

## Windows 10/11 Microphone Setup

### 1. Check Microphone Hardware
- Ensure your microphone is properly connected (USB, 3.5mm jack, or built-in)
- Test microphone in Windows Sound Settings

### 2. Windows Sound Settings
1. Right-click the speaker icon in the taskbar
2. Select "Sound Settings" or "Recording devices"
3. Find your microphone in the input devices list
4. Set it as the default recording device
5. Adjust input volume to appropriate level (usually 70-80%)

### 3. Privacy Settings
1. Go to Settings → Privacy → Microphone
2. Ensure "Allow apps to access your microphone" is ON
3. Ensure "Allow desktop apps to access your microphone" is ON

### 4. Python SpeechRecognition Configuration
The NEXORA voice engine uses the `SpeechRecognition` library with Google Speech-to-Text.

### 5. Testing Microphone
Run this test to verify microphone access:

```python
import speech_recognition as sr

def test_microphone():
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("Adjusting for ambient noise...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print("Listening for 5 seconds...")
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
            print("Processing...")
            text = recognizer.recognize_google(audio)
            print(f"Recognized: {text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_microphone()
```

### 6. Common Issues
- **Timeout Error**: Check if microphone is set as default device
- **Permission Denied**: Check Windows privacy settings
- **No Audio Input**: Check physical connection and volume levels
- **Recognition Failed**: Try speaking louder or closer to microphone

### 7. Language Support
NEXORA supports:
- English (en-US, en-IN)
- Tamil (ta-IN)
- Tanglish (mixed Tamil-English)

The voice engine automatically detects language based on text content.

### 8. NEXORA Integration
Once configured, the microphone will work through:
- Command Center UI → Voice page → "Listen & Process" button
- Voice commands: "Nexora, [command]"
- API endpoint: POST /voice/listen

### 9. Troubleshooting
If microphone still doesn't work:
1. Restart Windows
2. Reinstall SpeechRecognition: `pip install --upgrade SpeechRecognition`
3. Test with Windows Voice Recorder app
4. Check for driver updates for your audio device
